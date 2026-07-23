"""Immutable content-addressed filesystem artifact store."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from planguard.artifacts.codec import ArtifactCodec, default_codec
from planguard.artifacts.models import ArtifactDocument
from planguard.errors import ArtifactIntegrityError, ArtifactNotFoundError
from planguard.ids import validate_artifact_id
from planguard.store.base import ArtifactRecord


class FilesystemArtifactStore:
    def __init__(self, root: str | Path, *, codec: ArtifactCodec | None = None) -> None:
        self.root = Path(root)
        self.codec = codec or default_codec
        self.objects_root = self.root / "objects" / "sha256"
        self.artifacts_root = self.root / "artifacts"
        self.index_root = self.root / "index"
        self.objects_root.mkdir(parents=True, exist_ok=True)
        self.artifacts_root.mkdir(parents=True, exist_ok=True)
        self.index_root.mkdir(parents=True, exist_ok=True)

    def _object_path(self, qualified_hash: str) -> Path:
        algorithm, digest = qualified_hash.split(":", 1)
        if algorithm != "sha256" or len(digest) != 64:
            raise ArtifactIntegrityError("Unsupported or malformed content hash")
        return self.objects_root / digest[:2] / f"{digest}.json"

    def _artifact_path(self, artifact_id: str) -> Path:
        validate_artifact_id(artifact_id)
        return self.artifacts_root / f"{artifact_id}.json"

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass

    def save(self, artifact: ArtifactDocument[Any]) -> ArtifactRecord:
        sealed = self.codec.seal(artifact)
        if sealed.content_hash is None:
            raise ArtifactIntegrityError("Codec failed to seal artifact")
        encoded = self.codec.encode(sealed, pretty=True)
        object_path = self._object_path(sealed.content_hash)
        artifact_path = self._artifact_path(sealed.artifact_id)

        if object_path.exists():
            existing = self.codec.decode(object_path.read_bytes())
            if existing.content_hash != sealed.content_hash:
                raise ArtifactIntegrityError(
                    "Object path contains content with a different hash",
                    {"path": str(object_path)},
                )
        else:
            self._atomic_write(object_path, encoded)

        if artifact_path.exists():
            existing = self.codec.decode(artifact_path.read_bytes())
            if existing.content_hash != sealed.content_hash:
                raise ArtifactIntegrityError(
                    "Artifact ID is immutable and already points to different content",
                    {
                        "artifact_id": sealed.artifact_id,
                        "existing_hash": existing.content_hash,
                        "candidate_hash": sealed.content_hash,
                    },
                )
        else:
            self._atomic_write(artifact_path, encoded)

        self._write_index_record(sealed, artifact_path)
        return self._record_for(sealed, artifact_path)

    def _write_index_record(self, artifact: ArtifactDocument[Any], artifact_path: Path) -> None:
        if artifact.content_hash is None:
            raise ArtifactIntegrityError("Cannot index an unsealed artifact")
        record = {
            "artifact_id": artifact.artifact_id,
            "artifact_kind": artifact.artifact_kind,
            "schema_version": artifact.schema_version,
            "content_hash": artifact.content_hash,
            "created_at": artifact.created_at.isoformat(),
            "path": str(artifact_path.relative_to(self.root)),
        }
        path = self.index_root / f"{artifact.artifact_id}.json"
        self._atomic_write(
            path,
            (json.dumps(record, sort_keys=True, indent=2) + "\n").encode("utf-8"),
        )

    @staticmethod
    def _record_for(artifact: ArtifactDocument[Any], path: Path) -> ArtifactRecord:
        if artifact.content_hash is None:
            raise ArtifactIntegrityError("Cannot create a record for an unsealed artifact")
        return ArtifactRecord(
            artifact_id=artifact.artifact_id,
            artifact_kind=artifact.artifact_kind,
            schema_version=artifact.schema_version,
            content_hash=artifact.content_hash,
            created_at=artifact.created_at,
            path=path,
        )

    def load(self, artifact_id: str) -> ArtifactDocument[Any]:
        path = self._artifact_path(artifact_id)
        if not path.exists():
            raise ArtifactNotFoundError(artifact_id)
        return self.codec.decode(path.read_bytes())

    def load_by_hash(self, qualified_hash: str) -> ArtifactDocument[Any]:
        path = self._object_path(qualified_hash)
        if not path.exists():
            raise ArtifactNotFoundError(qualified_hash.replace(":", "_"))
        return self.codec.decode(path.read_bytes())

    def list(self, *, artifact_kind: str | None = None) -> tuple[ArtifactRecord, ...]:
        records: list[ArtifactRecord] = []
        for path in self.artifacts_root.glob("*.json"):
            try:
                artifact = self.codec.decode(path.read_bytes())
            except Exception:
                # Corrupt objects are deliberately omitted from normal listing and can be
                # surfaced by verify_all() or the API's diagnostics endpoint later.
                continue
            if artifact_kind is not None and artifact.artifact_kind != artifact_kind:
                continue
            records.append(self._record_for(artifact, path))
        records.sort(key=lambda item: (item.created_at, item.artifact_id), reverse=True)
        return tuple(records)

    def verify(self, artifact_id: str) -> bool:
        try:
            artifact = self.load(artifact_id)
        except Exception:
            return False
        if artifact.content_hash is None:
            return False
        object_path = self._object_path(artifact.content_hash)
        if not object_path.exists():
            return False
        try:
            object_artifact = self.codec.decode(object_path.read_bytes())
        except Exception:
            return False
        return object_artifact.content_hash == artifact.content_hash

    def verify_all(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for path in self.artifacts_root.glob("*.json"):
            artifact_id = path.stem
            results[artifact_id] = self.verify(artifact_id)
        return results

    def import_bytes(self, raw: bytes) -> ArtifactRecord:
        artifact = self.codec.decode(raw)
        return self.save(artifact)

    def rebuild_index(self) -> int:
        for path in self.index_root.glob("*.json"):
            path.unlink()
        count = 0
        for record in self.list():
            artifact = self.load(record.artifact_id)
            self._write_index_record(artifact, record.path)
            count += 1
        return count
