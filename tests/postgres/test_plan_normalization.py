from __future__ import annotations

import json
from pathlib import Path

from planguard.artifacts.models import ArtifactReference, PlanCollectionMode, ProducerIdentity
from planguard.postgres import PlanCollectionPolicy, analyze_plan, import_plan, normalize_postgres_plan, observation_from_raw_plan

ROOT = Path(__file__).resolve().parents[2]


def raw(name: str):
    return json.loads((ROOT / "fixtures" / "plans" / name).read_text())


def family_ref() -> ArtifactReference:
    return ArtifactReference(artifact_id="qfam_test_family", artifact_kind="observed_query_family", schema_version="planguard.observed-query-family.v1")


def test_plan_normalization_preserves_semantics_and_unknowns() -> None:
    root_id, nodes, features, metadata = normalize_postgres_plan(raw("nested_loop_spill.json"))
    assert root_id == "plan-node:root"
    assert features.node_count == 4
    assert features.maximum_depth == 2
    assert features.has_disk_spill is True
    assert features.temporary_io_blocks == 260
    assert features.maximum_estimate_error_ratio == 100
    assert features.nested_loop_effective_rows == 200000
    assert metadata["Execution Time"] == 321.0
    assert features.plan_shape_fingerprint.startswith("psh_")


def test_imported_plan_emits_contextual_findings() -> None:
    producer = ProducerIdentity(name="tests", version="1")
    plan = observation_from_raw_plan(
        raw_plan=raw("seq_scan.json"),
        run_id="run_plan_test",
        query_family_ref=family_ref(),
        producer=producer,
    )
    evidence, findings = analyze_plan(plan, producer=producer, high_volume_relations=frozenset({"enrollment"}))
    assert plan.payload.collection.mode == PlanCollectionMode.IMPORTED
    assert plan.payload.collection.analyzed is True
    assert {item.payload.mechanism_key for item in findings} == {"nonselective-access"}
    assert evidence[0].verify_integrity()


def test_plan_collection_policy_rejects_unsafe_analyze() -> None:
    policy = PlanCollectionPolicy(mode=PlanCollectionMode.ANALYZE_SAFE_SELECTS)
    allowed, checks, reason = policy.safety_check("UPDATE student SET active = false")
    assert allowed is False
    assert checks["read_only_shape"] is False
    assert "read-only" in (reason or "")

    allowed, checks, reason = policy.safety_check("SELECT nextval('danger')")
    assert allowed is False
    assert checks["volatile_hint_absent"] is False


def test_import_plan_emits_nonexecuting_receipt() -> None:
    producer = ProducerIdentity(name="tests", version="1")
    plan, receipt = import_plan(
        raw_plan=raw("index_scan.json"),
        run_id="run_plan_import",
        query_family_ref=family_ref(),
        producer=producer,
    )
    assert receipt.payload.plan_ref == plan.reference()
    assert receipt.payload.safety_checks == {"source": "imported_json", "executed_sql": False}
    assert receipt.payload.status.value == "collected"
    assert receipt.verify_integrity()
