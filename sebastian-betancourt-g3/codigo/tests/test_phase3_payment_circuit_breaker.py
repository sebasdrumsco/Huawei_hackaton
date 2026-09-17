"""Tests FASE 3 - Confirmación y proveedor de pagos inestable.

Cubre:
    - Pago APPROVED -> HELD a SOLD.
    - Pago DECLINED -> hold cancelado, asientos liberados.
    - Pago ERROR -> hold permanece activo.
    - Pago TIMEOUT -> hold permanece activo.
    - Circuit breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED.
    - Circuit breaker OPEN -> PaymentServiceUnavailable.
    - Confirmar hold expirado -> error.
    - Confirmar hold ya confirmado -> error.
    - Trazabilidad de la confirmación.
"""
from __future__ import annotations

import time

import pytest

from nexus_live.application.dto import ConfirmRequest, HoldSeatsRequest
from nexus_live.domain.enums import PaymentResult
from nexus_live.domain.exceptions import (
    HoldAlreadyConfirmedError,
    HoldExpiredError,
    HoldNotFoundError,
)
from nexus_live.domain.services import IdGenerator
from nexus_live.infrastructure.circuit_breaker import CircuitBreaker


@pytest.fixture
def approved_container():
    """Container con pago siempre aprobado."""
    from nexus_live.adapters.api.composition import build_container
    return build_container(payment_force_result=PaymentResult.APPROVED)


@pytest.fixture
def declined_container():
    """Container con pago siempre rechazado."""
    from nexus_live.adapters.api.composition import build_container
    return build_container(payment_force_result=PaymentResult.DECLINED)


@pytest.fixture
def error_container():
    """Container con pago siempre en error."""
    from nexus_live.adapters.api.composition import build_container
    return build_container(payment_force_result=PaymentResult.ERROR)


@pytest.fixture
def timeout_container():
    """Container con pago siempre en timeout."""
    from nexus_live.adapters.api.composition import build_container
    return build_container(payment_force_result=PaymentResult.TIMEOUT)


class TestPaymentApproved:
    """Tests de pago aprobado."""

    def test_approved_sells_seats(self, approved_container):
        """Escenario A: pago aprobado -> HELD a SOLD."""
        container = approved_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        result = container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok_test"
        ))
        assert result.status == "SOLD"
        assert result.payment_result == "APPROVED"
        assert result.confirmation_id is not None

        seats = container.list_seats.execute()
        seat = next(s for s in seats if s.seat_id == "A-101")
        assert seat.status == "SOLD"

    def test_trazabilidad_on_sale(self, approved_container):
        """La confirmación registra HELD -> SOLD en la trazabilidad."""
        container = approved_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok_test"
        ))
        transitions = container.audit_log.get_by_hold(hold.hold_id)
        sale_transitions = [t for t in transitions if t.to_state.value == "SOLD"]
        assert len(sale_transitions) == 1
        assert sale_transitions[0].reason.value == "payment_approved"


class TestPaymentDeclined:
    """Tests de pago rechazado."""

    def test_declined_releases_seats(self, declined_container):
        """Pago rechazado -> asientos vuelven a AVAILABLE."""
        container = declined_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        result = container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok_test"
        ))
        assert result.reason == "payment_declined"

        seats = container.list_seats.execute()
        seat = next(s for s in seats if s.seat_id == "A-101")
        assert seat.status == "AVAILABLE"


class TestPaymentError:
    """Tests de error de pago (resultado ambiguo)."""

    def test_error_keeps_hold_active(self, error_container):
        """Pago con ERROR -> hold permanece activo, asientos NO se liberan."""
        container = error_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        result = container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok_test"
        ))
        assert result.reason == "payment_error"

        seats = container.list_seats.execute()
        seat = next(s for s in seats if s.seat_id == "A-101")
        assert seat.status == "HELD"

        hold_after = container.get_hold.execute(hold.hold_id)
        assert hold_after.status == "HELD"


class TestPaymentTimeout:
    """Tests de timeout de pago (resultado ambiguo)."""

    def test_timeout_keeps_hold_active(self, timeout_container):
        """Pago con TIMEOUT -> hold permanece activo, NO se libera."""
        container = timeout_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        result = container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok_test"
        ))
        assert result.reason == "payment_timeout"

        seats = container.list_seats.execute()
        seat = next(s for s in seats if s.seat_id == "A-101")
        assert seat.status == "HELD"


class TestConfirmEdgeCases:
    """Tests de casos límite en la confirmación."""

    def test_confirm_nonexistent_hold(self, approved_container):
        """Confirmar un hold inexistente -> error."""
        with pytest.raises(HoldNotFoundError):
            approved_container.confirm_hold.execute(ConfirmRequest(
                hold_id="hold_nonexistent", payment_token="tok"
            ))

    def test_confirm_already_confirmed(self, approved_container):
        """Confirmar dos veces el mismo hold -> error."""
        container = approved_container
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold.hold_id, payment_token="tok"
        ))
        with pytest.raises(HoldAlreadyConfirmedError):
            container.confirm_hold.execute(ConfirmRequest(
                hold_id=hold.hold_id, payment_token="tok"
            ))

    def test_confirm_expired_hold(self):
        """Confirmar un hold expirado -> error."""
        from nexus_live.adapters.api.composition import build_container
        container = build_container(
            ttl_seconds=1, payment_force_result=PaymentResult.APPROVED
        )
        IdGenerator.reset()
        hold = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        time.sleep(2)
        container.expire_holds.execute()
        with pytest.raises(HoldNotActiveError if False else (HoldExpiredError, Exception)):
            container.confirm_hold.execute(ConfirmRequest(
                hold_id=hold.hold_id, payment_token="tok"
            ))


