#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MOVIRIS · punto de entrada del programa
=======================================

Arranca el backend Flask que sirve el componente ETL y la API de Turso.

    python run.py
    python run.py --port 8080 --open

El proceso ETL también se puede ejecutar por separado:

    python etl/etl.py --source hackathon
    python etl/etl.py --push-only
"""

from __future__ import annotations

import argparse
import sys
import threading
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _configure_console() -> None:
    if sys.platform != "win32":
        return
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, OSError):
            pass


def main() -> int:
    parser = argparse.ArgumentParser(
        description="MOVIRIS · ETL de focos de calor (NASA FIRMS + Turso)"
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host del servidor (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=5000, help="Puerto (default: 5000)")
    parser.add_argument("--debug", action="store_true", help="Activar modo debug de Flask")
    parser.add_argument("--reload", action="store_true", help="Recargar al cambiar el código")
    parser.add_argument("--open", action="store_true", help="Abrir el navegador al arrancar")
    args = parser.parse_args()

    _configure_console()

    try:
        from backend.app import app
    except ModuleNotFoundError as exc:
        missing = exc.name or "una dependencia"
        print(f"No se pudo importar {missing}.", file=sys.stderr)
        print("Instala las dependencias con: pip install -r requirements.txt", file=sys.stderr)
        return 1

    from etl.etl import EtlError, load_env, turso_config, turso_enabled

    env = load_env()
    if not (ROOT / ".env").exists():
        print(
            "Aviso: no existe .env. Copia .env.example y configura Turso.",
            file=sys.stderr,
        )
    if turso_enabled(env):
        try:
            url, _token = turso_config(env)
            host = url.split("//", 1)[-1].split("/", 1)[0]
            print(f"Turso: {host}")
        except EtlError as exc:
            print(f"Turso: sin configurar ({exc})", file=sys.stderr)
    else:
        print("Turso: desactivado (modo local)")

    url = f"http://{args.host}:{args.port}"
    print("")
    print("  MOVIRIS · Bienvenida")
    print(f"  Bienvenida: {url}/")
    print(f"  ETL:        {url}/etl/")
    print(f"  API:        {url}/api/health")
    print("  Ctrl+C para detener")
    print("")

    if args.open:
        threading.Timer(1.2, lambda: webbrowser.open(url)).start()

    try:
        app.run(
            host=args.host,
            port=args.port,
            debug=args.debug,
            use_reloader=args.reload,
            threaded=True,
        )
    except OSError as exc:
        print(f"No se pudo iniciar el servidor en {url}: {exc}", file=sys.stderr)
        print("Prueba con otro puerto: python run.py --port 8080", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
