"""Seed Milestone E plans, plan findings, a relative policy, and a valid comparison."""

from __future__ import annotations

import json
from pathlib import Path

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.models import (
    BudgetPolicyArtifact, BudgetPolicyPayload, BudgetRule, ProducerIdentity,
)
from planguard.comparison import compare_runs
from planguard.lab.academic import build_academic_catalog
from planguard.postgres import analyze_plan, import_plan
from planguard.scenario import ScenarioRunner, instantiate
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex

ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = ROOT / "examples" / "store"


def common_family(left, right):
    lt = {item.artifact_id: item for item in left.templates}
    rt = {item.artifact_id: item for item in right.templates}
    left_by_shape = {
        lt[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint: item
        for item in left.families if item.payload.family_scheme_key == "shape-origin.v1"
    }
    right_by_shape = {
        rt[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint: item
        for item in right.families if item.payload.family_scheme_key == "shape-origin.v1"
    }
    shape = sorted(set(left_by_shape) & set(right_by_shape))[0]
    return left_by_shape[shape], right_by_shape[shape]


def main() -> None:
    producer = ProducerIdentity(name="planguard", version="0.5.0", build="milestone-e-seed")
    store = FilesystemArtifactStore(STORE_ROOT)
    catalog = build_academic_catalog(producer=producer)
    catalog.persist(store)
    runner = ScenarioRunner(registry=catalog.registry, store=store, producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    parameters = {
        "scale_profile": "tiny", "tenant_skew": "uniform", "parent_count": 24,
        "relation_fanout": 6, "batch_size": 24, "page_offset": 0,
        "transaction_scope": "autocommit",
    }
    runs = []
    for variant in ("naive", "optimized"):
        instance = instantiate(
            template, binding, parameters=parameters, variant_key=variant,
            mutations=(), seed=12000, producer=producer,
            tags=("milestone-e", "comparison", variant),
        )
        runs.append(runner.run(instance).captured_run.manifest.artifact_id)

    baseline_manifest, baseline = load_analysis_bundle(store, runs[0])
    candidate_manifest, candidate = load_analysis_bundle(store, runs[1])
    baseline_family, candidate_family = common_family(baseline, candidate)
    seq = json.loads((ROOT / "fixtures" / "plans" / "seq_scan.json").read_text())
    idx = json.loads((ROOT / "fixtures" / "plans" / "index_scan.json").read_text())
    baseline_plan, baseline_receipt = import_plan(
        raw_plan=seq, run_id=runs[0], query_family_ref=baseline_family.reference(), producer=producer,
        cache_protocol="cold_then_warm", server_version="16.4",
        database_settings={"random_page_cost": "4", "work_mem": "4MB"},
    )
    candidate_plan, candidate_receipt = import_plan(
        raw_plan=idx, run_id=runs[1], query_family_ref=candidate_family.reference(), producer=producer,
        cache_protocol="cold_then_warm", server_version="16.4",
        database_settings={"random_page_cost": "4", "work_mem": "4MB"},
    )
    for plan, receipt in ((baseline_plan, baseline_receipt), (candidate_plan, candidate_receipt)):
        store.save(plan)
        store.save(receipt)
        evidence, findings = analyze_plan(plan, producer=producer, high_volume_relations=frozenset({"enrollment"}))
        for artifact in (*evidence, *findings):
            store.save(artifact)

    policy = BudgetPolicyArtifact(
        producer=producer,
        payload=BudgetPolicyPayload(
            policy_key="milestone-e.no-query-regression.v1",
            title="Candidate must reduce query count",
            rules=(BudgetRule(
                rule_key="query-count-must-decrease", subject_kind="comparison",
                metric="query_count", operator="less_than", threshold=0,
                disposition="fail", message="Candidate query count must be lower than baseline.",
            ),),
            tags=("relative", "milestone-e"),
        ),
    ).seal()
    store.save(policy)
    # Reload so persisted plans are included through run-scoped store discovery.
    baseline_manifest, baseline = load_analysis_bundle(store, runs[0])
    candidate_manifest, candidate = load_analysis_bundle(store, runs[1])
    report = compare_runs(
        baseline_manifest=baseline_manifest, candidate_manifest=candidate_manifest,
        baseline=baseline, candidate=candidate, loader=store.load, producer=producer,
        baseline_plans=baseline.plan_observations, candidate_plans=candidate.plan_observations,
        relative_policy=policy,
    )
    store.save(report)
    count = ArtifactIndex(STORE_ROOT / "registry.sqlite3").rebuild(store)
    print({"baseline_run_id": runs[0], "candidate_run_id": runs[1], "baseline_plan_id": baseline_plan.artifact_id, "candidate_plan_id": candidate_plan.artifact_id, "comparison_id": report.artifact_id, "comparison_status": str(report.payload.status), "artifact_count": count})


if __name__ == "__main__":
    main()
