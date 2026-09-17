"""Esquemas Pydantic para validación de requests/responses de la API."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class HoldSeatsRequestSchema(BaseModel):
    """Esquema de solicitud de reserva."""
    user_id: str = Field(..., description="ID del usuario")
    event_id: str = Field(..., description="ID del evento")
    seat_ids: list[str] = Field(..., min_length=1, description="IDs de asientos")


class ConfirmRequestSchema(BaseModel):
    """Esquema de solicitud de confirmación."""
    hold_id: str = Field(..., description="ID del hold a confirmar")
    payment_token: str = Field(..., description="Token de pago")


class HoldResponseSchema(BaseModel):
    """Esquema de respuesta de reserva."""
    hold_id: str
    user_id: str
    event_id: str
    seat_ids: list[str]
    status: str
    total: int
    currency: str
    expires_at: datetime
    remaining_seconds: int


class ConfirmResponseSchema(BaseModel):
    """Esquema de respuesta de confirmación."""
    confirmation_id: Optional[str] = None
    hold_id: Optional[str] = None
    user_id: Optional[str] = None
    seat_ids: Optional[list[str]] = None
    total: Optional[int] = None
    currency: Optional[str] = None
    status: str
    payment_result: Optional[str] = None


class RejectedSchema(BaseModel):
    """Esquema de respuesta de rechazo."""
    status: str = "REJECTED"
    reason: str
    detail: Optional[str] = None


class SeatSchema(BaseModel):
    """Esquema de asiento."""
    seat_id: str
    section: str
    price: int
    currency: str
    status: str


class RaceRequestSchema(BaseModel):
    """Esquema de solicitud de simulación de carrera."""
    seat_id: str
    event_id: str = "aurora-bogota-2026"
    num_users: int = Field(20, ge=2, le=500)


class RaceResultSchema(BaseModel):
    """Esquema de resultado de carrera."""
    seat_id: str
    total_requests: int
    winners: int
    rejected: int
    winner_hold_id: Optional[str] = None


class TransitionSchema(BaseModel):
    """Esquema de transición de trazabilidad."""
    hold_id: Optional[str] = None
    seat_id: str
    user_id: Optional[str] = None
    from_state: str
    to_state: str
    reason: str
    timestamp: datetime


class CircuitBreakerSchema(BaseModel):
    """Esquema del estado del circuit breaker."""
    state: str
    failure_count: int
    failure_threshold: int
    recovery_timeout: float
