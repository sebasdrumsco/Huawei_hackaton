"""Log de auditoría en memoria, thread-safe."""
from __future__ import annotations

import threading

from ..application.ports.audit_log import AuditLog
from ..domain.models import Transition


class InMemoryAuditLog(AuditLog):
    """Log de auditoría en memoria.

    Registra todas las transiciones de estado para trazabilidad.
    """

    def __init__(self):
        self._transitions: list[Transition] = []
        self._lock = threading.Lock()

    def record(self, transition: Transition) -> None:
        with self._lock:
            self._transitions.append(transition)

    def get_by_hold(self, hold_id: str) -> list[Transition]:
        with self._lock:
            return [
                t for t in self._transitions if t.hold_id == hold_id
            ]

    def get_by_seat(self, seat_id: str) -> list[Transition]:
        with self._lock:
            return [
                t for t in self._transitions if t.seat_id == seat_id
            ]

    def list_all(self) -> list[Transition]:
        with self._lock:
            return list(self._transitions)
