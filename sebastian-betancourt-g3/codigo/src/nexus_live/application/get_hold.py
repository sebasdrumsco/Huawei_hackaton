"""Caso de uso: consultar una reserva (HOLD)."""
from __future__ import annotations

from typing import Optional

from ..domain.exceptions import HoldNotFoundError
from ..domain.models import Hold
from .dto import HoldResponse
from .ports.clock import Clock
from .ports.hold_repository import HoldRepository


class GetHoldUseCase:
    """Obtiene los detalles de un hold por su ID."""

    def __init__(self, hold_repo: HoldRepository, clock: Clock):
        self._hold_repo = hold_repo
        self._clock = clock

    def execute(self, hold_id: str) -> HoldResponse:
        """Retorna los detalles del hold.

        Raises:
            HoldNotFoundError: si el hold no existe.
        """
        hold = self._hold_repo.get(hold_id)
        if hold is None:
            raise HoldNotFoundError(hold_id)
        return self._to_response(hold)

    def _to_response(self, hold: Hold) -> HoldResponse:
        seat_status = {
            "ACTIVE": "HELD",
            "CONFIRMED": "SOLD",
            "EXPIRED": "AVAILABLE",
            "CANCELLED": "AVAILABLE",
        }.get(hold.status.value, hold.status.value)
        return HoldResponse(
            hold_id=hold.hold_id,
            user_id=hold.user_id,
            event_id=hold.event_id,
            seat_ids=hold.seat_ids,
            status=seat_status,
            total=hold.total,
            currency=hold.currency,
            expires_at=hold.expires_at,
            remaining_seconds=hold.remaining_seconds(self._clock.now()),
        )
