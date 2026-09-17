"""Excepciones del dominio.

Cada excepción representa una violación de una regla de negocio.
Se propagan desde el dominio hasta los adaptadores de entrada para
ser traducidas a respuestas HTTP apropiadas.
"""


class DomainError(Exception):
    """Clase base para todas las excepciones del dominio."""


class SeatNotFoundError(DomainError):
    """El asiento solicitado no existe en el catálogo."""

    def __init__(self, seat_id: str):
        super().__init__(f"Seat not found: {seat_id}")
        self.seat_id = seat_id


class SeatNotAvailableError(DomainError):
    """Uno o más asientos no están disponibles para reservar."""

    def __init__(self, seat_ids: list[str]):
        super().__init__(f"Seats not available: {seat_ids}")
        self.seat_ids = seat_ids


class HoldNotFoundError(DomainError):
    """La reserva solicitada no existe."""

    def __init__(self, hold_id: str):
        super().__init__(f"Hold not found: {hold_id}")
        self.hold_id = hold_id


class HoldExpiredError(DomainError):
    """La reserva ya expiró y no puede confirmarse."""

    def __init__(self, hold_id: str):
        super().__init__(f"Hold expired: {hold_id}")
        self.hold_id = hold_id


class HoldAlreadyConfirmedError(DomainError):
    """La reserva ya fue confirmada (vendida)."""

    def __init__(self, hold_id: str):
        super().__init__(f"Hold already confirmed: {hold_id}")
        self.hold_id = hold_id


class HoldNotActiveError(DomainError):
    """La reserva no está activa (expirada, cancelada o confirmada)."""

    def __init__(self, hold_id: str, status: str):
        super().__init__(f"Hold {hold_id} is not active (status={status})")
        self.hold_id = hold_id
        self.status = status


class SeatLimitExceededError(DomainError):
    """El usuario excede el límite de asientos en reservas activas."""

    def __init__(self, limit: int, current: int, requested: int):
        super().__init__(
            f"Seat limit exceeded: limit={limit}, current={current}, requested={requested}"
        )
        self.limit = limit
        self.current = current
        self.requested = requested


class IdempotencyConflictError(DomainError):
    """La clave de idempotencia ya se usó con un payload diferente."""

    def __init__(self, key: str):
        super().__init__(f"Idempotency conflict for key: {key}")
        self.key = key


class PaymentServiceUnavailableError(DomainError):
    """El circuit breaker está OPEN; el servicio de pagos no está disponible."""

    def __init__(self):
        super().__init__("Payment service unavailable (circuit breaker OPEN)")


class InvalidRequestError(DomainError):
    """La solicitud viola validaciones básicas de entrada."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class DuplicateSeatInRequestError(DomainError):
    """La solicitud contiene asientos duplicados."""

    def __init__(self, seat_id: str):
        super().__init__(f"Duplicate seat in request: {seat_id}")
        self.seat_id = seat_id
