"""Repositorio de holds en memoria, thread-safe."""
from __future__ import annotations

import threading
from typing import Optional

from ..application.ports.hold_repository import HoldRepository
from ..domain.models import Hold


class InMemoryHoldRepository(HoldRepository):
    """Repositorio de holds en memoria."""

    def __init__(self):
        self._holds: dict[str, Hold] = {}
        self._lock = threading.Lock()

    def get(self, hold_id: str) -> Optional[Hold]:
        with self._lock:
            return self._holds.get(hold_id)

    def save(self, hold: Hold) -> None:
        with self._lock:
            self._holds[hold.hold_id] = hold

    def find_active_by_user(self, user_id: str) -> list[Hold]:
        with self._lock:
            return [
                h for h in self._holds.values()
                if h.user_id == user_id and h.is_active()
            ]

    def list_all(self) -> list[Hold]:
        with self._lock:
            return list(self._holds.values())

    def list_active(self) -> list[Hold]:
        with self._lock:
            return [h for h in self._holds.values() if h.is_active()]
