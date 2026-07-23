"""Time helpers used by artifact models."""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return an aware UTC timestamp."""

    return datetime.now(UTC)


def semantic_epoch() -> datetime:
    """Stable timestamp for content-addressed semantic definitions.

    Event artifacts use utc_now(); reusable definitions and deterministic
    instances use this epoch so their complete serialized identity is stable.
    """

    return datetime(1970, 1, 1, tzinfo=UTC)
