# -*- coding: utf-8 -*-
"""
Backend Flask de MOVIRIS.

Sirve el componente ETL (/etl) y expone una API JSON para:

    · listar/subir CSV
    · lanzar el ETL en segundo plano y consultar su progreso
    · reintentar la sincronización del staging
    · consultar estadísticas, celdas y máscara desde Turso

Ejecutar con:  python run.py
"""

from __future__ import annotations

import csv
import re
import shutil
import sqlite3
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request, send_from_directory
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from backend.db import (
    DatabaseError,
    health as db_health,
    list_cells,
    list_mask_sources,
    map_points,
    stats as db_stats,
)
from backend.jobs import JobBusy, JobError, JobManager
from backend.settings import turso_enabled
from etl.etl import DEFAULT_STAGING, ROOT
from mapa.mapa import bp as mapa_bp
from calendario.calendario import bp as calendario_bp
from dashboard.dashboard import bp as dashboard_bp
from backend.explain import bp as explain_bp

ETL_DIR = ROOT / "etl"
INICIO_DIR = ROOT / "inicio"
HEADER_DIR = ROOT / "header"
HACKATHON_DIR = ROOT / "hackathon"
UPLOADS_DIR = ROOT / "uploads"
MAX_UPLOAD_BYTES = 512 * 1024 * 1024
MAX_UPLOAD_FILES = 80
ALLOWED_EXTENSIONS = {".csv", ".zip"}
UPLOAD_ID_RE = re.compile(r"^[0-9a-f]{8,32}$")
REQUIRED_CSV_COLUMNS = {"latitude", "longitude", "acq_date"}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------


def human_size(size: float) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(value)} B"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _iso_from_timestamp(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(timespec="seconds")


def _json_body() -> dict[str, Any]:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


def _as_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _unique_path(folder: Path, filename: str) -> Path:
    candidate = folder / filename
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    suffix = candidate.suffix
    for index in range(2, 1000):
        candidate = folder / f"{stem}_{index}{suffix}"
        if not candidate.exists():
            return candidate
    raise OSError("No se pudo generar un nombre de archivo único.")


def csv_header_ok(path: Path) -> bool:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle), None)
    except (OSError, UnicodeDecodeError, csv.Error):
        return False
    if not header:
        return False
    normalized = {str(value).strip().lower().lstrip("\ufeff") for value in header}
    return REQUIRED_CSV_COLUMNS <= normalized


def _file_kind(path: Path) -> str:
    return "nrt" if "nrt" in path.stem.lower() else "archive"


def _server_entry(path: Path) -> dict[str, Any]:
    size = path.stat().st_size
    return {
        "id": path.relative_to(ROOT).as_posix(),
        "name": path.name,
        "group": path.parent.name,
        "kind": _file_kind(path),
        "size": size,
        "size_label": human_size(size),
        "source": "server",
    }


def _upload_entry(path: Path, batch_root: Path) -> dict[str, Any]:
    size = path.stat().st_size
    group = "Subida" if path.parent == batch_root else path.parent.name
    return {
        "id": path.relative_to(UPLOADS_DIR).as_posix(),
        "name": path.name,
        "group": group,
        "kind": _file_kind(path),
        "size": size,
        "size_label": human_size(size),
        "source": "upload",
    }


def list_server_files() -> list[dict[str, Any]]:
    if not HACKATHON_DIR.exists():
        return []
    entries = [_server_entry(path) for path in HACKATHON_DIR.rglob("*.csv") if path.is_file()]
    entries.sort(key=lambda item: (item["group"], item["kind"], item["name"]))
    return entries


def _batch_entry(folder: Path) -> dict[str, Any] | None:
    files = [_upload_entry(path, folder) for path in sorted(folder.rglob("*.csv")) if path.is_file()]
    if not files:
        return None
    total = sum(item["size"] for item in files)
    try:
        created = _iso_from_timestamp(folder.stat().st_mtime)
    except OSError:
        created = None
    return {
        "id": folder.name,
        "created_at": created,
        "size": total,
        "size_label": human_size(total),
        "file_count": len(files),
        "files": files,
    }


