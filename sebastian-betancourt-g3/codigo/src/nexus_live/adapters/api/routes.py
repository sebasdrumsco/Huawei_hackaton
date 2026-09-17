"""Rutas de la API REST para NEXUS LIVE.

Endpoints:
    GET    /api/seats              - Listar asientos
    GET    /api/seats/available    - Listar asientos disponibles
    POST   /api/holds              - Crear reserva (HOLD)
    GET    /api/holds/{hold_id}    - Consultar reserva
    DELETE /api/holds/{hold_id}    - Liberar reserva
    POST   /api/holds/confirm      - Confirmar compra
    POST   /api/simulate/race      - Simular carrera de concurrencia
    GET    /api/audit/{hold_id}    - Trazabilidad de una reserva
    GET    /api/circuit-breaker    - Estado del circuit breaker
    POST   /api/expire             - Expiar holds vencidos
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Header, HTTPException, Query

from ...domain.exceptions import (
    DomainError,
    HoldAlreadyConfirmedError,
    HoldExpiredError,
    HoldNotFoundError,
    HoldNotActiveError,
    IdempotencyConflictError,
    InvalidRequestError,
    PaymentServiceUnavailableError,
    SeatLimitExceededError,
    SeatNotFoundError,
    SeatNotAvailableError,
    DuplicateSeatInRequestError,
)
from ..api.schemas import (
    CircuitBreakerSchema,
    ConfirmRequestSchema,
    ConfirmResponseSchema,
    HoldResponseSchema,
    HoldSeatsRequestSchema,
    RaceRequestSchema,
    RaceResultSchema,
    RejectedSchema,
    SeatSchema,
    TransitionSchema,
)
from .composition import Container


def create_router(container: Container) -> APIRouter:
    """Crea el router de la API con todas las rutas.

    Args:
        container: Contenedor de dependencias.

    Returns:
        APIRouter configurado.
    """
    router = APIRouter(prefix="/api", tags=["nexus-live"])

    @router.get("/seats", response_model=list[SeatSchema])
    def list_seats(only_available: bool = Query(False)):
        """Lista asientos del catálogo."""
        seats = container.list_seats.execute(only_available=only_available)
        return [SeatSchema(**s.__dict__) for s in seats]

    @router.post("/holds")
    def create_hold(
        request: HoldSeatsRequestSchema,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ):
        """Crea una reserva temporal (HOLD).

        Headers:
            Idempotency-Key: Clave de idempotencia opcional.
        """
        from ...application.dto import HoldSeatsRequest

        try:
            result = container.hold_seats.execute(
                HoldSeatsRequest(
                    user_id=request.user_id,
                    event_id=request.event_id,
                    seat_ids=request.seat_ids,
                    idempotency_key=idempotency_key,
                )
            )
        except IdempotencyConflictError as e:
            raise HTTPException(status_code=409, detail={
                "status": "REJECTED",
                "reason": "IDEMPOTENCY_CONFLICT",
                "detail": str(e),
            })
        except (InvalidRequestError, DuplicateSeatInRequestError) as e:
            raise HTTPException(status_code=400, detail={
                "status": "REJECTED",
                "reason": "invalid_request",
                "detail": str(e),
            })
        except SeatNotFoundError as e:
            raise HTTPException(status_code=404, detail={
                "status": "REJECTED",
                "reason": "seat_not_found",
                "detail": str(e),
            })

        if hasattr(result, "hold_id"):
            return HoldResponseSchema(
                hold_id=result.hold_id,
                user_id=result.user_id,
                event_id=result.event_id,
                seat_ids=result.seat_ids,
                status=result.status,
                total=result.total,
                currency=result.currency,
                expires_at=result.expires_at,
                remaining_seconds=result.remaining_seconds,
            )
        return RejectedSchema(
            reason=result.reason,
            detail=result.detail,
        )

    @router.get("/holds/{hold_id}")
    def get_hold(hold_id: str):
        """Consulta una reserva por ID."""
        try:
            result = container.get_hold.execute(hold_id)
        except HoldNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))

        return HoldResponseSchema(
            hold_id=result.hold_id,
            user_id=result.user_id,
            event_id=result.event_id,
            seat_ids=result.seat_ids,
            status=result.status,
            total=result.total,
            currency=result.currency,
            expires_at=result.expires_at,
            remaining_seconds=result.remaining_seconds,
        )

    @router.delete("/holds/{hold_id}")
    def release_hold(hold_id: str):
        """Libera una reserva activa."""
        try:
            return container.release_hold.execute(hold_id)
        except HoldNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HoldNotActiveError as e:
            raise HTTPException(status_code=409, detail=str(e))

    @router.post("/holds/confirm")
    def confirm_hold(
        request: ConfirmRequestSchema,
        idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    ):
        """Confirma una compra procesando el pago."""
        from ...application.dto import ConfirmRequest

        try:
            result = container.confirm_hold.execute(
                ConfirmRequest(
                    hold_id=request.hold_id,
                    payment_token=request.payment_token,
                    idempotency_key=idempotency_key,
                )
            )
        except HoldNotFoundError as e:
            raise HTTPException(status_code=404, detail=str(e))
        except HoldExpiredError as e:
            raise HTTPException(status_code=410, detail=str(e))
        except HoldAlreadyConfirmedError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except HoldNotActiveError as e:
            raise HTTPException(status_code=409, detail=str(e))
        except InvalidRequestError as e:
            raise HTTPException(status_code=400, detail=str(e))
        except IdempotencyConflictError as e:
            raise HTTPException(status_code=409, detail={
                "status": "REJECTED",
                "reason": "IDEMPOTENCY_CONFLICT",
                "detail": str(e),
            })
        except Exception as e:
            if "Circuit breaker" in str(e):
                raise HTTPException(status_code=503, detail={
                    "status": "REJECTED",
                    "reason": "PAYMENT_SERVICE_UNAVAILABLE",
                    "detail": str(e),
                })
            raise

        if hasattr(result, "confirmation_id") and result.confirmation_id:
            return ConfirmResponseSchema(
                confirmation_id=result.confirmation_id,
                hold_id=result.hold_id,
                user_id=result.user_id,
                seat_ids=result.seat_ids,
                total=result.total,
                currency=result.currency,
                status=result.status,
                payment_result=result.payment_result,
            )
        return RejectedSchema(
            reason=result.reason,
            detail=result.detail,
        )

    @router.post("/simulate/race")
    def simulate_race(request: RaceRequestSchema):
        """Simula una carrera de N usuarios por un mismo asiento."""
        result = container.simulate_race.execute(
            seat_id=request.seat_id,
            event_id=request.event_id,
            num_users=request.num_users,
        )
        return RaceResultSchema(
            seat_id=result.seat_id,
            total_requests=result.total_requests,
            winners=result.winners,
            rejected=result.rejected,
            winner_hold_id=result.winner_hold_id,
        )

    @router.get("/audit/{hold_id}", response_model=list[TransitionSchema])
    def get_audit_trail(hold_id: str):
        """Obtiene la trazabilidad de una reserva."""
        transitions = container.audit_log.get_by_hold(hold_id)
        return [
            TransitionSchema(
                hold_id=t.hold_id,
                seat_id=t.seat_id,
                user_id=t.user_id,
                from_state=t.from_state.value,
                to_state=t.to_state.value,
                reason=t.reason.value,
                timestamp=t.timestamp,
            )
            for t in transitions
        ]

    @router.get("/circuit-breaker", response_model=CircuitBreakerSchema)
    def get_circuit_breaker_state():
        """Retorna el estado actual del circuit breaker."""
        data = container.circuit_breaker.to_dict()
        return CircuitBreakerSchema(**data)

    @router.post("/expire")
    def expire_holds():
        """Expira holds vencidos manualmente."""
        expired = container.expire_holds.execute()
        return {"expired_hold_ids": expired, "count": len(expired)}

    @router.get("/config")
    def get_config():
        """Retorna la configuración del sistema."""
        return {
            "max_seats_per_user": container.max_seats_per_user,
            "ttl_seconds": container.ttl_seconds,
        }

    return router
