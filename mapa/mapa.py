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

from backend.cache import (
    TTLCache,
    clave_params,
    modo_datos,
    respuesta_cache,
)
from backend.db import TursoConnection

COMPONENT_DIR = Path(__file__).resolve().parent
ROOT = COMPONENT_DIR.parent
STAGING = ROOT / "data" / "moviris_staging.db"
STATIC_FILES = {"style.css", "script.js"}

DEFAULT_CELLS = 20000   # celdas que se envían al mapa por defecto
MAX_CELLS = 30000       # tope máximo aceptado en ?limit=
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

bp = Blueprint("mapa", __name__)
_META_CACHE = TTLCache(ttl=300, maxsize=2)
_CELLS_CACHE = TTLCache(ttl=300, maxsize=12)


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ---------------------------------------------------------------- páginas
@bp.get("/mapa")
@bp.get("/mapa/")
@bp.get("/mapa/index.html")
def page():
    return _no_store(send_from_directory(COMPONENT_DIR, "index.html"))


@bp.get("/mapa/<path:filename>")
def static_file(filename):
    # Solo se sirven los archivos del front; mapa.py nunca se expone
    if filename not in STATIC_FILES:
        abort(404)
    return _no_store(send_from_directory(COMPONENT_DIR, filename))


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
    key = ("meta", modo_datos())
    cached = _META_CACHE.get(key)
    if cached is not None:
        return respuesta_cache(cached, hit=True)

    con = _connect()
    try:
        row = con.execute("SELECT MIN(acq_date), MAX(acq_date) FROM fire_cells_daily").fetchone()
    finally:
        con.close()
    if not row or not row[0]:
        raise ApiError("La base no tiene datos.", 503)

    payload = {"min_date": row[0], "max_date": row[1]}
    _META_CACHE.set(key, payload)
    return respuesta_cache(payload)


CELL_COLUMNS = ["lat", "lon", "days", "detections", "frp_max",
                "critical_days", "unusual_days", "last_date", "conf_max"]


@bp.get("/api/mapa/cells")
def cells():
    params = _query_params()
    try:
        limit = max(1, min(int(request.args.get("limit", DEFAULT_CELLS)), MAX_CELLS))
    except ValueError:
        limit = DEFAULT_CELLS
    try:
        grid = round(float(request.args.get("grid", 0.01)), 3)
    except (TypeError, ValueError):
        grid = 0.01
    grid = max(0.01, min(5.0, grid))

    key = ("cells", modo_datos(), *clave_params(*params), limit, grid)
    cached = _CELLS_CACHE.get(key)
    if cached is not None:
        return respuesta_cache(cached, hit=True)

    # Agrupación por cuadrícula: en zoom lejano se usa 0.5°/1° para cubrir
    # todo el país con pocas celdas; al acercarse, el frontend pide 0.01°.
    cell_expr = (
        "SELECT ROUND(ROUND(cell_lat / ?) * ?, 5) AS lat, "
        "ROUND(ROUND(cell_lon / ?) * ?, 5) AS lon, "
        "COUNT(*) AS days, SUM(detections) AS detections, "
        "MAX(frp_max) AS frp_max, SUM(status = 'critical') AS critical_days, "
        "SUM(status = 'unusual') AS unusual_days, MAX(acq_date) AS last_date, "
        "MAX(confidence_max) AS conf_max "
        f"FROM fire_cells_daily WHERE {WHERE} GROUP BY lat, lon"
    )
    con = _connect()
    try:
        summary_row = con.execute(
            "SELECT COUNT(*), COALESCE(SUM(days), 0), COALESCE(SUM(detections), 0), "
            "COALESCE(SUM(critical_days), 0), COALESCE(SUM(unusual_days), 0) "
            f"FROM ({cell_expr})",
            (grid, grid, grid, grid, *_sql_params(params)),
        ).fetchone()
        rows = con.execute(
            f"{cell_expr} ORDER BY days DESC, detections DESC LIMIT ?",
            (grid, grid, grid, grid, *_sql_params(params), limit),
        ).fetchall()
    finally:
        con.close()

    total_cells = int(summary_row[0] or 0) if summary_row else 0
    cell_days = int(summary_row[1] or 0) if summary_row else 0
    detections = int(summary_row[2] or 0) if summary_row else 0
    critical = int(summary_row[3] or 0) if summary_row else 0
    unusual = int(summary_row[4] or 0) if summary_row else 0
    summary = {
        "cells": total_cells,
        "cell_days": cell_days,
        "detections": detections,
        "critical_days": critical,
        "unusual_days": unusual,
        "normal_days": cell_days - critical - unusual,
    }

    payload = {
        "columns": CELL_COLUMNS,
        "cells": [list(r) for r in rows],
        "summary": summary,
        "shown": len(rows),
        "truncated": total_cells > len(rows),
        "grid": grid,
    }
    _CELLS_CACHE.set(key, payload)
    return respuesta_cache(payload)


CSV_COLUMNS = ["acq_date", "cell_lat", "cell_lon", "detections", "frp_max",
               "frp_sum_norm", "confidence_max", "sensors", "status", "z_score", "is_nrt"]
MAX_CSV_ROWS = 350_000


@bp.get("/api/mapa/csv")
def csv_export():
    params = _query_params()
    sql_params = _sql_params(params)
    _connect().close()  # valida modo y existencia antes de empezar a transmitir

    # Turso devuelve el resultado completo en memoria; un CSV de millones de
    # filas tumbaría el proceso. En modo Turso se exige un rango más pequeño.
    if _turso_on():
        con = _connect()
        try:
            total = con.execute(
                f"SELECT COUNT(*) FROM fire_cells_daily WHERE {WHERE}",
                sql_params,
            ).fetchone()[0]
        finally:
            con.close()
        if total and total > MAX_CSV_ROWS:
            raise ApiError(
                f"El CSV tendría {total:,} filas. Reduce el área o las fechas "
                f"(máximo {MAX_CSV_ROWS:,} filas en modo Turso).",
                413,
            )

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
