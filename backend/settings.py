# -*- coding: utf-8 -*-
"""
Interruptor único de Turso.

`TURSO_ENABLED` en `.env` controla todo:

    TURSO_ENABLED=false   -> modo local (staging SQLite, sin tocar Turso)
    TURSO_ENABLED=true    -> modo Turso (lecturas y escrituras cuando se pida)

No hay estado persistido aparte ni botón en la interfaz. Cambiar el valor en
`.env` es suficiente; `load_env()` se lee en cada comprobación.
"""

from __future__ import annotations

from etl.etl import load_env

_FALSE_VALUES = {"0", "false", "no", "off", "disabled", "local"}


def turso_enabled(env: dict[str, str] | None = None) -> bool:
    values = env if env is not None else load_env()
    raw = str(values.get("TURSO_ENABLED", "true")).strip().lower()
    return raw not in _FALSE_VALUES


def mode(env: dict[str, str] | None = None) -> str:
    return "turso" if turso_enabled(env) else "local"
