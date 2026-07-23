"""Safe parameter shape capture and optional HMAC identity."""

from __future__ import annotations

import hashlib
import hmac
from collections.abc import Mapping, Sequence, Set
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from planguard.artifacts.models import ParameterCaptureMode, ParameterDescriptor
from planguard.canonical import canonical_json_bytes


def _safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, (date, datetime, Decimal)):
        return str(value)
    if isinstance(value, bytes):
        return {"bytes_length": len(value), "sha256": hashlib.sha256(value).hexdigest()}
    return repr(value)


def _descriptor(
    value: Any,
    *,
    mode: ParameterCaptureMode,
    hmac_key: bytes | None,
) -> ParameterDescriptor:
    container: str | None = None
    length: int | None = None
    type_name = type(value).__name__
    if isinstance(value, Mapping):
        container = "mapping"
        length = len(value)
    elif isinstance(value, tuple):
        container = "tuple"
        length = len(value)
    elif isinstance(value, list):
        container = "list"
        length = len(value)
    elif isinstance(value, (set, frozenset)):
        container = "set"
        length = len(value)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        container = "sequence"
        try:
            length = len(value)
        except TypeError:
            length = None

    safe = _safe_value(value)
    value_hash: str | None = None
    preserved = None
    if mode == ParameterCaptureMode.SHAPE_AND_HASH and hmac_key is not None:
        digest = hmac.new(hmac_key, canonical_json_bytes(safe), hashlib.sha256).hexdigest()
        value_hash = f"hmac-sha256:{digest}"
    elif mode == ParameterCaptureMode.PRESERVE:
        preserved = safe

    return ParameterDescriptor(
        type_name=type_name,
        container=container,
        length=length,
        value_hash=value_hash,
        preserved_value=preserved,
    )


def capture_parameters(
    params: Any,
    *,
    mode: ParameterCaptureMode,
    hmac_key: bytes | None,
) -> tuple[ParameterDescriptor, ...]:
    if mode == ParameterCaptureMode.NONE or params is None:
        return ()
    if isinstance(params, Mapping):
        values = [params[key] for key in sorted(params, key=str)]
    elif isinstance(params, (list, tuple)):
        values = list(params)
    else:
        values = [params]
    return tuple(_descriptor(value, mode=mode, hmac_key=hmac_key) for value in values)


def binding_fingerprint(descriptors: tuple[ParameterDescriptor, ...]) -> str | None:
    if not descriptors:
        return "binding:none"
    material = [
        {
            "type_name": item.type_name,
            "container": item.container,
            "length": item.length,
            "value_hash": item.value_hash,
            "preserved_value": item.preserved_value,
        }
        for item in descriptors
    ]
    return f"binding:{hashlib.sha256(canonical_json_bytes(material)).hexdigest()}"
