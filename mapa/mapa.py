"""
MOVIRIS · Mapa
API de consulta por área de interés y rango de fechas (Flask Blueprint).

Integración en backend/app.py:
    from mapa.mapa import bp as mapa_bp
    app.register_blueprint(mapa_bp)

Rutas:
    GET /mapa/                 página del mapa
    GET /mapa/style.css|script.js
    GET /api/mapa/meta         rango de fechas disponible
    GET /api/mapa/cells        celdas agregadas del área (para dibujar)
    GET /api/mapa/csv          CSV de celdas-día del área y las fechas

Parámetros de /cells y /csv:
    south, north, west, east   límites del área (grados)
    start, end                 fechas YYYY-MM-DD
    conf                       confianza mínima: 0 (todas), 1 (nominal+), 2 (alta)

Lee data/moviris_staging.db en modo local o Turso cuando
TURSO_ENABLED=true.
"""
import csv
import io
import re
import sqlite3
from pathlib import Path

from flask import (Blueprint, Response, abort, jsonify, request,
                   send_from_directory, stream_with_context)

from backend.db import TursoConnection

COMPONENT_DIR = Path(__file__).resolve().parent
ROOT = COMPONENT_DIR.parent
STAGING = ROOT / "data" / "moviris_staging.db"
STATIC_FILES = {"style.css", "script.js"}

DEFAULT_CELLS = 20000   # celdas que se envían al mapa por defecto
MAX_CELLS = 30000       # tope máximo aceptado en ?limit=
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

bp = Blueprint("mapa", __name__)


# ---------------------------------------------------------------- páginas
@bp.get("/mapa")
@bp.get("/mapa/")
@bp.get("/mapa/index.html")
def page():
    return send_from_directory(COMPONENT_DIR, "index.html")


@bp.get("/mapa/<path:filename>")
def static_file(filename):
    # Solo se sirven los archivos del front; mapa.py nunca se expone
    if filename not in STATIC_FILES:
        abort(404)
    return send_from_directory(COMPONENT_DIR, filename)


# ---------------------------------------------------------------- utilidades
class ApiError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


@bp.errorhandler(ApiError)
def _handle_api_error(err):
    return jsonify({"error": str(err)}), err.status


def _turso_on():
    try:
        from backend.settings import turso_enabled
        return bool(turso_enabled())
    except Exception:
        return False


def _connect():
    if _turso_on():
        return TursoConnection()
    if not STAGING.exists():
        raise ApiError("No hay datos locales. Ejecuta primero el ETL.", 503)
    con = sqlite3.connect(STAGING.as_uri() + "?mode=ro", uri=True, timeout=10)
    return con


def _number(name, low, high):
    try:
        value = float(request.args[name])
    except (KeyError, ValueError):
        raise ApiError(f"Parámetro inválido o faltante: {name}")
    if not low <= value <= high:
        raise ApiError(f"El parámetro {name} está fuera de rango.")
    return value


def _query_params():
    south, north = _number("south", -90, 90), _number("north", -90, 90)
    west, east = _number("west", -180, 180), _number("east", -180, 180)
    if south >= north or west >= east:
        raise ApiError("Área no válida: el sur debe ser menor que el norte y el oeste menor que el este.")

    start, end = request.args.get("start", ""), request.args.get("end", "")
    if not (DATE_RE.match(start) and DATE_RE.match(end)):
        raise ApiError("Las fechas deben tener el formato AAAA-MM-DD.")
    if start > end:
        raise ApiError("La fecha inicial debe ser anterior o igual a la final.")

    try:
        conf = int(request.args.get("conf", 0))
    except ValueError:
        conf = -1
    if conf not in (0, 1, 2):
        raise ApiError("El parámetro conf debe ser 0, 1 o 2.")

    return south, north, west, east, start, end, conf


WHERE = ("cell_lat BETWEEN ? AND ? AND cell_lon BETWEEN ? AND ? "
         "AND acq_date BETWEEN ? AND ? AND confidence_max >= ?")


def _sql_params(p):
    south, north, west, east, start, end, conf = p
    return (south, north, west, east, start, end, conf)


# ---------------------------------------------------------------- API
@bp.get("/api/mapa/meta")
def meta():
    con = _connect()
    try:
        row = con.execute("SELECT MIN(acq_date), MAX(acq_date) FROM fire_cells_daily").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise ApiError("La base no tiene datos.", 503)
    return jsonify({"min_date": row[0], "max_date": row[1]})


CELL_COLUMNS = ["lat", "lon", "days", "detections", "frp_max",
                "critical_days", "unusual_days", "last_date", "conf_max"]


@bp.get("/api/mapa/cells")
def cells():
    params = _query_params()
    try:
        limit = max(1, min(int(request.args.get("limit", DEFAULT_CELLS)), MAX_CELLS))
    except ValueError:
        limit = DEFAULT_CELLS

    con = _connect()
    try:
        rows = con.execute(
            "SELECT cell_lat, cell_lon, COUNT(*), SUM(detections), MAX(frp_max), "
            "SUM(status = 'critical'), SUM(status = 'unusual'), MAX(acq_date), MAX(confidence_max) "
            f"FROM fire_cells_daily WHERE {WHERE} GROUP BY cell_lat, cell_lon",
            _sql_params(params),
        ).fetchall()
    finally:
        con.close()

    cell_days = sum(r[2] for r in rows)
    critical = sum(r[5] or 0 for r in rows)
    unusual = sum(r[6] or 0 for r in rows)
    summary = {
        "cells": len(rows),
        "cell_days": cell_days,
        "detections": sum(r[3] or 0 for r in rows),
        "critical_days": critical,
        "unusual_days": unusual,
        "normal_days": cell_days - critical - unusual,
    }

    rows.sort(key=lambda r: (r[2], r[3] or 0), reverse=True)
    shown = rows[:limit]
    return jsonify({
        "columns": CELL_COLUMNS,
        "cells": [list(r) for r in shown],
        "summary": summary,
        "shown": len(shown),
        "truncated": len(rows) > len(shown),
    })


CSV_COLUMNS = ["acq_date", "cell_lat", "cell_lon", "detections", "frp_max",
               "frp_sum_norm", "confidence_max", "sensors", "status", "z_score", "is_nrt"]


@bp.get("/api/mapa/csv")
def csv_export():
    params = _query_params()
    sql_params = _sql_params(params)
    _connect().close()  # valida modo y existencia antes de empezar a transmitir

    def generate():
        con = _connect()
        try:
            cursor = con.execute(
                f"SELECT {', '.join(CSV_COLUMNS)} FROM fire_cells_daily "
                f"WHERE {WHERE} ORDER BY acq_date, cell_lat, cell_lon",
                sql_params,
            )
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(CSV_COLUMNS)
            yield buffer.getvalue()
            while True:
                chunk = cursor.fetchmany(5000)
                if not chunk:
                    break
                buffer.seek(0)
                buffer.truncate(0)
                writer.writerows(chunk)
                yield buffer.getvalue()
        finally:
            con.close()

    filename = f"moviris_celdas_{params[4]}_{params[5]}.csv"
    return Response(
        stream_with_context(generate()),
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
