"""Puerto del repositorio de asientos.

Define las operaciones que el dominio necesita para persistir y
recuperar asientos. La implementación concreta (en memoria, SQL, etc.)
vive en la capa de infraestructura.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ...domain.models import Seat


class SeatRepository(ABC):
    """Interfaz del repositorio de asientos.

    Todas las operaciones son thread-safe en las implementaciones
    concretas para garantizar concurrencia segura.
    """

    @abstractmethod
    def get(self, seat_id: str) -> Optional[Seat]:
        """Obtiene un asiento por ID. Retorna None si no existe."""

    @abstractmethod
    def get_many(self, seat_ids: list[str]) -> list[Seat]:
        """Obtiene múltiples asientos por ID."""

    @abstractmethod
    def save(self, seat: Seat) -> None:
        """Persiste un asiento."""

    @abstractmethod
    def save_many(self, seats: list[Seat]) -> None:
        """Persiste múltiples asientos atómicamente."""

    @abstractmethod
    def list_all(self) -> list[Seat]:
        """Lista todos los asientos."""

    @abstractmethod
    def list_available(self) -> list[Seat]:
        """Lista solo los asientos disponibles."""

    @abstractmethod
    def lock(self) -> None:
        """Adquiere el lock global del repositorio."""

    @abstractmethod
    def unlock(self) -> None:
        """Libera el lock global del repositorio."""
