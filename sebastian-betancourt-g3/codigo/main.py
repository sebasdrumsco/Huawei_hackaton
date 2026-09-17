"""Punto de entrada de NEXUS LIVE.

Uso:
    python main.py                    # Servidor en http://localhost:8000
    python main.py --port 8080        # Puerto personalizado
    python main.py --ttl 30           # TTL de holds en segundos
    python main.py --max-seats 4      # Limite de asientos por usuario
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import uvicorn

from src.nexus_live.adapters.api.app import create_app
from src.nexus_live.adapters.api.composition import build_container


def main():
    parser = argparse.ArgumentParser(description="NEXUS LIVE - Motor de reservas")
    parser.add_argument("--host", default="0.0.0.0", help="Host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Puerto (default: 8000)")
    parser.add_argument("--ttl", type=int, default=120, help="TTL de holds en segundos")
    parser.add_argument("--max-seats", type=int, default=6, help="Limite de asientos por usuario")
    args = parser.parse_args()

    container = build_container(
        max_seats_per_user=args.max_seats,
        ttl_seconds=args.ttl,
    )
    app = create_app(container=container)

    print(f"""
    ╔══════════════════════════════════════════════════════════════╗
    ║                     NEXUS LIVE // T-80                      ║
    ╠══════════════════════════════════════════════════════════════╣
    ║ Servidor ........................................ {args.host}:{args.port:<6} ║
    ║ TTL de holds .................................... {args.ttl:>3} segundos ║
    ║ Max asientos por usuario .......................... {args.max_seats:>3}        ║
    ║ Interfaz web .................................. http://localhost:{args.port} ║
    ║ API docs ............................. http://localhost:{args.port}/docs ║
    ╚══════════════════════════════════════════════════════════════╝
    """)

    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
