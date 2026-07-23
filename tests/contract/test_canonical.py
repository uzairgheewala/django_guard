from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from planguard.canonical import canonical_json_bytes, content_hash


def test_mapping_order_does_not_change_canonical_bytes() -> None:
    first = {"b": 2, "a": {"y": 2, "x": 1}}
    second = {"a": {"x": 1, "y": 2}, "b": 2}
    assert canonical_json_bytes(first) == canonical_json_bytes(second)
    assert content_hash(first) == content_hash(second)


def test_sets_have_stable_ordering() -> None:
    assert canonical_json_bytes({"values": {"z", "a", "m"}}) == canonical_json_bytes(
        {"values": {"m", "z", "a"}}
    )


def test_timestamp_decimal_and_unicode_profile() -> None:
    value = {
        "timestamp": datetime(2026, 7, 23, 12, 0, 1, 12, tzinfo=UTC),
        "decimal": Decimal("12.3400"),
        "label": "Karachi → San Diego",
    }
    assert canonical_json_bytes(value) == (
        b'{"decimal":"12.34","label":"Karachi \xe2\x86\x92 San Diego",'
        b'"timestamp":"2026-07-23T12:00:01.000012Z"}'
    )


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValueError, match="Naive datetimes"):
        canonical_json_bytes({"timestamp": datetime(2026, 7, 23, 12, 0)})
