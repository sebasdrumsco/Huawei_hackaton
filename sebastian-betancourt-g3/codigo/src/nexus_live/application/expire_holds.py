"""Caso de uso: expirar holds vencidos.

Debe ejecutarse periódicamente (background task o cron) para
liberar asientos de reservas que expiraron sin confirmarse.
"""
from __future__ import annotations

from ..domain.enums import SeatStatus, TransitionReason
from ..domain.models import Transition
from .ports.audit_log import AuditLog
from .ports.clock import Clock
from .ports.hold_repository import HoldRepository
from .ports.seat_repository import SeatRepository


class ExpireHoldsUseCase:
    """Expira todos los holds que pasaron su TTL.

    Transición: HELD -> AVAILABLE para cada asiento del hold.
    """

    def __init__(
        self,
        seat_repo: SeatRepository,
        hold_repo: HoldRepository,
        audit_log: AuditLog,
        clock: Clock,
    ):
        self._seat_repo = seat_repo
        self._hold_repo = hold_repo
        self._audit = audit_log
        self._clock = clock

    def execute(self) -> list[str]:
        """Expira los holds vencidos.

        Returns:
            Lista de hold_ids expirados.
        """
        now = self._clock.now()
        expired_ids: list[str] = []

        self._seat_repo.lock()
        try:
            active_holds = self._hold_repo.list_active()
            for hold in active_holds:
                if not hold.is_expired(now):
                    continue

                seats = self._seat_repo.get_many(hold.seat_ids)
                for seat in seats:
                    prev = seat.status
                    seat.release()
                    self._audit.record(Transition(
                        hold_id=hold.hold_id,
                        seat_id=seat.seat_id,
                        from_state=prev,
                        to_state=SeatStatus.AVAILABLE,
                        reason=TransitionReason.HOLD_EXPIRED,
                        user_id=hold.user_id,
                    ))
                self._seat_repo.save_many(seats)

                hold.expire()
                self._hold_repo.save(hold)
                expired_ids.append(hold.hold_id)
        finally:
            self._seat_repo.unlock()

        return expired_ids
