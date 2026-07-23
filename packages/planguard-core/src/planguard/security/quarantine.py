"""Safe quarantine for invalid imported artifact bytes."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True, slots=True)
class QuarantineResult:
    path: Path
    sha256: str
    byte_count: int
    reason: str


def quarantine_bytes(data: bytes, *, quarantine_dir: Path, reason: str) -> QuarantineResult:
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(data).hexdigest()
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = quarantine_dir / f"{timestamp}-{digest[:16]}.artifact.bin"
    path.write_bytes(data)
    metadata = path.with_suffix(path.suffix + ".reason.txt")
    metadata.write_text(reason + "\n", encoding="utf-8")
    return QuarantineResult(path=path, sha256=digest, byte_count=len(data), reason=reason)
