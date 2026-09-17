"""Gateway de pagos mock con circuit breaker.

Simula un proveedor de pagos inestable que puede producir:
    APPROVED  (~70%)
    DECLINED  (~10%)
    ERROR     (~10%)
    TIMEOUT   (~10%)

El circuit breaker envuelve las llamadas para proteger el sistema
cuando el proveedor falla repetidamente.
"""
from __future__ import annotations

import random
import time
from typing import Optional

from ..application.ports.payment_gateway import PaymentGateway
from ..domain.enums import PaymentResult
from .circuit_breaker import CircuitBreaker


class MockPaymentGateway(PaymentGateway):
    """Proveedor de pagos mock.

    Permite controlar el comportamiento para demostrar los escenarios:
    - Forzar un resultado específico (para tests).
    - Modo aleatorio (para simulación realista).
    - Latencia simulada para TIMEOUT.
    """

    def __init__(
        self,
        circuit_breaker: Optional[CircuitBreaker] = None,
        force_result: Optional[PaymentResult] = None,
        timeout_delay: float = 2.5,
        seed: Optional[int] = None,
    ):
        self._cb = circuit_breaker or CircuitBreaker()
        self._force_result = force_result
        self._timeout_delay = timeout_delay
        self._rng = random.Random(seed)

    @property
    def circuit_breaker(self) -> CircuitBreaker:
        return self._cb

    def authorize(
        self, payment_token: str, amount: int, currency: str
    ) -> PaymentResult:
        """Autoriza un pago a través del circuit breaker.

        Raises:
            Exception: si el circuit breaker está OPEN.
        """
        return self._cb.call(
            lambda: self._do_authorize(payment_token, amount, currency)
        )

    def _do_authorize(
        self, payment_token: str, amount: int, currency: str
    ) -> PaymentResult:
        """Realiza la autorización simulada."""
        if self._force_result is not None:
            result = self._force_result
        else:
            roll = self._rng.random()
            if roll < 0.70:
                result = PaymentResult.APPROVED
            elif roll < 0.80:
                result = PaymentResult.DECLINED
            elif roll < 0.90:
                result = PaymentResult.ERROR
            else:
                result = PaymentResult.TIMEOUT

        if result == PaymentResult.TIMEOUT:
            time.sleep(self._timeout_delay)

        return result

    def set_force_result(self, result: Optional[PaymentResult]) -> None:
        """Cambia el resultado forzado (None = modo aleatorio)."""
        self._force_result = result
