"""Tests FASE 2 - Concurrencia segura e idempotencia.

Cubre:
    - 100 solicitudes concurrentes por 1 asiento = 1 ganador, 99 rechazadas.
    - Idempotencia: misma clave + mismo payload = mismo resultado.
    - Conflicto de idempotencia: misma clave + payload diferente = error.
    - Overselling = 0 bajo concurrencia.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from nexus_live.application.dto import HoldSeatsRequest
from nexus_live.domain.exceptions import IdempotencyConflictError
from nexus_live.domain.services import IdGenerator


class TestConcurrentReservation:
    """Tests de concurrencia segura (evitar double booking)."""

    def test_100_users_1_seat_exactly_1_winner(self, container):
        """100 usuarios intentan reservar el mismo asiento simultáneamente.

        Resultado esperado:
            1 HOLD exitoso
            99 solicitudes rechazadas
            0 overselling
        """
        IdGenerator.reset()
        num_users = 100
        seat_id = "VIP-A-001"
        results = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_users)

        def attempt(user_index):
            request = HoldSeatsRequest(
                user_id=f"usr_{user_index:04d}",
                event_id="aurora-bogota-2026",
                seat_ids=[seat_id],
            )
            barrier.wait()
            response = container.hold_seats.execute(request)
            with results_lock:
                results.append(response)
            return response

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [executor.submit(attempt, i) for i in range(num_users)]
            for f in as_completed(futures):
                f.result()

        winners = [r for r in results if hasattr(r, "hold_id")]
        rejected = [r for r in results if not hasattr(r, "hold_id")]

        assert len(winners) == 1, f"Expected 1 winner, got {len(winners)}"
        assert len(rejected) == 99, f"Expected 99 rejected, got {len(rejected)}"
        assert len(results) == 100

    def test_20_users_1_seat_1_winner(self, container):
        """20 usuarios intentan reservar el mismo asiento."""
        IdGenerator.reset()
        result = container.simulate_race.execute(
            seat_id="VIP-A-001",
            event_id="aurora-bogota-2026",
            num_users=20,
        )
        assert result.winners == 1
        assert result.rejected == 19
        assert result.total_requests == 20

    def test_no_overselling_with_multiple_seats(self, container):
        """Dos usuarios intentan reservar los mismos 2 asientos simultáneamente."""
        IdGenerator.reset()
        seat_ids = ["A-101", "A-102"]
        results = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(2)

        def attempt(user_id):
            request = HoldSeatsRequest(
                user_id=user_id, event_id="evt", seat_ids=seat_ids
            )
            barrier.wait()
            response = container.hold_seats.execute(request)
            with results_lock:
                results.append(response)
            return response

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(attempt, "usr_A"),
                executor.submit(attempt, "usr_B"),
            ]
            for f in as_completed(futures):
                f.result()

        winners = [r for r in results if hasattr(r, "hold_id")]
        assert len(winners) == 1


class TestIdempotency:
    """Tests de idempotencia (FASE 2, Requisito 2)."""

    def test_same_key_same_payload_returns_same_result(self, container):
        """Escenario D: misma Idempotency-Key + mismo payload = mismo resultado."""
        IdGenerator.reset()
        request = HoldSeatsRequest(
            user_id="usr_10482",
            event_id="aurora-bogota-2026",
            seat_ids=["VIP-A-001"],
            idempotency_key="reserve-usr10482-001",
        )
        result1 = container.hold_seats.execute(request)
        result2 = container.hold_seats.execute(request)

        assert result1.hold_id == result2.hold_id
        assert result1.status == result2.status

    def test_same_key_different_payload_raises_conflict(self, container):
        """Escenario E: misma key + payload diferente = IDEMPOTENCY_CONFLICT."""
        IdGenerator.reset()
        request1 = HoldSeatsRequest(
            user_id="usr_10482",
            event_id="aurora-bogota-2026",
            seat_ids=["VIP-A-001"],
            idempotency_key="reserve-usr10482-001",
        )
        container.hold_seats.execute(request1)

        request2 = HoldSeatsRequest(
            user_id="usr_10482",
            event_id="aurora-bogota-2026",
            seat_ids=["VIP-A-002"],
            idempotency_key="reserve-usr10482-001",
        )
        with pytest.raises(IdempotencyConflictError):
            container.hold_seats.execute(request2)

    def test_different_keys_create_different_holds(self, container):
        """Diferentes claves de idempotencia crean diferentes holds."""
        IdGenerator.reset()
        r1 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-101"], idempotency_key="key-1",
        ))
        r2 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-102"], idempotency_key="key-2",
        ))
        assert r1.hold_id != r2.hold_id

    def test_idempotency_with_reordered_seats(self, container):
        """El orden de seat_ids no afecta el hash de idempotencia."""
        IdGenerator.reset()
        r1 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-101", "A-102"], idempotency_key="key-reorder",
        ))
        r2 = container.hold_seats.execute(HoldSeatsRequest(
            user_id="usr_001", event_id="evt",
            seat_ids=["A-102", "A-101"], idempotency_key="key-reorder",
        ))
        assert r1.hold_id == r2.hold_id
