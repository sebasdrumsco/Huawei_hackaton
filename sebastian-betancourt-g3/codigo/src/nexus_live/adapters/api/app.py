"""Aplicación FastAPI para NEXUS LIVE.

Punto de entrada del adaptador API REST. Configura la app,
monta las rutas y sirve la interfaz web estática.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .composition import Container, build_container
from .routes import create_router


def create_app(
    container: Optional[Container] = None,
    max_seats_per_user: int = 6,
    ttl_seconds: int = 120,
) -> FastAPI:
    """Crea la aplicación FastAPI.

    Args:
        container: Contenedor de dependencias (se crea uno nuevo si es None).
        max_seats_per_user: Límite de asientos por usuario.
        ttl_seconds: TTL de los holds.

    Returns:
        Aplicación FastAPI configurada.
    """
    if container is None:
        container = build_container(
            max_seats_per_user=max_seats_per_user,
            ttl_seconds=ttl_seconds,
        )

    app = FastAPI(
        title="NEXUS LIVE // T-80",
        description="Motor de reservas de alta concurrencia",
        version="1.0.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.state.container = container

    router = create_router(container)
    app.include_router(router)

    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    @app.get("/", response_class=HTMLResponse)
    async def index():
        """Sirve la interfaz web de control."""
        html_path = static_dir / "index.html"
        if html_path.exists():
            return HTMLResponse(html_path.read_text(encoding="utf-8"))
        return HTMLResponse("<h1>NEXUS LIVE API</h1><p>Static files not found.</p>")

    return app
