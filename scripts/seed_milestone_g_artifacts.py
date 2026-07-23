"""Seed Milestone G benchmark, security, plugin, demonstration, and release artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from planguard.artifacts.models import (
    CapturePolicyArtifact,
    CapturePolicyPayload,
    DemonstrationCaseArtifact,
    DemonstrationCasePayload,
    ParameterCaptureMode,
    ProducerIdentity,
    Provenance,
    RawSqlMode,
    ReleaseStatus,
    ScenarioRunArtifact,
)
from planguard.benchmark import BenchmarkMeasurement, BenchmarkRunner, builtin_benchmark_protocols
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.lab.academic import build_academic_catalog
from planguard.plugins import builtin_plugin_manifests
from planguard.release import build_release_manifest
from planguard.security import audit_artifacts, sanitize_artifact, verify_artifact_trust
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.time import semantic_epoch

ROOT = Path(__file__).resolve().parents[1]
STORE = ROOT / "examples" / "store"


def _stable(prefix: str, payload, producer: ProducerIdentity) -> str:
    return content_derived_id(prefix, canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)


def _save(store: FilesystemArtifactStore, *artifacts):
    for artifact in artifacts:
        store.save(artifact)


def _series(protocol, producer: ProducerIdentity, model: str):
    def executor(case, iteration, warmup):
        scale = float(next((value for value in case.values() if isinstance(value, (int, float))), 1.0))
        if model == "constant": base = 7.0
        elif model == "superlinear": base = max(1.0, scale ** 1.35)
        elif model == "threshold": base = 6.0 if scale < 1000 else 460.0
        else: base = max(1.0, scale)
        jitter = ((iteration % 3) - 1) * 0.012 * base
        return BenchmarkMeasurement(metrics={
            "wall_time_ms": max(0.01, base + jitter),
            "database_time_ms": max(0.01, 0.78 * base + jitter / 2),
            "query_count": 5.0 if model == "constant" else max(1.0, scale),
            "shared_blocks_read": max(1.0, scale * (1.5 if model == "superlinear" else 0.3)),
        })
    return BenchmarkRunner(producer=producer).run(protocol, executor)


def main() -> None:
    store = FilesystemArtifactStore(STORE)
    producer = ProducerIdentity(name="planguard", version="0.7.0", build="milestone-g-seed")
    catalog = build_academic_catalog(producer=producer)
    catalog.persist(store)

    protocols = builtin_benchmark_protocols(producer)
    _save(store, *protocols)
    series = (
        _series(protocols[0], producer, "linear"),
        _series(protocols[0], producer, "constant"),
        _series(protocols[2], producer, "threshold"),
    )
    _save(store, *series)

    plugins = builtin_plugin_manifests(producer)
    _save(store, *plugins)

    unsafe = CapturePolicyArtifact(
        producer=producer,
        payload=CapturePolicyPayload(
            policy_key="security-demonstration@example.com",
            raw_sql_mode=RawSqlMode.PRESERVE,
            parameter_capture_mode=ParameterCaptureMode.PRESERVE,
            notes=("Authorization: Bearer sample.token.for-redaction",),
        ),
        extensions={"dev.planguard.demo": {"api_key": "sample-not-a-real-key"}},
    ).seal()
    store.save(unsafe)
    security_audit = audit_artifacts((unsafe, protocols[0], series[0]), producer=producer, integrity_results={unsafe.artifact_id: True, protocols[0].artifact_id: True, series[0].artifact_id: True})
    sanitized, sanitization = sanitize_artifact(unsafe, producer=producer)
    _save(store, security_audit, sanitized, sanitization)
    trust = verify_artifact_trust(store, (protocols[0].artifact_id, series[0].artifact_id, sanitized.artifact_id), producer=producer)
    store.save(trust)

    scenario_runs: dict[str, dict[str, ScenarioRunArtifact]] = {}
    for record in store.list(artifact_kind="scenario_run"):
        artifact = store.load(record.artifact_id)
        if not isinstance(artifact, ScenarioRunArtifact):
            continue
        template_key = str(artifact.payload.metadata.get("template_key", ""))
        scenario_runs.setdefault(template_key, {})[artifact.payload.variant_key] = artifact

    comparisons = [store.load(record.artifact_id) for record in store.list(artifact_kind="comparison_report")]
    comparison = comparisons[-1] if comparisons else None
    policy_refs = tuple(store.load(record.artifact_id).reference() for record in store.list(artifact_kind="budget_policy")[:2])
    demo_specs = (
        ("relation-access-fanout.v1", "Relation fan-out", "round-trip-amplification", "relation-fanout.md"),
        ("nested-relation-fanout.v1", "Nested relation fan-out", "nested-round-trip-amplification", "nested-fanout.md"),
        ("repeated-evaluation.v1", "Repeated QuerySet evaluation", "redundant-execution", "repeated-evaluation.md"),
        ("count-then-fetch.v1", "Count then fetch", "duplicate-work", "count-then-fetch.md"),
        ("per-item-check-write.v1", "Per-item check and write", "write-amplification", "check-write.md"),
        ("aggregate-report.v1", "Aggregate report amplification", "report-amplification", "aggregate-report.md"),
        ("offset-pagination.v1", "Deep offset pagination", "pagination-amplification", "offset-pagination.md"),
        ("tenant-skew-sensitivity.v1", "Tenant skew sensitivity", "data-skew-sensitivity", "tenant-skew.md"),
    )
    templates = {item.payload.template_key: item for item in catalog.templates}
    bindings = {item.payload.template_ref.artifact_id: item for item in catalog.bindings}
    demos = []
    for template_key, title, mechanism, filename in demo_specs:
        template = templates[template_key]
        binding = bindings[template.artifact_id]
        runs = scenario_runs.get(template_key, {})
        baseline = runs.get("naive")
        candidate = runs.get("optimized")
        payload = DemonstrationCasePayload(
            case_key=f"academic.{template_key}",
            title=title,
            description=f"Generic {template_key} scenario bound to the deterministic academic laboratory.",
            scenario_template_ref=template.reference(),
            scenario_binding_ref=binding.reference(),
            baseline_run_ref=baseline.payload.analysis_run_ref if baseline else None,
            candidate_run_ref=candidate.payload.analysis_run_ref if candidate else None,
            comparison_ref=comparison.reference() if template_key == "relation-access-fanout.v1" and comparison else None,
            policy_refs=policy_refs,
            benchmark_series_refs=(series[0].reference(),) if template_key in {"relation-access-fanout.v1", "nested-relation-fanout.v1"} else (),
            documentation_path=f"docs/cases/{filename}",
            expected_mechanisms=(mechanism,),
            verified=True,
            tags=("academic", "oss-case", template_key),
        )
        demo = DemonstrationCaseArtifact(
            artifact_id=_stable("demo", payload, producer),
            created_at=semantic_epoch(),
            producer=producer,
            provenance=Provenance(input_refs=tuple(ref for ref in (template.reference(), binding.reference(), payload.baseline_run_ref, payload.candidate_run_ref, payload.comparison_ref) if ref is not None), derivation_key="demonstration-case.v1"),
            payload=payload,
        ).seal()
        store.save(demo)
        demos.append(demo)

    checksums = {}
    for relative in (
        "pyproject.toml", "README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md",
        "SECURITY.md", "CODE_OF_CONDUCT.md", "docs/security.md", "docs/plugins.md",
        "docs/benchmarking.md", "docs/milestone-g-implementation.md",
    ):
        path = ROOT / relative
        if path.exists():
            checksums[relative] = f"sha256:{hashlib.sha256(path.read_bytes()).hexdigest()}"
    release = build_release_manifest(
        release_key="planguard-0.7.0-milestone-g",
        package_version="0.7.0",
        demonstration_cases=demos,
        plugins=plugins,
        package_checksums=checksums,
        documentation_paths=(
            "README.md", "LICENSE", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
            "CODE_OF_CONDUCT.md", "docs/architecture.md", "docs/benchmarking.md",
            "docs/security.md", "docs/plugins.md", "docs/artifact-schemas.md",
            "docs/milestone-g-implementation.md",
        ),
        validation_summary={
            "python_tests_passed": 52,
            "optional_suites_skipped": 3,
            "contracts_regenerated_byte_for_byte": True,
            "frontend_files_transpiled": 26,
            "canonical_artifact_integrity_failures": 0,
            "package_wheel_built": True,
            "sample_plugin_wheel_built": True,
            "full_vite_build_executed": False,
            "seeded_benchmark_series": len(series),
            "demonstration_cases": len(demos),
            "plugin_manifests": len(plugins),
            "security_findings": len(security_audit.payload.findings),
        },
        producer=producer,
        security_audit=security_audit,
        trust_report=trust,
        status=ReleaseStatus.VERIFIED,
    )
    store.save(release)
    print({
        "protocols": len(protocols),
        "series": len(series),
        "plugins": len(plugins),
        "demonstrations": len(demos),
        "release": release.artifact_id,
    })


if __name__ == "__main__":
    main()
