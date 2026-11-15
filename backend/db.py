# -*- coding: utf-8 -*-
"""
Acceso de datos del panel MOVIRIS.

Con `TURSO_ENABLED=false` todas las lecturas se hacen contra el staging SQLite
local (`data/moviris_staging.db`). Con `TURSO_ENABLED=true` se consulta Turso.
El token nunca sale del servidor.
"""

from __future__ import annotations

import datetime as dt
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence

import libsql_client

from backend.settings import turso_enabled
from etl.etl import DEFAULT_STAGING, load_env, turso_config

STATUS_VALUES = ("normal", "critical", "unusual")
REQUIRED_TABLES = {"fire_cells_daily", "fire_baseline", "non_vegetation_mask"}
STATS_TTL_SECONDS = 12.0

_stats_lock = threading.Lock()
_stats_cache: dict[str, Any] = {"at": 0.0, "value": None, "mode": None}


class DatabaseError(RuntimeError):
    """Error de conexión o de consulta contra Turso o el staging local."""


class TursoCursor:
    """Adapta un ResultSet de libSQL a la interfaz mínima de un cursor sqlite3."""

    def __init__(self, result):
        self._rows = list(result.rows)
        self._index = 0
        self.columns = list(result.columns or [])

    def fetchone(self):
        if self._index >= len(self._rows):
            return None
        row = self._rows[self._index]
        self._index += 1
        return row

    def fetchall(self):
        rows = self._rows[self._index:]
        self._index = len(self._rows)
        return rows

    def fetchmany(self, size=1):
        rows = self._rows[self._index:self._index + size]
        self._index += len(rows)
        return rows

    def __iter__(self):
        return iter(self.fetchall())


class TursoConnection:
    """Conexión de lectura a Turso con la misma interfaz que sqlite3.Connection."""

    def __init__(self):
        try:
            url, token = turso_config(load_env())
            self._client = libsql_client.create_client_sync(url, auth_token=token)
        except Exception as exc:
            raise DatabaseError(f"Turso: {exc}") from exc

    def execute(self, sql, args=()):
        try:
            result = self._client.execute(sql, tuple(args))
        except Exception as exc:
            raise DatabaseError(f"Turso: {exc}") from exc
        return TursoCursor(result)

    def close(self):
        try:
            self._client.close()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Fuentes de datos
# ---------------------------------------------------------------------------


@contextmanager
def _turso_connection() -> Iterator[Any]:
    try:
        url, token = turso_config(load_env())
    except Exception as exc:
        raise DatabaseError(str(exc)) from exc
    client = libsql_client.create_client_sync(url, auth_token=token)
    try:
        yield client
    finally:
        client.close()


def _turso_rows(client: Any, sql: str, args: Sequence[Any] = ()) -> list[dict[str, Any]]:
    result = client.execute(sql, tuple(args))
    columns = list(result.columns or [])
    return [dict(zip(columns, row)) for row in result.rows]


@contextmanager
def _local_connection() -> Iterator[sqlite3.Connection]:
    path = Path(DEFAULT_STAGING)
    if not path.exists():
        raise DatabaseError(
            "No existe el staging local. Ejecuta primero el ETL para generarlo."
        )
    try:
        connection = sqlite3.connect(str(path))
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        raise DatabaseError(f"Staging local: {exc}") from exc
    try:
        yield connection
    finally:
        connection.close()


@contextmanager
def _data_source() -> Iterator[Any]:
    """Devuelve una función fetch(sql, args) según el modo activo."""
    if not turso_enabled():
        with _local_connection() as connection:
            def fetch_local(sql: str, args: Sequence[Any] = ()) -> list[dict[str, Any]]:
                try:
                    cursor = connection.execute(sql, tuple(args))
                    return [dict(row) for row in cursor.fetchall()]
                except sqlite3.Error as exc:
                    raise DatabaseError(f"Staging local: {exc}") from exc

            yield fetch_local
        return

    with _turso_connection() as client:
        def fetch_turso(sql: str, args: Sequence[Any] = ()) -> list[dict[str, Any]]:
            try:
                return _turso_rows(client, sql, args)
            except Exception as exc:
                raise DatabaseError(f"Turso: {exc}") from exc

        yield fetch_turso


def query(sql: str, args: Sequence[Any] = ()) -> list[dict[str, Any]]:
    with _data_source() as fetch:
        return fetch(sql, args)


def query_one(sql: str, args: Sequence[Any] = ()) -> dict[str, Any]:
    rows = query(sql, args)
    return rows[0] if rows else {}


# ---------------------------------------------------------------------------
# Salud
# ---------------------------------------------------------------------------


