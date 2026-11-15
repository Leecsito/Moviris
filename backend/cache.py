# -*- coding: utf-8 -*-
"""Caché TTL en memoria para las consultas de lectura más costosas.

La app usa un solo worker de Gunicorn, así que una caché por proceso es
suficiente. Se limpia cuando termina un ETL/sync para que los datos nuevos se
vean de inmediato.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any

from flask import jsonify

from backend.settings import turso_enabled

_CACHES: list["TTLCache"] = []
_REGISTRY_LOCK = threading.Lock()


class TTLCache:
    """Cache LRU con vencimiento por tiempo y tamaño máximo."""

    def __init__(self, ttl: float = 300.0, maxsize: int = 32):
        self.ttl = float(ttl)
        self.maxsize = max(1, int(maxsize))
        self._items: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = threading.Lock()
        with _REGISTRY_LOCK:
            _CACHES.append(self)

    def get(self, key: Any) -> Any | None:
        ahora = time.time()
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            vence, valor = item
            if vence <= ahora:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return valor

    def set(self, key: Any, value: Any, ttl: float | None = None) -> None:
        vence = time.time() + (self.ttl if ttl is None else float(ttl))
        with self._lock:
            self._items[key] = (vence, value)
            self._items.move_to_end(key)
            while len(self._items) > self.maxsize:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)


def clear_all_caches() -> None:
    with _REGISTRY_LOCK:
        caches = list(_CACHES)
    for cache in caches:
        cache.clear()


def modo_datos() -> str:
    """Incluye el modo en la clave para no mezclar respuestas local/Turso."""
    try:
        return "turso" if turso_enabled() else "local"
    except Exception:
        return "desconocido"


def clave_params(*valores: Any) -> tuple:
    """Normaliza floats para que -5.01 y -5.010 compartan caché."""
    normalizados = []
    for valor in valores:
        if isinstance(valor, float):
            normalizados.append(round(valor, 4))
        else:
            normalizados.append(valor)
    return tuple(normalizados)


def respuesta_cache(payload: Any, *, hit: bool = False, max_age: int = 60):
    response = jsonify(payload)
    response.headers["Cache-Control"] = f"private, max-age={max_age}"
    response.headers["X-Cache"] = "HIT" if hit else "MISS"
    return response
