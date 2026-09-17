"""Puerto del almacén de idempotencia."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class IdempotencyStore(ABC):
    """Interfaz del almacén de claves de idempotencia.

    Permite que una misma solicitud con la misma Idempotency-Key
    produzca el mismo resultado lógico sin efectos secundarios
    duplicados.
    """

    @abstractmethod
    def get(self, key: str) -> Optional[dict]:
        """Obtiene el resultado almacenado para una clave.

        Returns:
            El resultado guardado o None si no existe.
        """

    @abstractmethod
    def get_payload_hash(self, key: str) -> Optional[str]:
        """Obtiene el hash del payload original asociado a la clave."""

    @abstractmethod
    def save(self, key: str, payload_hash: str, result: dict) -> None:
        """Guarda el resultado de una operación idempotente."""
