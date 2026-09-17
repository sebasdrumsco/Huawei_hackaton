"""Test de race condition real (Bono B).

Demuestra con threads reales que N solicitudes simultáneas
sobre 1 asiento producen exactamente 1 ganador.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from nexus_live.adapters.api.composition import build_container
from nexus_live.application.dto import HoldSeatsRequest
from nexus_live.domain.services import IdGenerator


def test_race_200_users_1_seat():
    """200 solicitudes simultaneas -> 1 asiento -> 1 ganador."""
    IdGenerator.reset()
    container = build_container()
    num_users = 200
    seat_id = "VIP-A-001"
    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(num_users)

    def attempt(user_index):
        request = HoldSeatsRequest(
            user_id=f"usr_race_{user_index:04d}",
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

    assert len(winners) == 1, f"Expected exactly 1 winner, got {len(winners)}"
    assert len(rejected) == 199, f"Expected 199 rejected, got {len(rejected)}"


def test_race_50_users_2_seats():
    """50 usuarios intentan reservar los mismos 2 asientos -> 1 ganador."""
    IdGenerator.reset()
    container = build_container()
    num_users = 50
    seat_ids = ["A-101", "A-102"]
    results = []
    results_lock = threading.Lock()
    barrier = threading.Barrier(num_users)

    def attempt(user_index):
        request = HoldSeatsRequest(
            user_id=f"usr_{user_index:04d}",
            event_id="evt",
            seat_ids=seat_ids,
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
    assert len(winners) == 1
