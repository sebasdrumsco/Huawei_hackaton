"""Servicios del dominio.

Contienen lógica de negocio pura que no pertenece a una entidad
específica pero que opera sobre múltiples entidades del dominio.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone


class IdGenerator:
    """Generador de IDs únicos para holds y confirmaciones.

    Usa un contador interno protegido para garantizar unicidad
    incluso bajo concurrencia.
    """
    _counter: int = 0

    @classmethod
    def hold_id(cls) -> str:
        """Genera un ID de hold con formato hold_XXXXX."""
        cls._counter += 1
        return f"hold_{cls._counter:05X}"

    @classmethod
    def confirmation_id(cls) -> str:
        """Genera un ID de confirmación con formato conf_XXXXX."""
        cls._counter += 1
        return f"conf_{cls._counter:05X}"

    @classmethod
    def reset(cls) -> None:
        """Reinicia el contador (útil para tests)."""
        cls._counter = 0


class PricingService:
    """Servicio de cálculo de precios.

    El precio lo controla el servidor usando el catálogo de asientos.
    El cliente nunca decide el precio final.
    """

    @staticmethod
    def calculate_total(seats: list, currency: str = "COP") -> tuple[int, str]:
        """Calcula el total a partir de los asientos del catálogo.

        Args:
            seats: Lista de entidades Seat del dominio.
            currency: Moneda esperada.

        Returns:
            Tupla (total, currency).

        Raises:
            ValueError: si las monedas no coinciden.
        """
        total = 0
        for seat in seats:
            if seat.currency != currency:
                raise ValueError(
                    f"Currency mismatch for seat {seat.seat_id}: "
                    f"expected {currency}, got {seat.currency}"
                )
            total += seat.price
        return total, currency


class HoldFactory:
    """Fábrica de reservas temporales (HOLDs).

    Encapsula la creación de un hold con TTL configurable.
    """
    DEFAULT_TTL_SECONDS = 120

    @staticmethod
    def create(
        hold_id: str,
        user_id: str,
        event_id: str,
        seat_ids: list[str],
        total: int,
        currency: str,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        now: datetime | None = None,
    ) -> object:
        """Crea un nuevo hold con expiración calculada.

        Args:
            hold_id: ID único del hold.
            user_id: Usuario solicitante.
            event_id: Evento.
            seat_ids: Asientos a reservar.
            total: Total calculado por el servidor.
            currency: Moneda.
            ttl_seconds: Tiempo de vida del hold en segundos.
            now: Timestamp actual (para tests).

        Returns:
            Una entidad Hold.
        """
        from .models import Hold

        if now is None:
            now = datetime.now(timezone.utc)

        return Hold(
            hold_id=hold_id,
            user_id=user_id,
            event_id=event_id,
            seat_ids=list(seat_ids),
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            total=total,
            currency=currency,
        )


class PayloadHasher:
    """Calcula un hash determinista del payload para idempotencia.

    Dos payloads idénticos producen el mismo hash; payloads diferentes
    producen hashes diferentes, permitiendo detectar conflictos.
    """

    @staticmethod
    def hash(user_id: str, event_id: str, seat_ids: list[str]) -> str:
        """Genera un hash del payload de reserva.

        Ordena los seat_ids para que el orden no afecte el hash.
        """
        sorted_seats = sorted(set(seat_ids))
        return f"{user_id}|{event_id}|{','.join(sorted_seats)}"
