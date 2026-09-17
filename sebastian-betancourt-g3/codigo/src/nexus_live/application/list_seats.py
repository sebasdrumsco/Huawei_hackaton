"""Caso de uso: listar asientos disponibles."""
from __future__ import annotations

from .dto import SeatResponse
from .ports.seat_repository import SeatRepository


class ListSeatsUseCase:
    """Lista asientos del catálogo, opcionalmente filtrando por estado."""

    def __init__(self, seat_repo: SeatRepository):
        self._seat_repo = seat_repo

    def execute(self, only_available: bool = False) -> list[SeatResponse]:
        """Retorna la lista de asientos.

        Args:
            only_available: Si True, retorna solo los AVAILABLE.
        """
        seats = (
            self._seat_repo.list_available()
            if only_available
            else self._seat_repo.list_all()
        )
        return [
            SeatResponse(
                seat_id=s.seat_id,
                section=s.section,
                price=s.price,
                currency=s.currency,
                status=s.status.value,
            )
            for s in seats
        ]
