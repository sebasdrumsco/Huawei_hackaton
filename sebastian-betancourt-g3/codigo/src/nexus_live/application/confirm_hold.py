"""Caso de uso: confirmar compra (FASE 3).

Convierte un HOLD válido en una venta confirmada tras autorizar
el pago con el proveedor externo. Incluye circuit breaker para
manejar la degradación del servicio de pagos.

Estrategia ante fallos:
    - APPROVED  -> HELD a SOLD, compra confirmada.
    - DECLINED  -> Hold se libera inmediatamente (asientos vuelven a AVAILABLE).
    - ERROR     -> Hold permanece activo; el cliente puede reintentar.
    - TIMEOUT   -> Hold permanece activo; el cliente puede reintentar.
    - CB OPEN   -> PaymentServiceUnavailableError; el hold no se modifica.

La decisión de NO liberar el hold en ERROR/TIMEOUT evita:
    - doble cobro al reintentar;
    - liberar un asiento mientras una operación queda pendiente;
    - vender sin certeza del resultado del pago.
"""
from __future__ import annotations

from typing import Optional

from ..domain.enums import PaymentResult, SeatStatus, TransitionReason
from ..domain.exceptions import (
    HoldExpiredError,
    HoldNotFoundError,
    HoldNotActiveError,
    HoldAlreadyConfirmedError,
    InvalidRequestError,
    PaymentServiceUnavailableError,
    IdempotencyConflictError,
)
from ..domain.models import Confirmation, Transition
from ..domain.services import IdGenerator
from .dto import ConfirmRequest, ConfirmResponse, RejectedResponse
from .ports.audit_log import AuditLog
from .ports.clock import Clock
from .ports.hold_repository import HoldRepository
from .ports.idempotency_store import IdempotencyStore
from .ports.payment_gateway import PaymentGateway
from .ports.seat_repository import SeatRepository


