"""Circuit Breaker para el proveedor de pagos.

Estados:
    CLOSED    -> las llamadas pasan normalmente.
    OPEN      -> no se hacen llamadas; se retorna PAYMENT_SERVICE_UNAVAILABLE.
    HALF_OPEN -> se permite una llamada de prueba.

Parámetros configurables:
    failure_threshold: fallos consecutivos para abrir (default 3).
    recovery_timeout: segundos en OPEN antes de HALF_OPEN (default 15).
    half_open_max_calls: llamadas de prueba en HALF_OPEN (default 1).

El circuit breaker envuelve al PaymentGateway real y decide si
las llamadas proceden o se rechazan rápidamente.
"""
from __future__ import annotations

import threading
import time
from typing import Optional

from ..domain.enums import CircuitState, PaymentResult


class CircuitBreaker:
    """Circuit breaker thread-safe para proteger llamadas a servicios externos.

    Uso:
        cb = CircuitBreaker()
        result = cb.call(lambda: gateway.authorize(token, amount, currency))
        if cb.state == CircuitState.OPEN:
            # servicio no disponible
    """

    def __init__(
        self,
        failure_threshold: int = 3,
        recovery_timeout: float = 15.0,
        half_open_max_calls: int = 1,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        """Estado actual del circuit breaker (con transición automática OPEN->HALF_OPEN)."""
        with self._lock:
            self._maybe_transition_to_half_open()
            return self._state

    @property
    def failure_count(self) -> int:
        with self._lock:
            return self._failure_count

    def call(self, operation: callable) -> PaymentResult:
        """Ejecuta una operación a través del circuit breaker.

        Args:
            operation: Callable que retorna un PaymentResult.

        Returns:
            PaymentResult de la operación.

        Raises:
            Exception: con mensaje "Circuit breaker is OPEN" si el
                circuit está OPEN y no se permite la llamada.
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                self._maybe_transition_to_half_open()

            if self._state == CircuitState.OPEN:
                raise Exception("Circuit breaker is OPEN")

            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self._half_open_max_calls:
                    raise Exception("Circuit breaker is OPEN (HALF_OPEN limit reached)")
                self._half_open_calls += 1

        try:
            result = operation()
        except Exception:
            self._on_failure()
            raise
        else:
            if result in (PaymentResult.APPROVED, PaymentResult.DECLINED):
                self._on_success()
            else:
                self._on_failure()
            return result

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
            elif self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN

    def _maybe_transition_to_half_open(self) -> None:
        """Transición automática de OPEN a HALF_OPEN tras el recovery_timeout."""
        if (
            self._state == CircuitState.OPEN
            and self._last_failure_time is not None
            and (time.monotonic() - self._last_failure_time) >= self._recovery_timeout
        ):
            self._state = CircuitState.HALF_OPEN
            self._half_open_calls = 0

    def reset(self) -> None:
        """Reinicia el circuit breaker a CLOSED (para tests)."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0

    def to_dict(self) -> dict:
        """Serializa el estado del circuit breaker."""
        with self._lock:
            self._maybe_transition_to_half_open()
            return {
                "state": self._state.value,
                "failure_count": self._failure_count,
                "failure_threshold": self._failure_threshold,
                "recovery_timeout": self._recovery_timeout,
            }
