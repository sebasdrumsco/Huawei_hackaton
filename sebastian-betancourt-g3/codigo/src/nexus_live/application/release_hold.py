"""Caso de uso: liberar una reserva (HOLD)."""
from __future__ import annotations

from ..domain.enums import SeatStatus, TransitionReason
from ..domain.exceptions import HoldNotFoundError, HoldNotActiveError
from ..domain.models import Transition
from .ports.audit_log import AuditLog
from .ports.hold_repository import HoldRepository
from .ports.seat_repository import SeatRepository


class ReleaseHoldUseCase:
    """Libera un hold activo, devolviendo los asientos a AVAILABLE."""

    def __init__(
        self,
        seat_repo: SeatRepository,
        hold_repo: HoldRepository,
        audit_log: AuditLog,
    ):
        self._seat_repo = seat_repo
        self._hold_repo = hold_repo
        self._audit = audit_log

    def execute(self, hold_id: str) -> dict:
        """Libera un hold.

        Returns:
            Diccionario con hold_id y asientos liberados.

        Raises:
            HoldNotFoundError: si el hold no existe.
            HoldNotActiveError: si el hold no está activo.
        """
        hold = self._hold_repo.get(hold_id)
        if hold is None:
            raise HoldNotFoundError(hold_id)
        if not hold.is_active():
            raise HoldNotActiveError(hold_id, hold.status.value)

        self._seat_repo.lock()
        try:
            seats = self._seat_repo.get_many(hold.seat_ids)
            for seat in seats:
                prev = seat.status
                seat.release()
                self._audit.record(Transition(
                    hold_id=hold_id,
                    seat_id=seat.seat_id,
                    from_state=prev,
                    to_state=SeatStatus.AVAILABLE,
                    reason=TransitionReason.HOLD_RELEASED,
                    user_id=hold.user_id,
                ))
            self._seat_repo.save_many(seats)

            hold.cancel()
            self._hold_repo.save(hold)
        finally:
            self._seat_repo.unlock()

        return {
            "hold_id": hold_id,
            "status": "CANCELLED",
            "released_seats": hold.seat_ids,
        }