class ConfirmHoldUseCase:
    """Confirma una reserva tras procesar el pago.

    Flujo:
        HOLD válido -> validar no expirado -> autorizar pago ->
        si APPROVED -> HELD a SOLD -> crear confirmación.
    """

    def __init__(
        self,
        seat_repo: SeatRepository,
        hold_repo: HoldRepository,
        payment_gateway: PaymentGateway,
        idempotency_store: IdempotencyStore,
        audit_log: AuditLog,
        clock: Clock,
    ):
        self._seat_repo = seat_repo
        self._hold_repo = hold_repo
        self._payment = payment_gateway
        self._idempotency = idempotency_store
        self._audit = audit_log
        self._clock = clock

    def execute(
        self, request: ConfirmRequest
    ) -> ConfirmResponse | RejectedResponse:
        """Ejecuta la confirmación de compra.

        Returns:
            ConfirmResponse si el pago fue aprobado.
            RejectedResponse si fue rechazado o hubo error.

        Raises:
            HoldNotFoundError: si el hold no existe.
            HoldExpiredError: si el hold ya expiró.
            HoldAlreadyConfirmedError: si el hold ya fue confirmado.
            PaymentServiceUnavailableError: si el circuit breaker está OPEN.
            IdempotencyConflictError: si la clave de idempotencia entra en conflicto.
            InvalidRequestError: si el payment_token es vacío.
        """
        if not request.payment_token or not request.payment_token.strip():
            raise InvalidRequestError("payment_token is required")

        payload_hash = f"{request.hold_id}|{request.payment_token}"

        if request.idempotency_key:
            cached = self._check_idempotency(
                request.idempotency_key, payload_hash
            )
            if cached is not None:
                return cached

        hold = self._hold_repo.get(request.hold_id)
        if hold is None:
            raise HoldNotFoundError(request.hold_id)
        if hold.status.value == "CONFIRMED":
            raise HoldAlreadyConfirmedError(request.hold_id)
        if not hold.is_active():
            raise HoldNotActiveError(request.hold_id, hold.status.value)
        if hold.is_expired(self._clock.now()):
            raise HoldExpiredError(request.hold_id)

        try:
            payment_result = self._payment.authorize(
                request.payment_token, hold.total, hold.currency
            )
        except PaymentServiceUnavailableError:
            return self._service_unavailable(hold)

        response = self._process_payment_result(hold, request, payment_result)

        if request.idempotency_key:
            self._idempotency.save(
                request.idempotency_key, payload_hash, self._response_to_dict(response)
            )

        return response

    def _process_payment_result(
        self, hold, request: ConfirmRequest, result: PaymentResult
    ) -> ConfirmResponse | RejectedResponse:
        """Procesa el resultado del pago y actualiza el dominio."""
        if result == PaymentResult.APPROVED:
            return self._approve(hold, request)
        elif result == PaymentResult.DECLINED:
            return self._decline(hold)
        elif result == PaymentResult.ERROR:
            return self._error(hold)
        elif result == PaymentResult.TIMEOUT:
            return self._timeout(hold)
        else:
            return RejectedResponse(reason="unknown_payment_result")

    def _approve(self, hold, request: ConfirmRequest) -> ConfirmResponse:
        """Pago aprobado: HELD -> SOLD."""
        self._seat_repo.lock()
        try:
            seats = self._seat_repo.get_many(hold.seat_ids)
            for seat in seats:
                prev = seat.status
                seat.sell()
                self._audit.record(Transition(
                    hold_id=hold.hold_id,
                    seat_id=seat.seat_id,
                    from_state=prev,
                    to_state=SeatStatus.SOLD,
                    reason=TransitionReason.PAYMENT_APPROVED,
                    user_id=hold.user_id,
                ))
            self._seat_repo.save_many(seats)

            hold.confirm()
            self._hold_repo.save(hold)

            confirmation = Confirmation(
                confirmation_id=IdGenerator.confirmation_id(),
                hold_id=hold.hold_id,
                user_id=hold.user_id,
                payment_token=request.payment_token,
                total=hold.total,
                currency=hold.currency,
                created_at=self._clock.now(),
            )
        finally:
            self._seat_repo.unlock()

        return ConfirmResponse(
            confirmation_id=confirmation.confirmation_id,
            hold_id=hold.hold_id,
            user_id=hold.user_id,
            seat_ids=hold.seat_ids,
            total=hold.total,
            currency=hold.currency,
            status="SOLD",
            payment_result=PaymentResult.APPROVED.value,
        )

    def _decline(self, hold) -> RejectedResponse:
        """Pago rechazado: libera los asientos inmediatamente."""
        self._seat_repo.lock()
        try:
            seats = self._seat_repo.get_many(hold.seat_ids)
            for seat in seats:
                prev = seat.status
                seat.release()
                self._audit.record(Transition(
                    hold_id=hold.hold_id,
                    seat_id=seat.seat_id,
                    from_state=prev,
                    to_state=SeatStatus.AVAILABLE,
                    reason=TransitionReason.PAYMENT_DECLINED,
                    user_id=hold.user_id,
                ))
            self._seat_repo.save_many(seats)

            hold.cancel()
            self._hold_repo.save(hold)
        finally:
            self._seat_repo.unlock()

        return RejectedResponse(
            reason="payment_declined",
            detail=f"Hold {hold.hold_id} cancelled, seats released.",
        )

    def _error(self, hold) -> RejectedResponse:
        """Error ambiguo: el hold permanece activo para reintento."""
        self._audit.record(Transition(
            hold_id=hold.hold_id,
            seat_id=hold.seat_ids[0],
            from_state=SeatStatus.HELD,
            to_state=SeatStatus.HELD,
            reason=TransitionReason.PAYMENT_ERROR,
            user_id=hold.user_id,
        ))
        return RejectedResponse(
            reason="payment_error",
            detail=(
                f"Hold {hold.hold_id} remains active. "
                "Client may retry. Seats are NOT released."
            ),
        )

    def _timeout(self, hold) -> RejectedResponse:
        """Timeout: el hold permanece activo para reintento."""
        self._audit.record(Transition(
            hold_id=hold.hold_id,
            seat_id=hold.seat_ids[0],
            from_state=SeatStatus.HELD,
            to_state=SeatStatus.HELD,
            reason=TransitionReason.PAYMENT_TIMEOUT,
            user_id=hold.user_id,
        ))
        return RejectedResponse(
            reason="payment_timeout",
            detail=(
                f"Hold {hold.hold_id} remains active. "
                "Payment may have succeeded; do NOT double-charge. "
                "Client should verify before retrying."
            ),
        )

    def _service_unavailable(self, hold) -> RejectedResponse:
        """Circuit breaker OPEN: el servicio de pagos no esta disponible.

        El hold permanece activo (NO se libera ni se vende).
        El asiento NO se marca como SOLD.
        """
        self._audit.record(Transition(
            hold_id=hold.hold_id,
            seat_id=hold.seat_ids[0],
            from_state=SeatStatus.HELD,
            to_state=SeatStatus.HELD,
            reason=TransitionReason.PAYMENT_SERVICE_UNAVAILABLE,
            user_id=hold.user_id,
        ))
        return RejectedResponse(
            reason="payment_service_unavailable",
            detail=(
                f"Hold {hold.hold_id} remains active. "
                "Payment service is unavailable (circuit breaker OPEN). "
                "Retry later. Seats are NOT released."
            ),
        )

    def _check_idempotency(
        self, key: str, payload_hash: str
    ) -> Optional[ConfirmResponse | RejectedResponse]:
        stored_hash = self._idempotency.get_payload_hash(key)
        if stored_hash is not None:
            if stored_hash != payload_hash:
                raise IdempotencyConflictError(key)
            cached = self._idempotency.get(key)
            if cached is not None:
                return self._dict_to_response(cached)
        return None

    def _response_to_dict(self, response) -> dict:
        return {
            "type": type(response).__name__,
            "confirmation_id": getattr(response, "confirmation_id", None),
            "hold_id": getattr(response, "hold_id", None),
            "user_id": getattr(response, "user_id", None),
            "seat_ids": getattr(response, "seat_ids", None),
            "total": getattr(response, "total", None),
            "currency": getattr(response, "currency", None),
            "status": getattr(response, "status", None),
            "payment_result": getattr(response, "payment_result", None),
            "reason": getattr(response, "reason", None),
            "detail": getattr(response, "detail", None),
        }

    def _dict_to_response(self, data: dict):
        if data.get("type") == "ConfirmResponse":
            return ConfirmResponse(
                confirmation_id=data["confirmation_id"],
                hold_id=data["hold_id"],
                user_id=data["user_id"],
                seat_ids=data["seat_ids"],
                total=data["total"],
                currency=data["currency"],
                status=data["status"],
                payment_result=data["payment_result"],
            )
        return RejectedResponse(
            reason=data.get("reason", ""),
            detail=data.get("detail"),
        )
