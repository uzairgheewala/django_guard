"""Artifact store contracts."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from planguard.artifacts.models import ArtifactDocument


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    artifact_id: str
    artifact_kind: str
    schema_version: str
    content_hash: str
    created_at: datetime
    path: Path


class ArtifactStore(Protocol):
    def save(self, artifact: ArtifactDocument[Any]) -> ArtifactRecord: ...

    def load(self, artifact_id: str) -> ArtifactDocument[Any]: ...

    def list(self, *, artifact_kind: str | None = None) -> tuple[ArtifactRecord, ...]: ...

    def verify(self, artifact_id: str) -> bool: ...
