"""Modelos del dominio: Seat, Hold, Confirmation y Transition.

Estas entidades encapsulan las reglas de negocio y las transiciones
de estado válidas. No dependen de ninguna infraestructura externa.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .enums import HoldStatus, SeatStatus, TransitionReason


@dataclass
class Seat:
    """Asiento del evento.

    Atributos:
        seat_id: Identificador único (ej. "A-101").
        section: Sección del venue (ej. "VIP", "GENERAL").
        price: Precio en enteros (ej. 210000).
        currency: Moneda ISO 4217 (ej. "COP").
        status: Estado actual del asiento.
        held_by: ID del hold que reserva el asiento, o None.
    """
    seat_id: str
    section: str
    price: int
    currency: str
    status: SeatStatus = SeatStatus.AVAILABLE
    held_by: Optional[str] = None

    def is_available(self) -> bool:
        """Indica si el asiento está disponible para reservar."""
        return self.status == SeatStatus.AVAILABLE

    def hold(self, hold_id: str) -> None:
        """Marca el asiento como HELD por un hold.

        Raises:
            ValueError: si el asiento no está AVAILABLE.
        """
        if self.status != SeatStatus.AVAILABLE:
            raise ValueError(
                f"Cannot hold seat {self.seat_id}: status={self.status}"
            )
        self.status = SeatStatus.HELD
        self.held_by = hold_id

    def sell(self) -> None:
        """Marca el asiento como SOLD.

        Raises:
            ValueError: si el asiento no está HELD.
        """
        if self.status != SeatStatus.HELD:
            raise ValueError(
                f"Cannot sell seat {self.seat_id}: status={self.status}"
            )
        self.status = SeatStatus.SOLD
        self.held_by = None

    def release(self) -> None:
        """Libera el asiento volviendo a AVAILABLE.

        Solo aplica si está HELD. Si ya está SOLD o AVAILABLE, no hace nada.
        """
        if self.status == SeatStatus.HELD:
            self.status = SeatStatus.AVAILABLE
            self.held_by = None


@dataclass
class Hold:
    """Reserva temporal de asientos.

    Atributos:
        hold_id: Identificador único del hold.
        user_id: Usuario que crea la reserva.
        event_id: Evento al que pertenecen los asientos.
        seat_ids: Lista de asientos reservados.
        created_at: Timestamp de creación.
        expires_at: Timestamp de expiración (created_at + TTL).
        status: Estado del hold.
        total: Total calculado por el servidor.
        currency: Moneda del total.
    """
    hold_id: str
    user_id: str
    event_id: str
    seat_ids: list[str]
    created_at: datetime
    expires_at: datetime
    status: HoldStatus = HoldStatus.ACTIVE
    total: int = 0
    currency: str = "COP"

    def is_active(self) -> bool:
        """Indica si el hold está activo (no expirado, cancelado ni confirmado)."""
        return self.status == HoldStatus.ACTIVE

    def is_expired(self, now: datetime) -> bool:
        """Indica si el hold ha pasado su tiempo de expiración."""
        return now >= self.expires_at

    def expire(self) -> None:
        """Marca el hold como expirado."""
        self.status = HoldStatus.EXPIRED

    def confirm(self) -> None:
        """Marca el hold como confirmado (compra exitosa)."""
        self.status = HoldStatus.CONFIRMED

    def cancel(self) -> None:
        """Marca el hold como cancelado."""
        self.status = HoldStatus.CANCELLED

    def remaining_seconds(self, now: datetime) -> int:
        """Segundos restantes antes de la expiración."""
        delta = (self.expires_at - now).total_seconds()
        return max(0, int(delta))


@dataclass
class Confirmation:
    """Confirmación de compra tras pago aprobado.

    Atributos:
        confirmation_id: Identificador único.
        hold_id: Hold que se confirmó.
        user_id: Usuario comprador.
        payment_token: Token de pago utilizado.
        total: Total cobrado.
        currency: Moneda del cobro.
        created_at: Timestamp de confirmación.
    """
    confirmation_id: str
    hold_id: str
    user_id: str
    payment_token: str
    total: int
    currency: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class Transition:
    """Registro de trazabilidad de un cambio de estado.

    Permite reconstruir la vida de una reserva y explicar por qué un
    asiento terminó en un estado determinado.
    """
    hold_id: Optional[str]
    seat_id: str
    from_state: SeatStatus
    to_state: SeatStatus
    reason: TransitionReason
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: Optional[str] = None

    def to_dict(self) -> dict:
        """Serializa la transición a diccionario para exportación."""
        return {
            "hold_id": self.hold_id,
            "seat_id": self.seat_id,
            "user_id": self.user_id,
            "from": self.from_state.value,
            "to": self.to_state.value,
            "reason": self.reason.value,
            "timestamp": self.timestamp.isoformat(),
        }