def list_upload_batches(limit: int = 10) -> list[dict[str, Any]]:
    if not UPLOADS_DIR.exists():
        return []
    folders = [path for path in UPLOADS_DIR.iterdir() if path.is_dir()]
    folders.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    batches: list[dict[str, Any]] = []
    for folder in folders:
        entry = _batch_entry(folder)
        if entry:
            batches.append(entry)
        if len(batches) >= limit:
            break
    return batches


def _cleanup_uploads(keep: int = 50, current: str | None = None) -> None:
    if not UPLOADS_DIR.exists() or job_manager.is_busy():
        return
    folders = [path for path in UPLOADS_DIR.iterdir() if path.is_dir()]
    folders.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for folder in folders[keep:]:
        if folder.name == current:
            continue
        shutil.rmtree(folder, ignore_errors=True)


def staging_info() -> dict[str, Any]:
    path = Path(DEFAULT_STAGING)
    if not path.exists():
        return {"exists": False, "ready": False, "path": str(path), "rows": {}}
    try:
        stat = path.stat()
    except OSError as exc:
        return {"exists": False, "ready": False, "path": str(path), "error": str(exc), "rows": {}}
    rows: dict[str, int] = {}
    error = None
    try:
        connection = sqlite3.connect(str(path))
        try:
            connection.execute("PRAGMA query_only = ON")
            for table in ("fire_cells_daily", "fire_baseline", "non_vegetation_mask"):
                rows[table] = int(
                    connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                )
        finally:
            connection.close()
    except sqlite3.Error as exc:
        error = str(exc)
    return {
        "exists": True,
        "ready": bool(rows.get("fire_cells_daily")),
        "path": str(path),
        "size": stat.st_size,
        "size_label": human_size(stat.st_size),
        "updated_at": _iso_from_timestamp(stat.st_mtime),
        "rows": rows,
        "error": error,
    }


def _resolve_server_file(value: Any) -> Path:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("Ruta de archivo vacía.")
    possible = Path(raw)
    candidates: list[Path] = []
    if possible.is_absolute():
        candidates.append(possible)
    else:
        candidates.append(ROOT / possible)
        candidates.append(HACKATHON_DIR / possible)
    root = HACKATHON_DIR.resolve()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        if (
            resolved.is_file()
            and resolved.suffix.lower() == ".csv"
            and resolved.is_relative_to(root)
        ):
            return resolved
    raise ValueError(f"Archivo no permitido o inexistente: {raw}")


def _resolve_upload(value: Any) -> list[Path]:
    upload_id = str(value or "").strip()
    if not UPLOAD_ID_RE.fullmatch(upload_id):
        raise ValueError(f"Identificador de subida no válido: {upload_id}")
    folder = (UPLOADS_DIR / upload_id).resolve()
    root = UPLOADS_DIR.resolve()
    if not folder.is_dir() or not folder.is_relative_to(root):
        raise ValueError(f"La subida {upload_id} no existe.")
    files = [path for path in folder.rglob("*.csv") if path.is_file()]
    if not files:
        raise ValueError(f"La subida {upload_id} no contiene CSV.")
    return files


def _resolve_run_files(payload: dict[str, Any]) -> list[Path]:
    files: list[Path] = []
    server_values = payload.get("server_files") or []
    if isinstance(server_values, str):
        server_values = [server_values]
    for value in server_values:
        files.append(_resolve_server_file(value))

    upload_values = payload.get("upload_ids") or []
    if isinstance(upload_values, str):
        upload_values = [upload_values]
    for value in upload_values:
        files.extend(_resolve_upload(value))

    unique: dict[str, Path] = {}
    for path in files:
        unique.setdefault(str(path.resolve()).lower(), path)
    if not unique:
        raise ValueError("Selecciona al menos un archivo CSV.")
    return list(unique.values())


# ---------------------------------------------------------------------------
# Aplicación
# ---------------------------------------------------------------------------

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES
app.config["JSON_SORT_KEYS"] = False
app.json.ensure_ascii = False

app.register_blueprint(mapa_bp)
app.register_blueprint(calendario_bp)
app.register_blueprint(dashboard_bp)
app.register_blueprint(explain_bp)

job_manager = JobManager()


