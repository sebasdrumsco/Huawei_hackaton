"""Repositorio de asientos en memoria, thread-safe.

Usa threading.RLock para garantizar que las operaciones de
reserva sean atómicas frente a solicitudes concurrentes.

El lock es reentrante (RLock) para que el caso de uso pueda
adquirirlo y las operaciones internas del repositorio también
funcionen si se llaman dentro del contexto protegido.
"""
from __future__ import annotations

import threading
from typing import Optional

from ..application.ports.seat_repository import SeatRepository
from ..domain.models import Seat


class InMemorySeatRepository(SeatRepository):
    """Repositorio de asientos en memoria con lock reentrante.

    El lock protege el diccionario interno _seats para que
    ninguna operación de lectura/escritura ocurra simultáneamente
    desde múltiples hilos.
    """

    def __init__(self, seats: Optional[list[Seat]] = None):
        self._seats: dict[str, Seat] = {}
        self._lock = threading.RLock()
        if seats:
            for seat in seats:
                self._seats[seat.seat_id] = seat

    def get(self, seat_id: str) -> Optional[Seat]:
        with self._lock:
            return self._seats.get(seat_id)

    def get_many(self, seat_ids: list[str]) -> list[Seat]:
        with self._lock:
            result = []
            for sid in seat_ids:
                seat = self._seats.get(sid)
                if seat is not None:
                    result.append(seat)
            return result

    def save(self, seat: Seat) -> None:
        with self._lock:
            self._seats[seat.seat_id] = seat

    def save_many(self, seats: list[Seat]) -> None:
        with self._lock:
            for seat in seats:
                self._seats[seat.seat_id] = seat

    def list_all(self) -> list[Seat]:
        with self._lock:
            return list(self._seats.values())

    def list_available(self) -> list[Seat]:
        with self._lock:
            return [
                s for s in self._seats.values() if s.is_available()
            ]

    def lock(self) -> None:
        """Adquiere el lock global para operaciones atómicas."""
        self._lock.acquire()

    def unlock(self) -> None:
        """Libera el lock global."""
        self._lock.release()
