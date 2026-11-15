# -*- coding: utf-8 -*-
"""Endpoint Explain: una sola llamada a Groq por clic, sin historial."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict, deque

from flask import Blueprint, jsonify, request

from etl.etl import load_env

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MAX_BODY_CHARS = 14_000
MAX_REQUESTS_PER_MINUTE = 20
ALLOWED_CHARTS = {
    "years",
    "anomaly",
    "season",
    "index",
    "coverage",
    "calendar_matrix",
    "calendar_compare",
    "calendar_weeks",
}

bp = Blueprint("explain", __name__)

_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()


def _mensaje(lang: str, key: str) -> str:
    textos = {
        "en": {
            "not_configured": "Explain is not configured on the server.",
            "invalid": "The explanation request is not valid.",
            "rate": "Too many requests. Try again later.",
            "failed": "Could not generate an explanation. Please try again.",
        },
        "es": {
            "not_configured": "Explain no está configurado en el servidor.",
            "invalid": "La solicitud de explicación no es válida.",
            "rate": "Demasiadas solicitudes. Inténtalo más tarde.",
            "failed": "No se pudo generar la explicación. Inténtalo de nuevo.",
        },
    }
    return textos.get(lang, textos["en"])[key]


def _permitir(ip: str) -> bool:
    ahora = time.monotonic()
    with _hits_lock:
        cola = _hits[ip]
        while cola and ahora - cola[0] > 60:
            cola.popleft()
        if len(cola) >= MAX_REQUESTS_PER_MINUTE:
            return False
        cola.append(ahora)
        return True


def _system_prompt(lang: str) -> str:
    if lang == "es":
        return (
            "Eres el explicador de datos de MOVIRIS, una aplicación de focos de calor. "
            "Responde en español, en lenguaje sencillo y en un máximo aproximado de 100 palabras. "
            "Explica en este orden: qué muestra el gráfico, qué dicen los datos y qué significa. "
            "Usa únicamente los datos del mensaje del usuario. No inventes cifras ni contexto. "
            "Si los datos no alcanzan, dilo. No uses Markdown ni listas largas."
        )
    return (
        "You are the data explainer for MOVIRIS, a fire hotspot monitoring app. "
        "Answer in English, in plain language and in about 100 words maximum. "
        "Explain in this order: what the chart shows, what the data says, and what it means. "
        "Use only the data in the user message. Never invent numbers or context. "
        "If the data is insufficient, say so. Do not use Markdown or long lists."
    )


def _extraer_texto(respuesta: dict) -> str:
    choices = respuesta.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return str(message.get("content") or "").strip()


def _llamar_groq(token: str, model: str, lang: str, payload: dict) -> str:
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": _system_prompt(lang)},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
            },
        ],
        "temperature": 0.2,
        "max_tokens": 240,
    }
    solicitud = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(solicitud, timeout=25) as respuesta:
        datos = json.loads(respuesta.read().decode("utf-8"))
    return _extraer_texto(datos)


@bp.post("/api/explain")
def explain():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return jsonify({"error": _mensaje("en", "invalid"), "code": "invalid"}), 400

    lang = str(body.get("lang") or "en").lower()
    if lang not in {"en", "es"}:
        lang = "en"

    chart = str(body.get("chart") or "").strip()
    title = str(body.get("title") or "").strip()[:120]
    filtros = body.get("filters")
    datos = body.get("data")

    if chart not in ALLOWED_CHARTS or not isinstance(filtros, dict) or not isinstance(datos, (dict, list)):
        return jsonify({"error": _mensaje(lang, "invalid"), "code": "invalid"}), 400

    payload = {
        "chart": chart,
        "title": title,
        "filters": filtros,
        "data": datos,
        "language": lang,
    }
    serializado = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    if len(serializado) > MAX_BODY_CHARS:
        return jsonify({"error": _mensaje(lang, "invalid"), "code": "invalid"}), 413

    ip = request.remote_addr or "unknown"
    if not _permitir(ip):
        return jsonify({"error": _mensaje(lang, "rate"), "code": "rate_limited"}), 429

    env = load_env()
    token = str(env.get("GROQ_LLM_TOKEN") or os.environ.get("GROQ_LLM_TOKEN") or "").strip()
    model = str(env.get("GROQ_MODEL") or os.environ.get("GROQ_MODEL") or "").strip()
    if not token or not model:
        return jsonify({"error": _mensaje(lang, "not_configured"), "code": "not_configured"}), 503

    try:
        texto = _llamar_groq(token, model, lang, payload)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, KeyError) as exc:
        # No se registra el token ni el cuerpo de la petición.
        print(f"[explain] Groq error: {type(exc).__name__}: {exc}", flush=True)
        return jsonify({"error": _mensaje(lang, "failed"), "code": "failed"}), 502
    except Exception as exc:  # pragma: no cover
        print(f"[explain] error inesperado: {type(exc).__name__}: {exc}", flush=True)
        return jsonify({"error": _mensaje(lang, "failed"), "code": "failed"}), 502

    if not texto:
        return jsonify({"error": _mensaje(lang, "failed"), "code": "failed"}), 502

    return jsonify({"text": texto, "lang": lang})
