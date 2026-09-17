"""Tests FASE 1 - SeatLock: reservas temporales.

Cubre:
    - Crear HOLD exitoso.
    - Reserva todo-o-nada.
    - Segundo usuario no puede reservar asiento en HELD.
    - Expiración automática (TTL).
    - Límite de asientos por usuario.
    - Precio calculado por el servidor.
    - Estados válidos (no se puede modificar arbitrariamente).
    - Casos límite: seat_ids vacío, asiento inexistente, duplicados.
"""
from __future__ import annotations

import time

import pytest

from nexus_live.application.dto import HoldSeatsRequest
from nexus_live.domain.exceptions import (
    DuplicateSeatInRequestError,
    InvalidRequestError,
    SeatNotFoundError,
)
from nexus_live.domain.services import IdGenerator


class TestHoldCreation:
    """Tests de creación de reservas exitosas."""

    def test_create_hold_success(self, container):
        """Escenario A: asiento disponible -> HOLD -> estado HELD."""
        IdGenerator.reset()
        request = HoldSeatsRequest(
            user_id="usr_10482",
            event_id="aurora-bogota-2026",
            seat_ids=["A-101", "A-102"],
        )
        result = container.hold_seats.execute(request)

        assert hasattr(result, "hold_id")
        assert result.status == "HELD"
        assert result.seat_ids == ["A-101", "A-102"]
        assert result.total == 420000
        assert result.currency == "COP"
        assert result.remaining_seconds > 0

    def test_seat_becomes_held_after_reservation(self, container):
        """Los asientos pasan a HELD después de la reserva."""
        container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        seats = container.list_seats.execute()
        seat_101 = next(s for s in seats if s.seat_id == "A-101")
        assert seat_101.status == "HELD"

    def test_price_calculated_by_server(self, container):
        """El precio lo calcula el servidor, no el cliente."""
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["VIP-A-001"]
        ))
        assert result.total == 500000
        assert result.currency == "COP"


class TestAllOrNothing:
    """Tests de reserva todo-o-nada."""

    def test_all_or_nothing_when_one_unavailable(self, container):
        """Si un asiento no está disponible, no se reserva parcialmente."""
        container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))

        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_002", event_id="evt", seat_ids=["A-101", "A-102", "A-103"]
        ))

        assert not hasattr(result, "hold_id")
        assert result.reason == "seat_not_available"

        seats = container.list_seats.execute()
        seat_102 = next(s for s in seats if s.seat_id == "A-102")
        seat_103 = next(s for s in seats if s.seat_id == "A-103")
        assert seat_102.status == "AVAILABLE"
        assert seat_103.status == "AVAILABLE"

    def test_second_user_cannot_reserve_held_seat(self, container):
        """Un segundo usuario no puede reservar un asiento en HELD."""
        container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))

        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_002", event_id="evt", seat_ids=["A-101"]
        ))

        assert result.reason == "seat_not_available"


class TestExpiration:
    """Tests de expiración automática."""

    def test_hold_expires_after_ttl(self, short_ttl_container):
        """Escenario B: HOLD expira y el asiento vuelve a AVAILABLE."""
        container = short_ttl_container
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        assert result.status == "HELD"

        time.sleep(3)

        expired = container.expire_holds.execute()
        assert len(expired) == 1

        seats = container.list_seats.execute()
        seat_101 = next(s for s in seats if s.seat_id == "A-101")
        assert seat_101.status == "AVAILABLE"

    def test_remaining_seconds_decreases(self, short_ttl_container):
        """El tiempo restante disminuye con el tiempo."""
        container = short_ttl_container
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        initial = result.remaining_seconds
        time.sleep(1)
        hold = container.get_hold.execute(result.hold_id)
        assert hold.remaining_seconds < initial


class TestSeatLimit:
    """Tests del límite de asientos por usuario."""

    def test_seat_limit_exceeded(self, container):
        """Un usuario no puede exceder el límite de 6 asientos."""
        container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-101", "A-102", "A-103"],
        ))
        container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["B-001", "B-002", "B-003"],
        ))

        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["B-004"],
        ))

        assert result.reason == "seat_limit_exceeded"

    def test_seat_limit_exactly_at_max(self, container):
        """Un usuario puede tener exactamente el límite de asientos."""
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-101", "A-102", "A-103", "B-001", "B-002", "B-003"],
        ))
        assert hasattr(result, "hold_id")


class TestValidation:
    """Tests de validación de entrada."""

    def test_empty_seat_ids(self, container):
        """seat_ids vacío debe fallar."""
        with pytest.raises(InvalidRequestError):
            container.hold_seats.execute(HoldSeatsRequest(
                user_id="usr_001", event_id="evt", seat_ids=[]
            ))

    def test_nonexistent_seat(self, container):
        """Asiento inexistente debe fallar."""
        with pytest.raises(SeatNotFoundError):
            container.hold_seats.execute(HoldSeatsRequest(
                user_id="usr_001", event_id="evt", seat_ids=["ZZ-999"]
            ))

    def test_duplicate_seat_in_request(self, container):
        """Asiento duplicado en la misma solicitud debe fallar."""
        with pytest.raises(DuplicateSeatInRequestError):
            container.hold_seats.execute(HoldSeatsRequest(
                user_id="usr_001", event_id="evt",
                seat_ids=["A-101", "A-101"],
            ))

    def test_empty_user_id(self, container):
        """user_id vacío debe fallar."""
        with pytest.raises(InvalidRequestError):
            container.hold_seats.execute(HoldSeatsRequest(
                user_id="", event_id="evt", seat_ids=["A-101"]
            ))


class TestReleaseHold:
    """Tests de liberación de reservas."""

    def test_release_hold_returns_seats(self, container):
        """Liberar un HOLD devuelve los asientos a AVAILABLE."""
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        container.release_hold.execute(result.hold_id)

        seats = container.list_seats.execute()
        seat_101 = next(s for s in seats if s.seat_id == "A-101")
        assert seat_101.status == "AVAILABLE"


class TestTrazabilidad:
    """Tests de trazabilidad (transiciones de estado)."""

    def test_transition_recorded_on_hold(self, container):
        """La creación de un HOLD registra la transición AVAILABLE -> HELD."""
        result = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt", seat_ids=["A-101"]
        ))
        transitions = container.audit_log.get_by_hold(result.hold_id)
        assert len(transitions) == 1
        assert transitions[0].from_state.value == "AVAILABLE"
        assert transitions[0].to_state.value == "HELD"
        assert transitions[0].reason.value == "hold_created"
