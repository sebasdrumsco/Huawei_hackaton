"""Objetos de transferencia de datos (DTOs).

Estos objetos representan los datos que entran y salen de los
casos de uso, independientes de cualquier framework web.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class HoldSeatsRequest:
    """Solicitud de reserva de asientos."""
    user_id: str
    event_id: str
    seat_ids: list[str]
    idempotency_key: Optional[str] = None


@dataclass
class HoldResponse:
    """Respuesta de una reserva exitosa."""
    hold_id: str
    user_id: str
    event_id: str
    seat_ids: list[str]
    status: str
    total: int
    currency: str
    expires_at: datetime
    remaining_seconds: int


@dataclass
class ConfirmRequest:
    """Solicitud de confirmación de compra."""
    hold_id: str
    payment_token: str
    idempotency_key: Optional[str] = None


@dataclass
class ConfirmResponse:
    """Respuesta de confirmación de compra."""
    confirmation_id: str
    hold_id: str
    user_id: str
    seat_ids: list[str]
    total: int
    currency: str
    status: str
    payment_result: str


@dataclass
class SeatResponse:
    """Representación de un asiento para la API."""
    seat_id: str
    section: str
    price: int
    currency: str
    status: str


@dataclass
class RaceSimulationResult:
    """Resultado de la simulación de carrera (concurrencia)."""
    seat_id: str
    total_requests: int
    winners: int
    rejected: int
    winner_hold_id: Optional[str] = None
    results: list[dict] = field(default_factory=list)


@dataclass
class RejectedResponse:
    """Respuesta estándar de rechazo."""
    status: str = "REJECTED"
    reason: str = ""
    detail: Optional[str] = None
