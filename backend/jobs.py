# -*- coding: utf-8 -*-
"""
Gestor de trabajos ETL en memoria.

El ETL puede tardar varios minutos (sobre todo la sincronización con Turso), así
que se ejecuta en un hilo y la UI consulta el estado por polling. Solo se
permite un trabajo activo a la vez para no competir por las tablas.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import threading
import time
import traceback
import uuid
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence

from etl.etl import DEFAULT_STAGING, EtlError, load_env, push_staging, run_etl
from backend.settings import turso_enabled

MAX_LOGS = 500
MAX_JOBS = 20


class JobError(RuntimeError):
    """Error controlado al crear o ejecutar un trabajo."""


class JobBusy(JobError):
    """Ya existe un trabajo en ejecución."""


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _clock() -> str:
    return dt.datetime.now().strftime("%H:%M:%S")


class JobManager:
    def __init__(self, staging_path: str | Path = DEFAULT_STAGING) -> None:
        self.staging_path = Path(staging_path)
        self._lock = threading.Lock()
        self._jobs: "OrderedDict[str, dict[str, Any]]" = OrderedDict()
        self._current: str | None = None

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def start_etl(self, files: Sequence[str | Path], options: dict[str, Any]) -> dict:
        files = [str(Path(path)) for path in files]
        if not files:
            raise JobError("Selecciona al menos un archivo CSV.")
        options = dict(options)
        if not turso_enabled():
            options["push"] = False
        with self._lock:
            self._assert_idle()
            job_id = uuid.uuid4().hex[:10]
            job = self._build_job(job_id, "etl", files, options)
            self._jobs[job_id] = job
            self._current = job_id
            self._trim()
        thread = threading.Thread(
            target=self._run_etl,
            args=(job_id, files, options),
            daemon=True,
            name=f"moviris-etl-{job_id}",
        )
        thread.start()
        return self.snapshot(job_id)

    def start_sync(self, replace: bool = True) -> dict:
        if not turso_enabled():
            raise JobError(
                "Turso está desactivado (TURSO_ENABLED=false). "
                "Cambia la opción a true en .env para sincronizar."
            )
        if not self.staging_ready():
            raise JobError(
                "No hay un staging local con datos. Ejecuta primero el ETL completo."
            )
        with self._lock:
            self._assert_idle()
            job_id = uuid.uuid4().hex[:10]
            job = self._build_job(job_id, "sync", [], {"replace": replace})
            job["stage"] = "Preparando sincronización"
            job["message"] = "Reintentando la subida del staging a Turso."
            self._jobs[job_id] = job
            self._current = job_id
            self._trim()
        thread = threading.Thread(
            target=self._run_sync,
            args=(job_id, replace),
            daemon=True,
            name=f"moviris-sync-{job_id}",
        )
        thread.start()
        return self.snapshot(job_id)

    def snapshot(self, job_id: str | None = None) -> dict | None:
        with self._lock:
            if job_id is None:
                job_id = self._current
                if job_id is None and self._jobs:
                    job_id = next(reversed(self._jobs))
            job = self._jobs.get(job_id) if job_id else None
            if job is None:
                return None
            data = {key: value for key, value in job.items() if not key.startswith("_")}
            data["logs"] = list(job["logs"])
            data["metrics"] = dict(job["metrics"])
            data["options"] = dict(job["options"])
            data["summary"] = dict(job["summary"]) if job["summary"] else None
            if job["status"] == "running":
                data["elapsed_seconds"] = round(time.time() - job["_started_ts"], 1)
            return data

    def list_jobs(self, limit: int = 8) -> list[dict]:
        with self._lock:
            jobs = list(self._jobs.values())[-limit:]
            result = []
            for job in reversed(jobs):
                result.append(
                    {
                        "id": job["id"],
                        "kind": job["kind"],
                        "status": job["status"],
                        "stage": job["stage"],
                        "percent": job["percent"],
                        "created_at": job["created_at"],
                        "finished_at": job["finished_at"],
                        "elapsed_seconds": job["elapsed_seconds"],
                        "error": job["error"],
                    }
                )
            return result

    def is_busy(self) -> bool:
        with self._lock:
            return bool(self._current)

    def staging_ready(self) -> bool:
        if not self.staging_path.exists():
            return False
        try:
            connection = sqlite3.connect(str(self.staging_path))
            try:
                count = connection.execute(
                    "SELECT COUNT(*) FROM fire_cells_daily"
                ).fetchone()[0]
            finally:
                connection.close()
            return count > 0
        except sqlite3.Error:
            return False

    # ------------------------------------------------------------------
    # Internos
    # ------------------------------------------------------------------

    def _assert_idle(self) -> None:
        if self._current:
            current = self._jobs.get(self._current)
            if current and current["status"] == "running":
                raise JobBusy("Ya hay un proceso en ejecución. Espera a que termine.")

    def _build_job(
        self,
        job_id: str,
        kind: str,
        files: Sequence[str],
        options: dict[str, Any],
    ) -> dict[str, Any]:
        now = _now_iso()
        return {
            "id": job_id,
            "kind": kind,
            "status": "running",
            "stage": "Iniciando",
            "percent": 0.0,
            "message": "Preparando el proceso...",
            "created_at": now,
            "started_at": now,
            "finished_at": None,
            "elapsed_seconds": 0.0,
            "files": [Path(path).name for path in files],
            "file_count": len(files),
            "options": dict(options),
            "logs": [],
            "metrics": {},
            "summary": None,
            "error": None,
            "can_sync": False,
            "_started_ts": time.time(),
        }

    def _trim(self) -> None:
        while len(self._jobs) > MAX_JOBS:
            oldest = next(iter(self._jobs))
            if oldest == self._current:
                break
            self._jobs.pop(oldest, None)

    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job.update(fields)

    def _log(self, job_id: str, message: str, level: str = "info") -> None:
        text = str(message)
        prefix = {"error": "ERROR", "warn": "AVISO"}.get(level, "")
        line = f"[{_clock()}] {prefix + ' ' if prefix else ''}{text}"
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["logs"].append(line[:4000])
            if len(job["logs"]) > MAX_LOGS:
                del job["logs"][: len(job["logs"]) - MAX_LOGS]

    def _progress(self, job_id: str, payload: dict[str, Any]) -> None:
        stage = str(payload.get("stage") or "")
        message = str(payload.get("message") or "")
        percent = float(payload.get("percent") or 0.0)
        changed_stage = False
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            changed_stage = bool(stage and stage != job["stage"])
            if stage:
                job["stage"] = stage
            if message:
                job["message"] = message
            job["percent"] = max(0.0, min(100.0, percent))
            for key in ("total_rows", "pushed"):
                if key in payload:
                    job["metrics"][key] = payload[key]
            if payload.get("summary"):
                job["summary"] = dict(payload["summary"])
        if changed_stage:
            self._log(job_id, f"{stage} · {message}" if message else stage)

    def _finish(
        self,
        job_id: str,
        status: str,
        *,
        summary: dict | None = None,
        error: str | None = None,
        can_sync: bool = False,
    ) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return
            job["status"] = status
            job["finished_at"] = _now_iso()
            job["elapsed_seconds"] = round(time.time() - job["_started_ts"], 1)
            if status == "done":
                job["percent"] = 100.0
                job["stage"] = "Completado"
                job["message"] = "Proceso finalizado correctamente."
            if summary is not None:
                job["summary"] = dict(summary)
            if error is not None:
                job["error"] = error
                job["message"] = error
            job["can_sync"] = bool(can_sync)
            if self._current == job_id:
                self._current = None
        if status == "done":
            self._log(job_id, "Proceso finalizado correctamente.")
        else:
            self._log(job_id, error or "Proceso fallido.", level="error")

    def _run_etl(self, job_id: str, files: Sequence[str], options: dict[str, Any]) -> None:
        try:
            push = bool(options.get("push", True))
            if not push and not turso_enabled():
                self._log(
                    job_id,
                    "Modo local: Turso desactivado; el resultado queda en el staging local.",
                )
            summary = run_etl(
                files,
                include_nrt=bool(options.get("include_nrt", True)),
                exclude_current_year=bool(options.get("exclude_current_year", True)),
                replace=bool(options.get("replace", True)),
                push=push,
                staging_path=self.staging_path,
                progress=lambda payload: self._progress(job_id, payload),
                log=lambda message: self._log(job_id, message),
                env=load_env(),
            )
            self._finish(job_id, "done", summary=summary)
        except EtlError as exc:
            self._finish(
                job_id,
                "error",
                error=str(exc),
                can_sync=self.staging_ready(),
            )
        except Exception as exc:  # pragma: no cover
            self._log(job_id, traceback.format_exc(), level="error")
            self._finish(
                job_id,
                "error",
                error=f"{type(exc).__name__}: {exc}",
                can_sync=self.staging_ready(),
            )

    def _run_sync(self, job_id: str, replace: bool) -> None:
        try:
            if not turso_enabled():
                self._finish(
                    job_id,
                    "error",
                    error=(
                        "Turso está desactivado (TURSO_ENABLED=false). "
                        "Cambia la opción a true en .env para sincronizar."
                    ),
                    can_sync=False,
                )
                return
            result = push_staging(
                self.staging_path,
                replace=replace,
                progress=lambda payload: self._progress(job_id, payload),
                log=lambda message: self._log(job_id, message),
                env=load_env(),
            )
            summary = {
                "pushed": result["pushed"],
                "staging_rows": sum(result["counts"].values()),
                "staging_path": str(self.staging_path),
            }
            self._finish(job_id, "done", summary=summary)
        except EtlError as exc:
            self._finish(job_id, "error", error=str(exc), can_sync=True)
        except Exception as exc:  # pragma: no cover
            self._log(job_id, traceback.format_exc(), level="error")
            self._finish(
                job_id,
                "error",
                error=f"{type(exc).__name__}: {exc}",
                can_sync=True,
            )
