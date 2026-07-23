from __future__ import annotations

from planguard.artifacts.models import (
    CapturePolicyArtifact,
    CapturePolicyPayload,
    ParameterCaptureMode,
    ProducerIdentity,
    RawSqlMode,
)
from planguard.security import audit_artifacts, quarantine_bytes, sanitize_artifact, verify_artifact_trust
from planguard.store.filesystem import FilesystemArtifactStore


def test_security_audit_and_sanitization_preserve_schema(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1")
    artifact = CapturePolicyArtifact(
        producer=producer,
        payload=CapturePolicyPayload(
            policy_key="unsafe@example.com",
            raw_sql_mode=RawSqlMode.PRESERVE,
            parameter_capture_mode=ParameterCaptureMode.PRESERVE,
            notes=("Authorization: Bearer abc.def.ghi",),
        ),
        extensions={"example.secret": {"api_key": "secret-value"}},
    ).seal()
    audit = audit_artifacts((artifact,), producer=producer)
    assert str(audit.payload.trust_state) == "untrusted"
    assert audit.payload.findings
    sanitized, receipt = sanitize_artifact(artifact, producer=producer)
    assert sanitized.artifact_kind == artifact.artifact_kind
    assert sanitized.artifact_id != artifact.artifact_id
    assert sanitized.verify_integrity()
    assert receipt.payload.redacted_paths
    re_audit = audit_artifacts((sanitized,), producer=producer)
    assert re_audit.payload.integrity_failed == 0
    assert all(item.category != "parameter_value" for item in re_audit.payload.findings)


def test_store_trust_and_quarantine(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1")
    store = FilesystemArtifactStore(tmp_path / "store")
    artifact = CapturePolicyArtifact(producer=producer, payload=CapturePolicyPayload(policy_key="safe.v1")).seal()
    store.save(artifact)
    trust = verify_artifact_trust(store, (artifact.artifact_id,), producer=producer)
    assert str(trust.payload.trust_state) == "trusted"
    quarantined = quarantine_bytes(b"not-json", quarantine_dir=tmp_path / "quarantine", reason="invalid")
    assert quarantined.path.exists()
    assert quarantined.byte_count == 8


def test_store_quota_assessment(tmp_path) -> None:
    from planguard.security import StoreQuotaPolicy, assess_store_quota
    producer = ProducerIdentity(name="test", version="1")
    store = FilesystemArtifactStore(tmp_path / "quota-store")
    store.save(CapturePolicyArtifact(producer=producer, payload=CapturePolicyPayload(policy_key="one.v1")).seal())
    assessment = assess_store_quota(store, StoreQuotaPolicy(max_artifacts=0, max_total_bytes=10**9, max_single_artifact_bytes=10**9))
    assert assessment.artifact_count == 1
    assert not assessment.accepted
    assert assessment.artifact_count_exceeded
