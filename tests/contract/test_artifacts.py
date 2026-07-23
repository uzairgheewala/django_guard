from __future__ import annotations

import json

import pytest

from planguard.artifacts.codec import build_default_codec
from planguard.artifacts.models import (
    CapturePolicyArtifact,
    CapturePolicyPayload,
    EnvironmentProfileArtifact,
    EnvironmentProfilePayload,
    Provenance,
)
from planguard.errors import ArtifactIntegrityError


def test_artifact_seal_round_trip(producer, fixed_time) -> None:
    codec = build_default_codec()
    artifact = CapturePolicyArtifact(
        artifact_id="cap_contract_test",
        created_at=fixed_time,
        producer=producer,
        payload=CapturePolicyPayload(policy_key="test.v1"),
        extensions={"example.test": {"enabled": True}},
    )
    encoded = codec.encode(artifact, pretty=True)
    decoded = codec.decode(encoded)

    assert decoded.artifact_id == artifact.artifact_id
    assert decoded.verify_integrity()
    assert decoded.extensions["example.test"]["enabled"] is True
    assert encoded.endswith(b"\n")


def test_tampering_is_detected(producer, fixed_time) -> None:
    codec = build_default_codec()
    artifact = EnvironmentProfileArtifact(
        artifact_id="env_tamper_test",
        created_at=fixed_time,
        producer=producer,
        payload=EnvironmentProfilePayload(python_version="3.13.5"),
    )
    data = json.loads(codec.encode(artifact))
    data["payload"]["python_version"] = "0.0.0"
    with pytest.raises(ArtifactIntegrityError):
        codec.decode(json.dumps(data))


def test_reference_carries_integrity_identity(producer, fixed_time) -> None:
    codec = build_default_codec()
    artifact = codec.seal(
        CapturePolicyArtifact(
            artifact_id="cap_reference_test",
            created_at=fixed_time,
            producer=producer,
            provenance=Provenance(code_revision="git:abc"),
            payload=CapturePolicyPayload(policy_key="reference.v1"),
        )
    )
    reference = artifact.reference()
    assert reference.artifact_id == "cap_reference_test"
    assert reference.content_hash == artifact.content_hash
    assert reference.schema_version == "planguard.capture-policy.v1"
