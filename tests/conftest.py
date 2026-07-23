from __future__ import annotations

from datetime import UTC, datetime

import pytest

from planguard.artifacts.models import ProducerIdentity


@pytest.fixture
def producer() -> ProducerIdentity:
    return ProducerIdentity(name="planguard-tests", version="0.1.0")


@pytest.fixture
def fixed_time() -> datetime:
    return datetime(2026, 7, 23, 12, 0, tzinfo=UTC)