def health() -> dict[str, Any]:
    """Comprueba el modo activo y la fuente que se está usando."""
    started = time.perf_counter()
    if not turso_enabled():
        path = Path(DEFAULT_STAGING)
        latency = lambda: round((time.perf_counter() - started) * 1000, 1)
        if not path.exists():
            return {
                "ok": False,
                "mode": "local",
                "storage": "staging",
                "path": str(path),
                "error": "No existe el staging local. Ejecuta el ETL para generarlo.",
                "tables": [],
                "missing": sorted(REQUIRED_TABLES),
                "latency_ms": latency(),
            }
        try:
            with _local_connection() as connection:
                tables = {
                    row["name"]
                    for row in connection.execute(
                        "SELECT name FROM sqlite_master "
                        "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                }
            missing = sorted(REQUIRED_TABLES - tables)
            return {
                "ok": not missing,
                "mode": "local",
                "storage": "staging",
                "path": str(path),
                "tables": sorted(tables),
                "missing": missing,
                "latency_ms": latency(),
            }
        except DatabaseError as exc:
            return {
                "ok": False,
                "mode": "local",
                "storage": "staging",
                "path": str(path),
                "error": str(exc),
                "tables": [],
                "missing": sorted(REQUIRED_TABLES),
                "latency_ms": latency(),
            }

    try:
        url, _token = turso_config(load_env())
        host = url.split("//", 1)[-1].split("/", 1)[0]
        with _turso_connection() as client:
            tables_result = client.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
            tables = {row[0] for row in tables_result.rows}
            client.execute("SELECT 1")
        missing = sorted(REQUIRED_TABLES - tables)
        return {
            "ok": not missing,
            "mode": "turso",
            "storage": "turso",
            "host": host,
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "tables": sorted(tables),
            "missing": missing,
        }
    except Exception as exc:
        return {
            "ok": False,
            "mode": "turso",
            "storage": "turso",
            "error": str(exc),
            "latency_ms": round((time.perf_counter() - started) * 1000, 1),
            "missing": [],
        }


# ---------------------------------------------------------------------------
# Estadísticas
# ---------------------------------------------------------------------------


def _load_stats() -> dict[str, Any]:
    with _data_source() as fetch:
        summary = fetch(
            """
            SELECT
                COUNT(*)                                   AS daily_rows,
                COALESCE(SUM(detections), 0)               AS detections,
                COALESCE(SUM(is_nrt), 0)                   AS nrt_rows,
                MIN(acq_date)                              AS date_from,
                MAX(acq_date)                              AS date_to,
                (SELECT COUNT(*) FROM fire_baseline)       AS baseline_rows,
                (SELECT COUNT(*) FROM non_vegetation_mask) AS mask_rows,
                (SELECT COUNT(*) FROM (
                    SELECT 1 FROM fire_cells_daily GROUP BY cell_lat, cell_lon
                ))                                         AS cells
            FROM fire_cells_daily
            """
        )[0]
        status_rows = fetch(
            "SELECT status, COUNT(*) AS n FROM fire_cells_daily GROUP BY status"
        )
        mask_rows = fetch(
            """
            SELECT source_type, COUNT(*) AS n, COALESCE(SUM(hits), 0) AS hits
            FROM non_vegetation_mask GROUP BY source_type
            """
        )
        recent = fetch(
            """
            SELECT cell_lat, cell_lon, acq_date, detections, frp_max,
                   z_score, sensors, confidence_max, is_nrt
            FROM fire_cells_daily
            WHERE status = 'critical'
            ORDER BY acq_date DESC, detections DESC
            LIMIT 8
            """
        )

    status = {"critical": 0, "unusual": 0, "normal": 0, "unknown": 0}
    for row in status_rows:
        key = row.get("status") or "unknown"
        status[key] = int(row.get("n") or 0)
    mask = {"volcano": 0, "fixed": 0, "sea": 0}
    mask_hits = {"volcano": 0, "fixed": 0, "sea": 0}
    type_names = {1: "volcano", 2: "fixed", 3: "sea"}
    for row in mask_rows:
        name = type_names.get(int(row.get("source_type") or 0))
        if name is None:
            continue
        mask[name] = int(row.get("n") or 0)
        mask_hits[name] = int(row.get("hits") or 0)

    return {
        "counts": {
            "daily_rows": int(summary.get("daily_rows") or 0),
            "detections": int(summary.get("detections") or 0),
            "cells": int(summary.get("cells") or 0),
            "baseline_rows": int(summary.get("baseline_rows") or 0),
            "mask_rows": int(summary.get("mask_rows") or 0),
            "nrt_rows": int(summary.get("nrt_rows") or 0),
        },
        "range": {
            "from": summary.get("date_from"),
            "to": summary.get("date_to"),
        },
        "status": status,
        "mask": {"rows": mask, "hits": mask_hits},
        "recent_critical": recent,
        "mode": "turso" if turso_enabled() else "local",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }


def stats(force: bool = False) -> dict[str, Any]:
    current_mode = "turso" if turso_enabled() else "local"
    now = time.monotonic()
    with _stats_lock:
        if (
            not force
            and _stats_cache["value"] is not None
            and _stats_cache.get("mode") == current_mode
            and now - float(_stats_cache["at"]) < STATS_TTL_SECONDS
        ):
            return _stats_cache["value"]
    try:
        value = _load_stats()
    except DatabaseError:
        raise
    except Exception as exc:
        raise DatabaseError(f"Datos: {exc}") from exc
    with _stats_lock:
        _stats_cache["at"] = now
        _stats_cache["value"] = value
        _stats_cache["mode"] = current_mode
    return value


# ---------------------------------------------------------------------------
# Consultas del panel
# ---------------------------------------------------------------------------


def map_points(limit: int = 2500, days: int = 90) -> dict[str, Any]:
    limit = max(50, min(int(limit), 5000))
    days = max(1, min(int(days), 365))
    latest_row = query_one("SELECT MAX(acq_date) AS latest FROM fire_cells_daily")
    latest = latest_row.get("latest")
    if not latest:
        return {"points": [], "latest": None, "from": None, "to": None, "count": 0}
    try:
        first = dt.date.fromisoformat(str(latest)) - dt.timedelta(days=days)
    except ValueError:
        first = dt.date.today() - dt.timedelta(days=days)
    rows = query(
        """
        SELECT cell_lat AS lat, cell_lon AS lon, acq_date AS date,
               detections AS det, frp_max AS frp, status, z_score AS z,
               is_nrt
        FROM fire_cells_daily
        WHERE status IN ('critical', 'unusual') AND acq_date >= ?
        ORDER BY detections DESC
        LIMIT ?
        """,
        (first.isoformat(), limit),
    )
    return {
        "points": rows,
        "latest": latest,
        "from": first.isoformat(),
        "to": latest,
        "count": len(rows),
    }


def list_cells(
    *,
    status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    lat_min: float | None = None,
    lon_min: float | None = None,
    lat_max: float | None = None,
    lon_max: float | None = None,
    limit: int = 500,
    offset: int = 0,
    order: str = "date_desc",
) -> dict[str, Any]:
    where: list[str] = []
    args: list[Any] = []
    if status:
        if status not in STATUS_VALUES:
            raise ValueError("Estado no válido.")
        where.append("status = ?")
        args.append(status)
    for value, column, operator in (
        (date_from, "acq_date", ">="),
        (date_to, "acq_date", "<="),
    ):
        if value:
            dt.date.fromisoformat(value)
            where.append(f"{column} {operator} ?")
            args.append(value)
    for value, column, operator in (
        (lat_min, "cell_lat", ">="),
        (lat_max, "cell_lat", "<="),
        (lon_min, "cell_lon", ">="),
        (lon_max, "cell_lon", "<="),
    ):
        if value is not None:
            where.append(f"{column} {operator} ?")
            args.append(float(value))
    orders = {
        "date_desc": "acq_date DESC, detections DESC",
        "date_asc": "acq_date ASC, detections DESC",
        "det_desc": "detections DESC, acq_date DESC",
        "z_desc": "z_score DESC, detections DESC",
    }
    order_sql = orders.get(order, orders["date_desc"])
    limit = max(1, min(int(limit), 5000))
    offset = max(0, int(offset))
    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    rows = query(
        f"""
        SELECT cell_lat, cell_lon, acq_date, year, month, week_of_year,
               detections, frp_max, frp_sum_norm, confidence_max, sensors,
               is_nrt, status, z_score
        FROM fire_cells_daily
        {where_sql}
        ORDER BY {order_sql}
        LIMIT ? OFFSET ?
        """,
        (*args, limit, offset),
    )
    return {"cells": rows, "count": len(rows), "limit": limit, "offset": offset}


def list_mask_sources(limit: int = 500) -> dict[str, Any]:
    limit = max(1, min(int(limit), 2000))
    rows = query(
        """
        SELECT cell_lat AS lat, cell_lon AS lon, source_type AS type, hits
        FROM non_vegetation_mask
        ORDER BY hits DESC
        LIMIT ?
        """,
        (limit,),
    )
    return {"sources": rows, "count": len(rows)}


def top_cells_by_status(status: str = "critical", limit: int = 50) -> list[dict[str, Any]]:
    if status not in STATUS_VALUES:
        raise ValueError("Estado no válido.")
    return query(
        """
        SELECT cell_lat, cell_lon, acq_date, detections, frp_max, z_score,
               sensors, is_nrt
        FROM fire_cells_daily
        WHERE status = ?
        ORDER BY acq_date DESC, detections DESC
        LIMIT ?
        """,
        (status, max(1, min(int(limit), 500))),
    )