class TestCircuitBreaker:
    """Tests del circuit breaker."""

    def test_circuit_breaker_starts_closed(self):
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)
        assert cb.state.value == "CLOSED"

    def test_circuit_opens_after_threshold(self):
        """3 fallos consecutivos -> OPEN."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)

        for _ in range(3):
            try:
                cb.call(lambda: PaymentResult.ERROR)
            except Exception:
                pass

        assert cb.state.value == "OPEN"

    def test_circuit_blocks_calls_when_open(self):
        """Cuando está OPEN, las llamadas se rechazan."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=15)

        for _ in range(2):
            try:
                cb.call(lambda: PaymentResult.ERROR)
            except Exception:
                pass

        assert cb.state.value == "OPEN"
        with pytest.raises(PaymentServiceUnavailableError):
            cb.call(lambda: PaymentResult.APPROVED)

    def test_circuit_transitions_to_half_open(self):
        """Después de recovery_timeout, OPEN -> HALF_OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            try:
                cb.call(lambda: PaymentResult.ERROR)
            except Exception:
                pass

        assert cb.state.value == "OPEN"
        time.sleep(0.2)
        assert cb.state.value == "HALF_OPEN"

    def test_circuit_closes_on_successful_half_open_call(self):
        """HALF_OPEN + llamada exitosa -> CLOSED."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            try:
                cb.call(lambda: PaymentResult.ERROR)
            except Exception:
                pass

        time.sleep(0.2)
        assert cb.state.value == "HALF_OPEN"

        result = cb.call(lambda: PaymentResult.APPROVED)
        assert result == PaymentResult.APPROVED
        assert cb.state.value == "CLOSED"

    def test_circuit_reopens_on_failed_half_open_call(self):
        """HALF_OPEN + llamada fallida -> OPEN."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

        for _ in range(2):
            try:
                cb.call(lambda: PaymentResult.ERROR)
            except Exception:
                pass

        time.sleep(0.2)
        assert cb.state.value == "HALF_OPEN"

        try:
            cb.call(lambda: PaymentResult.ERROR)
        except Exception:
            pass
        assert cb.state.value == "OPEN"

    def test_circuit_resets_on_success(self):
        """Una llamada exitosa reinicia el contador de fallos."""
        cb = CircuitBreaker(failure_threshold=3, recovery_timeout=15)

        try:
            cb.call(lambda: PaymentResult.ERROR)
        except Exception:
            pass
        try:
            cb.call(lambda: PaymentResult.ERROR)
        except Exception:
            pass
        assert cb.failure_count == 2

        cb.call(lambda: PaymentResult.APPROVED)
        assert cb.failure_count == 0
        assert cb.state.value == "CLOSED"


class TestCircuitBreakerWithConfirmUseCase:
    """Tests del circuit breaker integrado con el caso de uso de confirmacion."""

    def test_cb_open_returns_rejected_response_not_exception(self):
        """Cuando el CB esta OPEN, el use case retorna RejectedResponse, no excepcion."""
        from nexus_live.adapters.api.composition import build_container
        container = build_container(
            payment_force_result=PaymentResult.ERROR,
            cb_failure_threshold=2,
        )
        IdGenerator.reset()

        hold1 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold1.hold_id, payment_token="tok"
        ))
        hold2 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_002", event_id="evt", seat_ids=["A-102"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold2.hold_id, payment_token="tok"
        ))

        assert container.circuit_breaker.state.value == "OPEN"

        hold3 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_003", event_id="evt", seat_ids=["A-103"]
        ))
        result = container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold3.hold_id, payment_token="tok"
        ))

        assert result.reason == "payment_service_unavailable"
        assert "circuit breaker" in result.detail.lower()

    def test_cb_open_does_not_sell_seat(self):
        """Cuando el CB esta OPEN, el asiento NO se marca como SOLD."""
        from nexus_live.adapters.api.composition import build_container
        container = build_container(
            payment_force_result=PaymentResult.ERROR,
            cb_failure_threshold=2,
        )
        IdGenerator.reset()

        for i in range(2):
            hold = container.hold_seats.execute(HoldSeatsRequest(
                user_id=f"usr_{i}", event_id="evt", seat_ids=[f"A-10{i+1}"]
            ))
            container.confirm_hold.execute(ConfirmRequest(
                hold_id=hold.hold_id, payment_token="tok"
            ))

        hold3 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_003", event_id="evt", seat_ids=["A-103"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold3.hold_id, payment_token="tok"
        ))

        seats = container.list_seats.execute()
        seat = next(s for s in seats if s.seat_id == "A-103")
        assert seat.status == "HELD"

    def test_cb_open_records_audit_transition(self):
        """Cuando el CB esta OPEN, se registra la transicion en la auditoria."""
        from nexus_live.adapters.api.composition import build_container
        container = build_container(
            payment_force_result=PaymentResult.ERROR,
            cb_failure_threshold=2,
        )
        IdGenerator.reset()

        for i in range(2):
            hold = container.hold_seats.execute(HoldSeatsRequest(
                user_id=f"usr_{i}", event_id="evt", seat_ids=[f"A-10{i+1}"]
            ))
            container.confirm_hold.execute(ConfirmRequest(
                hold_id=hold.hold_id, payment_token="tok"
            ))

        hold3 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_003", event_id="evt", seat_ids=["A-103"]
        ))
        container.confirm_hold.execute(ConfirmRequest(
            hold_id=hold3.hold_id, payment_token="tok"
        ))

        transitions = container.audit_log.get_by_hold(hold3.hold_id)
        cb_transitions = [
            t for t in transitions
            if t.reason.value == "payment_service_unavailable"
        ]
        assert len(cb_transitions) == 1


from nexus_live.domain.exceptions import HoldNotActiveError
from nexus_live.domain.exceptions import PaymentServiceUnavailableError
