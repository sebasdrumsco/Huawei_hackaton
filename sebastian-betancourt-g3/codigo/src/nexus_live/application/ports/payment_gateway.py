"""Puerto del gateway de pagos."""
from __future__ import annotations

from abc import ABC, abstractmethod

from ...domain.enums import PaymentResult


class PaymentGateway(ABC):
    """Interfaz del proveedor de pagos externo.

    La implementación mock puede producir APPROVED, DECLINED, ERROR
    o TIMEOUT para simular un proveedor inestable.
    """

    @abstractmethod
    def authorize(
        self, payment_token: str, amount: int, currency: str
    ) -> PaymentResult:
        """Autoriza un pago.

        Args:
            payment_token: Token de pago del cliente.
            amount: Monto a cobrar.
            currency: Moneda.

        Returns:
            Resultado del pago (APPROVED, DECLINED, ERROR, TIMEOUT).
        """
