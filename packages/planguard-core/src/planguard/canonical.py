"""Deterministic JSON canonicalization for PlanGuard artifacts.

This is intentionally a small, documented canonical profile rather than an
implicit reliance on one Pydantic or JSON-library implementation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path, PurePath
from typing import Any, Mapping

from pydantic import BaseModel


def _canonical_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Naive datetimes are not canonicalizable")
    utc_value = value.astimezone(UTC)
    if utc_value.microsecond:
        rendered = utc_value.isoformat(timespec="microseconds")
    else:
        rendered = utc_value.isoformat(timespec="seconds")
    return rendered.replace("+00:00", "Z")


def _canonical_decimal(value: Decimal) -> str:
    if not value.is_finite():
        raise ValueError("Non-finite Decimal values are not canonicalizable")
    normalized = value.normalize()
    rendered = format(normalized, "f")
    if "." in rendered:
        rendered = rendered.rstrip("0").rstrip(".")
    return rendered or "0"


def canonical_data(value: Any) -> Any:
    """Convert supported values into a deterministic JSON-compatible tree."""

    if isinstance(value, BaseModel):
        return canonical_data(value.model_dump(mode="python", exclude_none=False))
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return canonical_data(dataclasses.asdict(value))
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite float values are not canonicalizable")
        # JSON's shortest round-trippable decimal rendering is stable on supported Python.
        return value
    if isinstance(value, Decimal):
        # Decimals are serialized as strings to avoid implementation-specific precision loss.
        return _canonical_decimal(value)
    if isinstance(value, datetime):
        return _canonical_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return canonical_data(value.value)
    if isinstance(value, (Path, PurePath)):
        return value.as_posix()
    if isinstance(value, bytes):
        return {"$bytes_hex": value.hex()}
    if isinstance(value, Mapping):
        output: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Canonical JSON object keys must be strings")
            output[key] = canonical_data(item)
        return output
    if isinstance(value, (list, tuple)):
        return [canonical_data(item) for item in value]
    if isinstance(value, (set, frozenset)):
        canonical_items = [canonical_data(item) for item in value]
        return sorted(canonical_items, key=canonical_json_bytes)
    raise TypeError(f"Unsupported canonical value: {type(value)!r}")


def canonical_json_bytes(value: Any) -> bytes:
    """Serialize a value using PlanGuard's canonical JSON profile."""

    normalized = canonical_data(value)
    text = json.dumps(
        normalized,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def canonical_json_text(value: Any, *, pretty: bool = False) -> str:
    normalized = canonical_data(value)
    if pretty:
        return json.dumps(
            normalized,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            indent=2,
        )
    return canonical_json_bytes(normalized).decode("utf-8")


def content_hash(value: Any) -> str:
    """Return a qualified SHA-256 content hash."""

    return f"sha256:{hashlib.sha256(canonical_json_bytes(value)).hexdigest()}"
