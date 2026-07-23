"""Artifact identity helpers."""

from __future__ import annotations

import hashlib
import re
import uuid

_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}_[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")
_PREFIX_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,31}$")


def new_artifact_id(prefix: str = "art") -> str:
    """Create a globally unique event-like artifact identifier."""

    if not _PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError(f"Invalid artifact ID prefix: {prefix}")
    return f"{prefix}_{uuid.uuid4().hex}"


def content_derived_id(prefix: str, canonical_bytes: bytes, length: int = 24) -> str:
    """Create a stable identifier for immutable semantic content."""

    if not _PREFIX_PATTERN.fullmatch(prefix):
        raise ValueError(f"Invalid artifact ID prefix: {prefix}")
    digest = hashlib.sha256(canonical_bytes).hexdigest()[:length]
    return f"{prefix}_{digest}"


def validate_artifact_id(value: str) -> str:
    if not _ID_PATTERN.fullmatch(value):
        raise ValueError(
            "Artifact IDs must be '<lowercase_prefix>_<safe-id>' and contain only "
            "letters, numbers, dots, underscores, or hyphens after the separator."
        )
    return value
