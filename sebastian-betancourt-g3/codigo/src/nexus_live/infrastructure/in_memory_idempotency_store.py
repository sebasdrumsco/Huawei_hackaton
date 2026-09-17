"""Almacén de idempotencia en memoria, thread-safe."""
from __future__ import annotations

import threading
from typing import Optional

from ..application.ports.idempotency_store import IdempotencyStore


class InMemoryIdempotencyStore(IdempotencyStore):
    """Almacén de idempotencia en memoria.

    Mantiene un mapeo clave -> (payload_hash, resultado).
    Thread-safe con un lock simple.
    """

    def __init__(self):
        self._store: dict[str, tuple[str, dict]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[dict]:
        with self._lock:
            entry = self._store.get(key)
            return entry[1] if entry else None

    def get_payload_hash(self, key: str) -> Optional[str]:
        with self._lock:
            entry = self._store.get(key)
            return entry[0] if entry else None

    def save(self, key: str, payload_hash: str, result: dict) -> None:
        with self._lock:
            self._store[key] = (payload_hash, result)
