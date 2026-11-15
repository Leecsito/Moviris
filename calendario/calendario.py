"""
MOVIRIS · Calendario
API del calendario de actividad de quema por área de interés (Flask Blueprint).

Integración en backend/app.py (después de registrar el blueprint del mapa):
    from calendario.calendario import bp as calendario_bp
    app.register_blueprint(calendario_bp)

Reutiliza _connect(), ApiError y _number() de mapa/mapa.py y lee el staging
local o Turso según TURSO_ENABLED.

Rutas:
    GET /calendario/               página
    GET /calendario/style.css|script.js
    GET /api/calendario/matrix     matriz año × mes, mes actual vs. mediana y
                                   semanas con más celdas críticas
    GET /api/calendario/month      detalle diario de un mes

Parámetros: south, north, west, east (área), conf (0, 1 o 2) y, en /month,
year y month. El calendario usa todo el período disponible.
"""
import statistics
from pathlib import Path

from flask import Blueprint, abort, jsonify, request, send_from_directory

from mapa.mapa import ApiError, _connect, _number

COMPONENT_DIR = Path(__file__).resolve().parent
STATIC_FILES = {"style.css", "script.js"}

AREA = "cell_lat BETWEEN ? AND ? AND cell_lon BETWEEN ? AND ? AND confidence_max >= ?"
# celdas-día activas, detecciones, celdas-día críticas, celdas-día inusuales
METRICS = "COUNT(*), SUM(detections), SUM(status = 'critical'), SUM(status = 'unusual')"

bp = Blueprint("calendario", __name__)


@bp.errorhandler(ApiError)
def _handle_api_error(err):
    return jsonify({"error": str(err)}), err.status


# ---------------------------------------------------------------- páginas
@bp.get("/calendario")
@bp.get("/calendario/")
@bp.get("/calendario/index.html")
def page():
    return send_from_directory(COMPONENT_DIR, "index.html")


@bp.get("/calendario/<path:filename>")
def static_file(filename):
    if filename not in STATIC_FILES:  # calendario.py nunca se expone
        abort(404)
    return send_from_directory(COMPONENT_DIR, filename)


# ---------------------------------------------------------------- utilidades
def _area_params():
    south, north = _number("south", -90, 90), _number("north", -90, 90)
    west, east = _number("west", -180, 180), _number("east", -180, 180)
    if south >= north or west >= east:
        raise ApiError("Área no válida: el sur debe ser menor que el norte y el oeste menor que el este.")
    try:
        conf = int(request.args.get("conf", 0))
    except ValueError:
        conf = -1
    if conf not in (0, 1, 2):
        raise ApiError("El parámetro conf debe ser 0, 1 o 2.")
    return (south, north, west, east, conf)


def _ints(row):
    return [int(v or 0) for v in row]


def _current_vs_median(con, area, min_date, max_date):
    """Compara el tramo transcurrido del último mes con el mismo tramo de años anteriores."""
    year, month, day = int(max_date[:4]), int(max_date[5:7]), int(max_date[8:10])
    rows = con.execute(
        f"SELECT year, {METRICS} FROM fire_cells_daily "
        f"WHERE {AREA} AND month = ? AND CAST(substr(acq_date, 9, 2) AS INTEGER) <= ? "
        "GROUP BY year",
        area + (month, day),
    ).fetchall()
    by_year = {r[0]: _ints(r[1:]) for r in rows}
    zeros = [0, 0, 0, 0]

    # Solo años cuyo tramo completo cae dentro del período con datos
    years = [y for y in range(int(min_date[:4]), year) if f"{y}-{month:02d}-01" >= min_date]
    history = [by_year.get(y, zeros) for y in years]
    median = [statistics.median(h[i] for h in history) for i in range(4)] if history else None

    return {"year": year, "month": month, "day": day,
            "values": by_year.get(year, zeros), "median": median, "years": years}


# ---------------------------------------------------------------- API
@bp.get("/api/calendario/matrix")
def matrix():
    area = _area_params()
    con = _connect()
    try:
        bounds = con.execute("SELECT MIN(acq_date), MAX(acq_date) FROM fire_cells_daily").fetchone()
        if not bounds or not bounds[0]:
            raise ApiError("La base no tiene datos.", 503)

        months = con.execute(
            f"SELECT year, month, {METRICS} FROM fire_cells_daily WHERE {AREA} "
            "GROUP BY year, month ORDER BY year, month",
            area,
        ).fetchall()

        weeks = con.execute(
            f"SELECT year, week_of_year, {METRICS} FROM fire_cells_daily WHERE {AREA} "
            "GROUP BY year, week_of_year HAVING SUM(status = 'critical') > 0 "
            "ORDER BY SUM(status = 'critical') DESC, COUNT(*) DESC LIMIT 10",
            area,
        ).fetchall()

        current = _current_vs_median(con, area, bounds[0], bounds[1])
    finally:
        con.close()

    return jsonify({
        "min_date": bounds[0],
        "max_date": bounds[1],
        "metrics": ["cell_days", "detections", "critical", "unusual"],
        "months": [_ints(r) for r in months],   # [año, mes, m1, m2, m3, m4]
        "weeks": [_ints(r) for r in weeks],     # [año, semana, m1, m2, m3, m4]
        "current": current,
    })


@bp.get("/api/calendario/month")
def month_detail():
    area = _area_params()
    try:
        year = int(request.args["year"])
        month = int(request.args["month"])
    except (KeyError, ValueError):
        raise ApiError("Los parámetros year y month son obligatorios.")
    if not (2000 <= year <= 2100 and 1 <= month <= 12):
        raise ApiError("Año o mes fuera de rango.")

    con = _connect()
    try:
        rows = con.execute(
            f"SELECT acq_date, {METRICS} FROM fire_cells_daily "
            f"WHERE {AREA} AND year = ? AND month = ? GROUP BY acq_date ORDER BY acq_date",
            area + (year, month),
        ).fetchall()
    finally:
        con.close()

    return jsonify({
        "year": year,
        "month": month,
        "days": [[r[0]] + _ints(r[1:]) for r in rows],  # [fecha, m1, m2, m3, m4]
    })
