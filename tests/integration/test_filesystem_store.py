from __future__ import annotations

import json

import pytest

from planguard.artifacts.models import CapturePolicyArtifact, CapturePolicyPayload
from planguard.errors import ArtifactIntegrityError
from planguard.store.filesystem import FilesystemArtifactStore


def test_store_is_idempotent_and_content_addressed(tmp_path, producer, fixed_time) -> None:
    store = FilesystemArtifactStore(tmp_path)
    artifact = CapturePolicyArtifact(
        artifact_id="cap_store_test",
        created_at=fixed_time,
        producer=producer,
        payload=CapturePolicyPayload(policy_key="store.v1"),
    )

    first = store.save(artifact)
    second = store.save(artifact)

    assert first.content_hash == second.content_hash
    assert store.verify("cap_store_test")
    assert store.load("cap_store_test").payload.policy_key == "store.v1"
    assert len(tuple((tmp_path / "objects" / "sha256").glob("*/*.json"))) == 1


def test_store_rejects_artifact_id_reuse(tmp_path, producer, fixed_time) -> None:
    store = FilesystemArtifactStore(tmp_path)
    first = CapturePolicyArtifact(
        artifact_id="cap_immutable_test",
        created_at=fixed_time,
        producer=producer,
        payload=CapturePolicyPayload(policy_key="first.v1"),
    )
    second = CapturePolicyArtifact(
        artifact_id="cap_immutable_test",
        created_at=fixed_time,
        producer=producer,
        payload=CapturePolicyPayload(policy_key="second.v1"),
    )
    store.save(first)
    with pytest.raises(ArtifactIntegrityError, match="immutable"):
        store.save(second)


def test_store_detects_corrupt_artifact_pointer(tmp_path, producer, fixed_time) -> None:
    store = FilesystemArtifactStore(tmp_path)
    record = store.save(
        CapturePolicyArtifact(
            artifact_id="cap_corrupt_test",
            created_at=fixed_time,
            producer=producer,
            payload=CapturePolicyPayload(policy_key="corrupt.v1"),
        )
    )
    data = json.loads(record.path.read_text())
    data["payload"]["policy_key"] = "tampered.v1"
    record.path.write_text(json.dumps(data))
    assert not store.verify("cap_corrupt_test")
