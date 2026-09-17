"""Caso de uso: reservar asientos (crear HOLD).

Implementa FASE 1 (reserva todo-o-nada, TTL, límite de asientos,
precio controlado por servidor) y FASE 2 (idempotencia y concurrencia).

El caso de uso adquiere el lock del repositorio de asientos para
garantizar que la operación sea atómica frente a solicitudes
concurrentes.
"""
from __future__ import annotations

from typing import Optional

from ..domain.enums import SeatStatus, TransitionReason
from ..domain.exceptions import (
    DuplicateSeatInRequestError,
    InvalidRequestError,
    SeatLimitExceededError,
    SeatNotAvailableError,
    SeatNotFoundError,
    IdempotencyConflictError,
)
from ..domain.models import Hold, Seat, Transition
from ..domain.services import HoldFactory, IdGenerator, PayloadHasher, PricingService
from .dto import HoldResponse, HoldSeatsRequest, RejectedResponse
from .ports.audit_log import AuditLog
from .ports.clock import Clock
from .ports.hold_repository import HoldRepository
from .ports.idempotency_store import IdempotencyStore
from .ports.seat_repository import SeatRepository


class HoldSeatsUseCase:
    """Crea una reserva temporal de asientos.

    Reglas:
        1. Reserva todo-o-nada: si un asiento no está disponible, falla.
        2. Límite de asientos por usuario configurable.
        3. El precio lo calcula el servidor.
        4. Idempotencia: misma clave + mismo payload = mismo resultado.
        5. Concurrencia: lock del repositorio garantiza atomicidad.
    """

    def __init__(
        self,
        seat_repo: SeatRepository,
        hold_repo: HoldRepository,
        idempotency_store: IdempotencyStore,
        audit_log: AuditLog,
        clock: Clock,
        max_seats_per_user: int = 6,
        ttl_seconds: int = 120,
    ):
        self._seat_repo = seat_repo
        self._hold_repo = hold_repo
        self._idempotency = idempotency_store
        self._audit = audit_log
        self._clock = clock
        self._max_seats = max_seats_per_user
        self._ttl = ttl_seconds

    def execute(self, request: HoldSeatsRequest) -> HoldResponse | RejectedResponse:
        """Ejecuta la reserva de asientos.

        Returns:
            HoldResponse si la reserva fue exitosa.
            RejectedResponse si fue rechazada (asiento no disponible, etc.).

        Raises:
            IdempotencyConflictError: si la clave de idempotencia
                se reutiliza con un payload diferente.
            InvalidRequestError: si la solicitud es inválida.
        """
        self._validate_request(request)

        payload_hash = PayloadHasher.hash(
            request.user_id, request.event_id, request.seat_ids
        )

        if request.idempotency_key:
            cached = self._check_idempotency(
                request.idempotency_key, payload_hash
            )
            if cached is not None:
                return cached

        try:
            hold = self._create_hold(request)
        except SeatNotAvailableError as e:
            return RejectedResponse(
                reason="seat_not_available",
                detail=f"Seats not available: {e.seat_ids}",
            )
        except SeatLimitExceededError as e:
            return RejectedResponse(
                reason="seat_limit_exceeded",
                detail=str(e),
            )

        response = self._to_response(hold)

        if request.idempotency_key:
            self._idempotency.save(
                request.idempotency_key, payload_hash, self._response_to_dict(response)
            )

        return response

    def _validate_request(self, request: HoldSeatsRequest) -> None:
        """Valida la solicitud de entrada."""
        if not request.user_id or not request.user_id.strip():
            raise InvalidRequestError("user_id is required")
        if not request.event_id or not request.event_id.strip():
            raise InvalidRequestError("event_id is required")
        if not request.seat_ids or len(request.seat_ids) == 0:
            raise InvalidRequestError("seat_ids must not be empty")

        seen = set()
        for seat_id in request.seat_ids:
            if seat_id in seen:
                raise DuplicateSeatInRequestError(seat_id)
            seen.add(seat_id)

    def _check_idempotency(
        self, key: str, payload_hash: str
    ) -> Optional[HoldResponse]:
        """Verifica si ya existe un resultado para la clave de idempotencia.

        Raises:
            IdempotencyConflictError: si la clave se reutiliza con
                un payload diferente.
        """
        stored_hash = self._idempotency.get_payload_hash(key)
        if stored_hash is not None:
            if stored_hash != payload_hash:
                raise IdempotencyConflictError(key)
            cached = self._idempotency.get(key)
            if cached is not None:
                return self._dict_to_response(cached)
        return None

    def _create_hold(self, request: HoldSeatsRequest) -> Hold:
        """Crea el hold de forma atómica bajo lock.

        Adquiere el lock del repositorio de asientos para que
        ninguna otra operación pueda modificar los asientos
        mientras se verifica disponibilidad y se reservan.
        """
        self._seat_repo.lock()
        try:
            seats = self._seat_repo.get_many(request.seat_ids)

            self._validate_seats_exist(request.seat_ids, seats)
            self._validate_seats_available(seats)
            self._validate_user_limit(request.user_id, len(request.seat_ids))

            hold_id = IdGenerator.hold_id()
            total, currency = PricingService.calculate_total(
                seats, seats[0].currency
            )

            hold = HoldFactory.create(
                hold_id=hold_id,
                user_id=request.user_id,
                event_id=request.event_id,
                seat_ids=request.seat_ids,
                total=total,
                currency=currency,
                ttl_seconds=self._ttl,
                now=self._clock.now(),
            )

            for seat in seats:
                seat.hold(hold_id)
                self._audit.record(Transition(
                    hold_id=hold_id,
                    seat_id=seat.seat_id,
                    from_state=SeatStatus.AVAILABLE,
                    to_state=SeatStatus.HELD,
                    reason=TransitionReason.HOLD_CREATED,
                    user_id=request.user_id,
                ))

            self._seat_repo.save_many(seats)
            self._hold_repo.save(hold)

            return hold
        finally:
            self._seat_repo.unlock()

    def _validate_seats_exist(
        self, requested: list[str], found: list[Seat]
    ) -> None:
        """Verifica que todos los asientos solicitados existan."""
        found_ids = {s.seat_id for s in found}
        missing = [sid for sid in requested if sid not in found_ids]
        if missing:
            raise SeatNotFoundError(missing[0])

    def _validate_seats_available(self, seats: list[Seat]) -> None:
        """Verifica que todos los asientos estén disponibles."""
        unavailable = [s.seat_id for s in seats if not s.is_available()]
        if unavailable:
            raise SeatNotAvailableError(unavailable)

    def _validate_user_limit(self, user_id: str, requested_count: int) -> None:
        """Verifica que el usuario no exceda el límite de asientos."""
        active_holds = self._hold_repo.find_active_by_user(user_id)
        current_count = sum(len(h.seat_ids) for h in active_holds)
        if current_count + requested_count > self._max_seats:
            raise SeatLimitExceededError(
                self._max_seats, current_count, requested_count
            )

    def _to_response(self, hold: Hold) -> HoldResponse:
        """Convierte un hold a respuesta.

        El status refleja el estado de los asientos (HELD/SOLD/AVAILABLE),
        no el ciclo de vida interno del hold (ACTIVE/EXPIRED/...).
        """
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

    def _response_to_dict(self, response: HoldResponse) -> dict:
        return {
            "hold_id": response.hold_id,
            "user_id": response.user_id,
            "event_id": response.event_id,
            "seat_ids": response.seat_ids,
            "status": response.status,
            "total": response.total,
            "currency": response.currency,
            "expires_at": response.expires_at.isoformat(),
            "remaining_seconds": response.remaining_seconds,
        }

    def _dict_to_response(self, data: dict) -> HoldResponse:
        from datetime import datetime
        return HoldResponse(
            hold_id=data["hold_id"],
            user_id=data["user_id"],
            event_id=data["event_id"],
            seat_ids=data["seat_ids"],
            status=data["status"],
            total=data["total"],
            currency=data["currency"],
            expires_at=datetime.fromisoformat(data["expires_at"]),
            remaining_seconds=data["remaining_seconds"],
        )
