"""
MOVIRIS · Dashboard
API de indicadores históricos por área de interés (Flask Blueprint).

Integración en backend/app.py (después de los blueprints del mapa y del calendario):
    from dashboard.dashboard import bp as dashboard_bp
    app.register_blueprint(dashboard_bp)

Reutiliza _connect() y ApiError de mapa/mapa.py y los parámetros de
calendario/calendario.py; lee el staging local o Turso según TURSO_ENABLED.

Rutas:
    GET /dashboard/                 página
    GET /dashboard/style.css|script.js
    GET /api/dashboard/summary      totales, matriz año × mes, celdas por año y
                                    cobertura por familia de sensores

Parámetros: south, north, west, east (área) y conf (0, 1 o 2).
Las estadísticas (media, mediana, anomalías) se calculan en script.js.
"""
from pathlib import Path

from flask import Blueprint, abort, jsonify, send_from_directory

from calendario.calendario import AREA, METRICS, _area_params, _ints
from mapa.mapa import ApiError, _connect

COMPONENT_DIR = Path(__file__).resolve().parent
STATIC_FILES = {"style.css", "script.js"}

bp = Blueprint("dashboard", __name__)


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.errorhandler(ApiError)
def _handle_api_error(err):
    return jsonify({"error": str(err)}), err.status


# ---------------------------------------------------------------- páginas
@bp.get("/dashboard")
@bp.get("/dashboard/")
@bp.get("/dashboard/index.html")
def page():
    return _no_store(send_from_directory(COMPONENT_DIR, "index.html"))


@bp.get("/dashboard/<path:filename>")
def static_file(filename):
    if filename not in STATIC_FILES:  # dashboard.py nunca se expone
        abort(404)
    return _no_store(send_from_directory(COMPONENT_DIR, filename))


# ---------------------------------------------------------------- utilidades
def _coverage(rows):
    """Celdas-día por año según qué familia de sensores las vio.

    Devuelve [año, solo MODIS, MODIS y VIIRS, solo VIIRS].
    """
    by_year = {}
    for year, sensors, count in rows:
        tokens = [t.strip() for t in (sensors or "").split(",") if t.strip()]
        if not tokens:
            continue
        has_modis = "MODIS" in tokens
        has_viirs = any(t != "MODIS" for t in tokens)
        slot = 1 if (has_modis and has_viirs) else (0 if has_modis else 2)
        by_year.setdefault(year, [0, 0, 0])[slot] += int(count or 0)
    return [[year] + counts for year, counts in sorted(by_year.items())]


# ---------------------------------------------------------------- API
@bp.get("/api/dashboard/summary")
def summary():
    area = _area_params()
    con = _connect()
    try:
        bounds = con.execute("SELECT MIN(acq_date), MAX(acq_date) FROM fire_cells_daily").fetchone()
        if not bounds or not bounds[0]:
            raise ApiError("La base no tiene datos.", 503)

        totals = con.execute(
            f"SELECT COUNT(DISTINCT cell_lat || ',' || cell_lon), {METRICS} "
            f"FROM fire_cells_daily WHERE {AREA}",
            area,
        ).fetchone()

        months = con.execute(
            f"SELECT year, month, {METRICS} FROM fire_cells_daily WHERE {AREA} "
            "GROUP BY year, month ORDER BY year, month",
            area,
        ).fetchall()

        year_cells = con.execute(
            "SELECT year, COUNT(DISTINCT cell_lat || ',' || cell_lon) FROM fire_cells_daily "
            f"WHERE {AREA} GROUP BY year ORDER BY year",
            area,
        ).fetchall()

        coverage = con.execute(
            f"SELECT year, sensors, COUNT(*) FROM fire_cells_daily WHERE {AREA} "
            "GROUP BY year, sensors",
            area,
        ).fetchall()
    finally:
        con.close()

    t = _ints(totals)
    return jsonify({
        "min_date": bounds[0],
        "max_date": bounds[1],
        "totals": {"cells": t[0], "cell_days": t[1], "detections": t[2],
                   "critical": t[3], "unusual": t[4]},
        "months": [_ints(r) for r in months],        # [año, mes, m1, m2, m3, m4]
        "year_cells": [_ints(r) for r in year_cells],  # [año, celdas con focos]
        "coverage": _coverage(coverage),              # [año, solo MODIS, ambos, solo VIIRS]
    })
