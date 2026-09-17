"""Puerto del repositorio de reservas (HOLDs)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ...domain.models import Hold


class HoldRepository(ABC):
    """Interfaz del repositorio de reservas temporales."""

    @abstractmethod
    def get(self, hold_id: str) -> Optional[Hold]:
        """Obtiene un hold por ID."""

    @abstractmethod
    def save(self, hold: Hold) -> None:
        """Persiste un hold."""

    @abstractmethod
    def find_active_by_user(self, user_id: str) -> list[Hold]:
        """Retorna los holds activos de un usuario."""

    @abstractmethod
    def list_all(self) -> list[Hold]:
        """Lista todos los holds."""

    @abstractmethod
    def list_active(self) -> list[Hold]:
        """Lista solo los holds activos."""
