"""Puerto del log de auditoría (trazabilidad)."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.models import Transition


class AuditLog(ABC):
    """Interfaz del log de auditoría para trazabilidad.

    Cada cambio de estado importante se registra para poder
    reconstruir la vida de una reserva.
    """

    @abstractmethod
    def record(self, transition: Transition) -> None:
        """Registra una transición de estado."""

    @abstractmethod
    def get_by_hold(self, hold_id: str) -> list[Transition]:
        """Obtiene todas las transiciones de un hold."""

    @abstractmethod
    def get_by_seat(self, seat_id: str) -> list[Transition]:
        """Obtiene todas las transiciones de un asiento."""

    @abstractmethod
    def list_all(self) -> list[Transition]:
        """Lista todas las transiciones registradas."""
