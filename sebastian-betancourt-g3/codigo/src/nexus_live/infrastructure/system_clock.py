"""Reloj del sistema (implementación real del puerto Clock)."""
from __future__ import annotations

from datetime import datetime, timezone

from ..application.ports.clock import Clock


class SystemClock(Clock):
    """Reloj que retorna la hora real del sistema."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)
