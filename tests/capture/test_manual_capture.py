from __future__ import annotations

from planguard.capture import AnalysisSession
from planguard.policy import QueryPolicy
from planguard.store.filesystem import FilesystemArtifactStore


def test_manual_capture_produces_reloadable_developer_mvp(tmp_path) -> None:
    session = AnalysisSession(
        "manual-test",
        store=tmp_path,
        attach_django=False,
        hmac_key=b"test-key",
        budget_policy=QueryPolicy(
            max_queries=10,
            max_family_executions=3,
            forbid_findings=frozenset({"likely-n-plus-one.v1"}),
        ),
    )
    with session:
        session.record_query("SELECT * FROM parent WHERE id = %s", [1], duration_ms=2)
        for child_id in range(5):
            session.record_query(
                "SELECT * FROM child WHERE id = %s",
                [child_id],
                duration_ms=1,
            )

    assert session.result is not None
    assert session.analysis.summary.payload.query_count == 6
    assert any(item.payload.detector_key == "likely-n-plus-one.v1" for item in session.analysis.findings)
    assert session.analysis.budget_evaluations[0].payload.status == "failed"
    store = FilesystemArtifactStore(tmp_path)
    assert store.verify(session.manifest.artifact_id)
    assert session.manifest.payload.artifact_inventory.by_kind["query_execution"] == 6


def test_query_limit_is_explicit_in_manifest(tmp_path) -> None:
    from planguard.artifacts.models import CaptureLimits, CapturePolicyPayload

    policy = CapturePolicyPayload(
        policy_key="limit.v1",
        limits=CaptureLimits(max_query_count=2),
    )
    with AnalysisSession(
        "limited",
        store=tmp_path,
        attach_django=False,
        capture_policy=policy,
    ) as session:
        for index in range(4):
            session.record_query("SELECT %s", [index])
    assert session.analysis.summary.payload.query_count == 2
    assert session.manifest.payload.capability_status["capture.limit_reached"].state == "partial"