def _no_store(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ------------------------------- Frontend ---------------------------------


def _send_frontend(filename: str):
    return _no_store(send_from_directory(ETL_DIR, filename))


def _send_root(filename: str):
    return _no_store(send_from_directory(ROOT, filename))


def _send_inicio(filename: str):
    return _no_store(send_from_directory(INICIO_DIR, filename))


def _send_header(filename: str):
    return _no_store(send_from_directory(HEADER_DIR, filename))


@app.get("/header/index.html")
def header_fragment():
    return _send_header("index.html")


@app.get("/header/style.css")
def header_styles():
    return _send_header("style.css")


@app.get("/header/script.js")
def header_script():
    return _send_header("script.js")


@app.get("/")
def welcome():
    return _send_root("index.html")


@app.get("/styles.css")
def welcome_styles():
    return _send_root("styles.css")


@app.get("/script.js")
def welcome_script():
    return _send_root("script.js")


@app.get("/etl")
@app.get("/etl/")
@app.get("/etl/index.html")
def etl_index():
    return _send_frontend("index.html")


@app.get("/style.css")
@app.get("/etl/style.css")
def etl_styles():
    return _send_frontend("style.css")


@app.get("/etl/script.js")
def etl_script():
    return _send_frontend("script.js")


@app.get("/inicio")
@app.get("/inicio/")
@app.get("/inicio/index.html")
def inicio_index():
    return _send_inicio("index.html")


@app.get("/inicio/style.css")
def inicio_styles():
    return _send_inicio("style.css")


@app.get("/inicio/script.js")
def inicio_script():
    return _send_inicio("script.js")


@app.get("/i18n.js")
def i18n_script():
    return _send_root("i18n.js")


@app.get("/explain.js")
def explain_script():
    return _send_root("explain.js")


@app.get("/explain.css")
def explain_styles():
    return _send_root("explain.css")


@app.get("/ico.svg")
def logo():
    # El icono vive en la raíz del proyecto; no se duplica en etl/.
    return _send_root("ico.svg")


@app.get("/favicon.ico")
def favicon():
    return "", 204


# -------------------------------- Salud -----------------------------------


@app.get("/api/health")
def health():
    database = db_health()
    return jsonify(
        {
            "ok": bool(database.get("ok")),
            "service": "moviris-etl",
            "mode": database.get("mode"),
            "turso_enabled": turso_enabled(),
            "database": database,
            "staging": staging_info(),
            "time": _iso_from_timestamp(time.time()),
        }
    )


# ------------------------------- Archivos ---------------------------------


@app.get("/api/files")
def files():
    return jsonify(
        {
            "server": list_server_files(),
            "uploads": list_upload_batches(),
            "hackathon_dir": "hackathon",
        }
    )


@app.post("/api/upload")
def upload():
    uploads = request.files.getlist("files") or request.files.getlist("file")
    uploads = [item for item in uploads if item and item.filename]
    if not uploads:
        return jsonify({"error": "No se recibió ningún archivo."}), 400
    if len(uploads) > MAX_UPLOAD_FILES:
        return jsonify({"error": f"Máximo {MAX_UPLOAD_FILES} archivos por subida."}), 400

    upload_id = uuid.uuid4().hex[:12]
    target = UPLOADS_DIR / upload_id
    target.mkdir(parents=True, exist_ok=True)
    rejected: list[str] = []
    valid: list[Path] = []
    extracted_bytes = 0

    for storage in uploads:
        original = storage.filename or ""
        safe = secure_filename(original)
        if not safe:
            rejected.append(f"{original or '(sin nombre)'}: nombre no válido")
            continue
        extension = Path(safe).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            rejected.append(f"{original}: solo se aceptan .csv o .zip")
            continue

        if extension == ".csv":
            destination = _unique_path(target, safe)
            try:
                storage.save(destination)
            except OSError as exc:
                rejected.append(f"{original}: {exc}")
                continue
            extracted_bytes += destination.stat().st_size
            if extracted_bytes > MAX_UPLOAD_BYTES:
                destination.unlink(missing_ok=True)
                rejected.append(f"{original}: se superó el límite de 512 MB")
                break
            if csv_header_ok(destination):
                valid.append(destination)
            else:
                destination.unlink(missing_ok=True)
                rejected.append(
                    f"{original}: faltan columnas latitude, longitude o acq_date"
                )
            continue

        # ZIP
        archive_path = _unique_path(target, safe)
        try:
            storage.save(archive_path)
        except OSError as exc:
            rejected.append(f"{original}: {exc}")
            continue
        try:
            with zipfile.ZipFile(archive_path) as archive:
                entries = [
                    info
                    for info in archive.infolist()
                    if not info.is_dir()
                    and info.filename.lower().endswith(".csv")
                    and "__MACOSX" not in info.filename
                ]
                if len(entries) > MAX_UPLOAD_FILES:
                    rejected.append(
                        f"{original}: se procesaron solo los primeros {MAX_UPLOAD_FILES} CSV"
                    )
                    entries = entries[:MAX_UPLOAD_FILES]
                folder_name = secure_filename(Path(safe).stem) or "zip"
                destination_root = _unique_path(target, folder_name)
                destination_root.mkdir(parents=True, exist_ok=True)
                for info in entries:
                    name = secure_filename(Path(info.filename).name)
                    if not name:
                        continue
                    if extracted_bytes + info.file_size > MAX_UPLOAD_BYTES:
                        rejected.append(f"{original}: se superó el límite de 512 MB")
                        break
                    destination = _unique_path(destination_root, name)
                    try:
                        with archive.open(info) as source, destination.open("wb") as output:
                            while True:
                                chunk = source.read(1024 * 1024)
                                if not chunk:
                                    break
                                extracted_bytes += len(chunk)
                                if extracted_bytes > MAX_UPLOAD_BYTES:
                                    raise ValueError("límite de 512 MB superado")
                                output.write(chunk)
                    except (OSError, ValueError, RuntimeError, zipfile.BadZipFile) as exc:
                        destination.unlink(missing_ok=True)
                        rejected.append(f"{info.filename}: {exc}")
                        break
                    if csv_header_ok(destination):
                        valid.append(destination)
                    else:
                        destination.unlink(missing_ok=True)
                        rejected.append(
                            f"{info.filename}: faltan columnas latitude, longitude o acq_date"
                        )
        except zipfile.BadZipFile:
            rejected.append(f"{original}: ZIP inválido")
        except (OSError, RuntimeError) as exc:
            rejected.append(f"{original}: {exc}")
        finally:
            archive_path.unlink(missing_ok=True)

    if not valid:
        shutil.rmtree(target, ignore_errors=True)
        return (
            jsonify(
                {
                    "error": "Ningún archivo contiene un CSV válido de FIRMS.",
                    "rejected": rejected,
                }
            ),
            400,
        )

    _cleanup_uploads(keep=50, current=upload_id)
    batch = _batch_entry(target) or {
        "id": upload_id,
        "created_at": _iso_from_timestamp(time.time()),
        "file_count": len(valid),
        "size": 0,
        "size_label": "0 B",
        "files": [],
    }
    return jsonify({"upload_id": upload_id, "batch": batch, "rejected": rejected}), 201


@app.delete("/api/uploads/<upload_id>")
def delete_upload(upload_id: str):
    if not UPLOAD_ID_RE.fullmatch(upload_id):
        return jsonify({"error": "Identificador de subida no válido."}), 400
    if job_manager.is_busy():
        return (
            jsonify(
                {
                    "error": "No se pueden quitar archivos mientras hay un ETL en ejecución."
                }
            ),
            409,
        )
    root = UPLOADS_DIR.resolve()
    folder = (UPLOADS_DIR / upload_id).resolve()
    if not folder.is_dir() or not folder.is_relative_to(root):
        return jsonify({"error": "La subida no existe o ya fue eliminada."}), 404
    try:
        shutil.rmtree(folder)
    except OSError as exc:
        return jsonify({"error": f"No se pudo eliminar la subida: {exc}"}), 500
    return jsonify({"deleted": True, "upload_id": upload_id})


# --------------------------------- ETL ------------------------------------


@app.post("/api/etl/run")
def run_etl_endpoint():
    payload = _json_body()
    try:
        selected = _resolve_run_files(payload)
        options = {
            "include_nrt": _as_bool(payload.get("include_nrt"), True),
            "exclude_current_year": _as_bool(payload.get("exclude_current_year"), True),
            "replace": _as_bool(payload.get("replace"), True),
            "push": _as_bool(payload.get("push"), True),
        }
        if not turso_enabled():
            options["push"] = False
        job = job_manager.start_etl(selected, options)
        return jsonify({"job": job}), 202
    except JobBusy as exc:
        return jsonify({"error": str(exc)}), 409
    except (JobError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400


@app.post("/api/etl/sync")
def sync_endpoint():
    if not turso_enabled():
        return (
            jsonify(
                {
                    "error": "Turso está desactivado (TURSO_ENABLED=false). "
                    "Cambia la opción a true en .env para sincronizar.",
                    "mode": "local",
                }
            ),
            409,
        )
    payload = _json_body()
    try:
        job = job_manager.start_sync(_as_bool(payload.get("replace"), True))
        return jsonify({"job": job}), 202
    except JobBusy as exc:
        return jsonify({"error": str(exc)}), 409
    except JobError as exc:
        return jsonify({"error": str(exc)}), 400


@app.get("/api/etl/status")
def etl_status():
    job_id = request.args.get("job_id") or None
    return jsonify({"job": job_manager.snapshot(job_id)})


@app.get("/api/etl/runs")
def etl_runs():
    return jsonify({"jobs": job_manager.list_jobs()})


@app.get("/api/staging")
def staging():
    return jsonify(staging_info())


# ------------------------------- Consultas --------------------------------


@app.get("/api/stats")
def stats_endpoint():
    force = request.args.get("force") in {"1", "true", "yes"}
    try:
        return jsonify(db_stats(force=force))
    except DatabaseError as exc:
        return (
            jsonify(
                {
                    "error": "No se pudieron consultar los datos.",
                    "detail": str(exc),
                    "hint": "Revisa el staging local (TURSO_ENABLED=false) o la conexión con Turso.",
                }
            ),
            503,
        )


@app.get("/api/map")
def map_endpoint():
    try:
        limit = int(request.args.get("limit", 2500))
        days = int(request.args.get("days", 90))
    except ValueError:
        return jsonify({"error": "Parámetros numéricos no válidos."}), 400
    try:
        return jsonify(map_points(limit=limit, days=days))
    except DatabaseError as exc:
        return jsonify({"error": "No se pudieron consultar los datos.", "detail": str(exc)}), 503


@app.get("/api/cells")
def cells_endpoint():
    args = request.args
    try:
        result = list_cells(
            status=args.get("status") or None,
            date_from=args.get("date_from") or None,
            date_to=args.get("date_to") or None,
            lat_min=float(args["lat_min"]) if "lat_min" in args else None,
            lon_min=float(args["lon_min"]) if "lon_min" in args else None,
            lat_max=float(args["lat_max"]) if "lat_max" in args else None,
            lon_max=float(args["lon_max"]) if "lon_max" in args else None,
            limit=int(args.get("limit", 500)),
            offset=int(args.get("offset", 0)),
            order=args.get("order", "date_desc"),
        )
        return jsonify(result)
    except (ValueError, TypeError) as exc:
        return jsonify({"error": f"Filtros no válidos: {exc}"}), 400
    except DatabaseError as exc:
        return jsonify({"error": "No se pudieron consultar los datos.", "detail": str(exc)}), 503


@app.get("/api/mask")
def mask_endpoint():
    try:
        limit = int(request.args.get("limit", 500))
    except ValueError:
        return jsonify({"error": "Límite no válido."}), 400
    try:
        return jsonify(list_mask_sources(limit=limit))
    except DatabaseError as exc:
        return jsonify({"error": "No se pudieron consultar los datos.", "detail": str(exc)}), 503


# -------------------------------- Errores ---------------------------------


@app.errorhandler(DatabaseError)
def database_error(error):
    return (
        jsonify(
            {
                "error": "No se pudieron consultar los datos.",
                "detail": str(error),
            }
        ),
        503,
    )


@app.errorhandler(413)
def payload_too_large(_error):
    return (
        jsonify(
            {
                "error": "La subida supera el límite permitido por el servidor.",
                "hint": "Render también limita el tamaño de la petición. Usa el CLI del ETL o divide el CSV en partes más pequeñas.",
            }
        ),
        413,
    )


@app.errorhandler(404)
def not_found(error):
    if request.path.startswith("/api/"):
        return jsonify({"error": "Ruta no encontrada."}), 404
    return error


@app.errorhandler(Exception)
def unhandled(error):
    if isinstance(error, HTTPException):
        return error
    app.logger.exception("Error no controlado")
    if request.path.startswith("/api/"):
        return (
            jsonify(
                {
                    "error": "Error interno del servidor.",
                    "detail": str(error),
                }
            ),
            500,
        )
    return "Error interno del servidor.", 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, threaded=True)
