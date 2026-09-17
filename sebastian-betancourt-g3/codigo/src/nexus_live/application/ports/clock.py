"""Puerto del reloj (abstracción de tiempo)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime


class Clock(ABC):
    """Interfaz del reloj para abstraer la obtención del tiempo.

    Permite inyectar un reloj fijo en tests para controlar
    la expiración de holds.
    """

    @abstractmethod
    def now(self) -> datetime:
        """Retorna el timestamp actual."""
