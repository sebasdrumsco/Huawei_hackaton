"""Configuración de fixtures para los tests."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pytest

from nexus_live.adapters.api.composition import build_container
from nexus_live.domain.models import Seat


@pytest.fixture
def container():
    """Contenedor fresco para cada test."""
    return build_container(ttl_seconds=120, max_seats_per_user=6)


@pytest.fixture
def short_ttl_container():
    """Contenedor con TTL corto para tests de expiración."""
    return build_container(ttl_seconds=2, max_seats_per_user=6)


@pytest.fixture
def seats():
    """Catálogo de asientos de prueba."""
    return [
        Seat(seat_id="A-101", section="GENERAL", price=210000, currency="COP"),
        Seat(seat_id="A-102", section="GENERAL", price=210000, currency="COP"),
        Seat(seat_id="A-103", section="GENERAL", price=210000, currency="COP"),
        Seat(seat_id="VIP-A-001", section="VIP", price=500000, currency="COP"),
        Seat(seat_id="VIP-A-002", section="VIP", price=500000, currency="COP"),
    ]
