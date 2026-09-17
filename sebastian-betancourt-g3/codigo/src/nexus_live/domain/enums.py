"""Enumeraciones del dominio.

Define los estados válidos de asientos, reservas, resultados de pago
y estados del circuit breaker.
"""
from enum import Enum


class SeatStatus(str, Enum):
    """Estados posibles de un asiento.

    Transiciones válidas:
        AVAILABLE -> HELD  (crear reserva)
        HELD -> SOLD       (confirmar compra)
        HELD -> AVAILABLE  (expirar o liberar reserva)
        SOLD -> (terminal)
    """
    AVAILABLE = "AVAILABLE"
    HELD = "HELD"
    SOLD = "SOLD"


class HoldStatus(str, Enum):
    """Estados posibles de una reserva temporal (HOLD)."""
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentResult(str, Enum):
    """Resultados posibles del proveedor de pagos."""
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    ERROR = "ERROR"
    TIMEOUT = "TIMEOUT"


class CircuitState(str, Enum):
    """Estados del circuit breaker."""
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class TransitionReason(str, Enum):
    """Motivos de transición de estado para trazabilidad."""
    HOLD_CREATED = "hold_created"
    HOLD_EXPIRED = "hold_expired"
    HOLD_RELEASED = "hold_released"
    PAYMENT_APPROVED = "payment_approved"
    PAYMENT_DECLINED = "payment_declined"
    PAYMENT_ERROR = "payment_error"
    PAYMENT_TIMEOUT = "payment_timeout"
    PAYMENT_SERVICE_UNAVAILABLE = "payment_service_unavailable"
