"""Composition root: ensambla todas las dependencias.

Crea los adaptadores de infraestructura, los casos de uso y
la configuración del sistema. Este es el único punto donde
las dependencias se cablean explícitamente.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from ...application.confirm_hold import ConfirmHoldUseCase
from ...application.expire_holds import ExpireHoldsUseCase
from ...application.get_hold import GetHoldUseCase
from ...application.hold_seats import HoldSeatsUseCase
from ...application.list_seats import ListSeatsUseCase
from ...application.release_hold import ReleaseHoldUseCase
from ...application.simulate_race import SimulateRaceUseCase
from ...domain.enums import SeatStatus
from ...domain.models import Seat
from ...infrastructure.circuit_breaker import CircuitBreaker
from ...infrastructure.in_memory_audit_log import InMemoryAuditLog
from ...infrastructure.in_memory_hold_repository import InMemoryHoldRepository
from ...infrastructure.in_memory_idempotency_store import InMemoryIdempotencyStore
from ...infrastructure.in_memory_seat_repository import InMemorySeatRepository
from ...infrastructure.mock_payment_gateway import MockPaymentGateway
from ...infrastructure.system_clock import SystemClock


@dataclass
class Container:
    """Contenedor de dependencias.

    Agrupa todos los casos de uso y servicios configurados
    para que los adaptadores de entrada puedan acceder a ellos.
    """
    hold_seats: HoldSeatsUseCase
    get_hold: GetHoldUseCase
    release_hold: ReleaseHoldUseCase
    list_seats: ListSeatsUseCase
    confirm_hold: ConfirmHoldUseCase
    expire_holds: ExpireHoldsUseCase
    simulate_race: SimulateRaceUseCase
    seat_repo: InMemorySeatRepository
    hold_repo: InMemoryHoldRepository
    audit_log: InMemoryAuditLog
    payment_gateway: MockPaymentGateway
    circuit_breaker: CircuitBreaker
    max_seats_per_user: int
    ttl_seconds: int


def _build_default_seats() -> list[Seat]:
    """Crea el catálogo inicial de asientos del evento AURORA WORLD TOUR."""
    seats: list[Seat] = []

    for i in range(1, 11):
        seats.append(Seat(
            seat_id=f"VIP-A-{i:03d}",
            section="VIP",
            price=500000,
            currency="COP",
        ))

    for i in range(101, 121):
        seats.append(Seat(
            seat_id=f"A-{i:03d}",
            section="GENERAL-A",
            price=210000,
            currency="COP",
        ))

    for i in range(1, 21):
        seats.append(Seat(
            seat_id=f"B-{i:03d}",
            section="GENERAL-B",
            price=150000,
            currency="COP",
        ))

    return seats


def build_container(
    max_seats_per_user: int = 6,
    ttl_seconds: int = 120,
    seats: Optional[list[Seat]] = None,
    payment_force_result=None,
    cb_failure_threshold: int = 3,
    cb_recovery_timeout: float = 15.0,
) -> Container:
    """Construye el contenedor de dependencias.

    Args:
        max_seats_per_user: Límite de asientos por usuario.
        ttl_seconds: TTL de los holds en segundos.
        seats: Catálogo de asientos inicial (default: AURORA).
        payment_force_result: Forzar resultado de pago (para tests).
        cb_failure_threshold: Fallos para abrir el circuit breaker.
        cb_recovery_timeout: Segundos de recuperación del circuit breaker.

    Returns:
        Container con todos los casos de uso cableados.
    """
    if seats is None:
        seats = _build_default_seats()

    seat_repo = InMemorySeatRepository(seats)
    hold_repo = InMemoryHoldRepository()
    idempotency_store = InMemoryIdempotencyStore()
    audit_log = InMemoryAuditLog()
    clock = SystemClock()

    circuit_breaker = CircuitBreaker(
        failure_threshold=cb_failure_threshold,
        recovery_timeout=cb_recovery_timeout,
    )
    payment_gateway = MockPaymentGateway(
        circuit_breaker=circuit_breaker,
        force_result=payment_force_result,
    )

    hold_seats_uc = HoldSeatsUseCase(
        seat_repo=seat_repo,
        hold_repo=hold_repo,
        idempotency_store=idempotency_store,
        audit_log=audit_log,
        clock=clock,
        max_seats_per_user=max_seats_per_user,
        ttl_seconds=ttl_seconds,
    )

    get_hold_uc = GetHoldUseCase(hold_repo=hold_repo, clock=clock)

    release_hold_uc = ReleaseHoldUseCase(
        seat_repo=seat_repo,
        hold_repo=hold_repo,
        audit_log=audit_log,
    )

    list_seats_uc = ListSeatsUseCase(seat_repo=seat_repo)

    confirm_hold_uc = ConfirmHoldUseCase(
        seat_repo=seat_repo,
        hold_repo=hold_repo,
        payment_gateway=payment_gateway,
        idempotency_store=idempotency_store,
        audit_log=audit_log,
        clock=clock,
    )

    expire_holds_uc = ExpireHoldsUseCase(
        seat_repo=seat_repo,
        hold_repo=hold_repo,
        audit_log=audit_log,
        clock=clock,
    )

    simulate_race_uc = SimulateRaceUseCase(hold_use_case=hold_seats_uc)

    return Container(
        hold_seats=hold_seats_uc,
        get_hold=get_hold_uc,
        release_hold=release_hold_uc,
        list_seats=list_seats_uc,
        confirm_hold=confirm_hold_uc,
        expire_holds=expire_holds_uc,
        simulate_race=simulate_race_uc,
        seat_repo=seat_repo,
        hold_repo=hold_repo,
        audit_log=audit_log,
        payment_gateway=payment_gateway,
        circuit_breaker=circuit_breaker,
        max_seats_per_user=max_seats_per_user,
        ttl_seconds=ttl_seconds,
    )
