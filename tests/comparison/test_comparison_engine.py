from __future__ import annotations

import json
from pathlib import Path

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.models import ProducerIdentity
from planguard.comparison import compare_runs
from planguard.postgres import observation_from_raw_plan
from planguard.store.filesystem import FilesystemArtifactStore

ROOT = Path(__file__).resolve().parents[2]


def test_naive_and_optimized_scenario_compare_with_plan_transition() -> None:
    store = FilesystemArtifactStore(ROOT / "examples" / "store")
    baseline_id = "run_1571fc0ae30640ca9cee4f4473477acd"
    candidate_id = "run_4fb3424ff2c24536a10368179d6851be"
    baseline_manifest, baseline = load_analysis_bundle(store, baseline_id)
    candidate_manifest, candidate = load_analysis_bundle(store, candidate_id)
    producer = ProducerIdentity(name="tests", version="1")
    baseline_templates = {item.artifact_id: item for item in baseline.templates}
    candidate_templates = {item.artifact_id: item for item in candidate.templates}
    common_shapes = {
        baseline_templates[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint
        for item in baseline.families if item.payload.family_scheme_key == "shape-origin.v1"
    } & {
        candidate_templates[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint
        for item in candidate.families if item.payload.family_scheme_key == "shape-origin.v1"
    }
    common_shape = next(iter(common_shapes))
    baseline_family = next(item for item in baseline.families if item.payload.family_scheme_key == "shape-origin.v1" and baseline_templates[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint == common_shape)
    candidate_family = next(item for item in candidate.families if item.payload.family_scheme_key == "shape-origin.v1" and candidate_templates[item.payload.query_template_ref.artifact_id].payload.structural_shape_fingerprint == common_shape)
    seq = json.loads((ROOT / "fixtures" / "plans" / "seq_scan.json").read_text())
    idx = json.loads((ROOT / "fixtures" / "plans" / "index_scan.json").read_text())
    baseline_plan = observation_from_raw_plan(raw_plan=seq, run_id=baseline_id, query_family_ref=baseline_family.reference(), producer=producer)
    candidate_plan = observation_from_raw_plan(raw_plan=idx, run_id=candidate_id, query_family_ref=candidate_family.reference(), producer=producer)
    report = compare_runs(
        baseline_manifest=baseline_manifest,
        candidate_manifest=candidate_manifest,
        baseline=baseline,
        candidate=candidate,
        loader=store.load,
        producer=producer,
        baseline_plans=(baseline_plan,),
        candidate_plans=(candidate_plan,),
    )
    assert str(report.payload.status) == "invalid"  # differing deterministic seeds are a declared confounder
    query_delta = next(item for item in report.payload.metric_deltas if item.metric_key == "query_count")
    assert query_delta.baseline == 7
    assert query_delta.candidate == 2
    assert query_delta.direction == "improved"
    assert any("Seq Scan" in transition and "Index Scan" in transition for change in report.payload.plan_changes for transition in change.transitions)
    assert report.verify_integrity()
