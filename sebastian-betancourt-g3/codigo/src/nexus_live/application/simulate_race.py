"""Caso de uso: simular carrera de concurrencia (FASE 2).

Lanza N solicitudes concurrentes sobre un mismo asiento para
demostrar que exactamente un usuario gana y el resto son rechazados.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from .dto import HoldSeatsRequest, RaceSimulationResult
from .hold_seats import HoldSeatsUseCase


class SimulateRaceUseCase:
    """Simula una carrera de N usuarios por un mismo asiento.

    Garantiza que el resultado sea:
        1 HOLD exitoso
        N-1 solicitudes rechazadas
        0 overselling
    """

    def __init__(self, hold_use_case: HoldSeatsUseCase):
        self._hold_use_case = hold_use_case

    def execute(
        self,
        seat_id: str,
        event_id: str,
        num_users: int = 100,
    ) -> RaceSimulationResult:
        """Ejecuta la simulación de carrera.

        Args:
            seat_id: Asiento objetivo (ej. "VIP-A-001").
            event_id: Evento.
            num_users: Número de usuarios concurrentes.

        Returns:
            RaceSimulationResult con el resumen de la simulación.
        """
        results: list[dict] = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(num_users)

        def attempt(user_index: int) -> dict:
            user_id = f"usr_race_{user_index:04d}"
            request = HoldSeatsRequest(
                user_id=user_id,
                event_id=event_id,
                seat_ids=[seat_id],
                idempotency_key=f"race-{user_index}",
            )
            barrier.wait()
            response = self._hold_use_case.execute(request)

            is_winner = hasattr(response, "hold_id")
            entry = {
                "user_id": user_id,
                "success": is_winner,
                "hold_id": getattr(response, "hold_id", None),
                "reason": getattr(response, "reason", None),
            }
            with results_lock:
                results.append(entry)
            return entry

        with ThreadPoolExecutor(max_workers=num_users) as executor:
            futures = [
                executor.submit(attempt, i) for i in range(num_users)
            ]
            for future in as_completed(futures):
                future.result()

        winners = [r for r in results if r["success"]]
        rejected = [r for r in results if not r["success"]]

        return RaceSimulationResult(
            seat_id=seat_id,
            total_requests=num_users,
            winners=len(winners),
            rejected=len(rejected),
            winner_hold_id=winners[0]["hold_id"] if winners else None,
            results=results,
        )
