"""OSS demonstration case and release-manifest helpers."""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from planguard.artifacts.models import (
    ArtifactReference,
    DemonstrationCaseArtifact,
    PluginManifestArtifact,
    ProducerIdentity,
    Provenance,
    ReleaseManifestArtifact,
    ReleaseManifestPayload,
    ReleaseStatus,
    SecurityAuditArtifact,
    ArtifactTrustReportArtifact,
)
from planguard.artifacts.models import ARTIFACT_MODELS
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def verify_demonstration_case(case: DemonstrationCaseArtifact, loader) -> tuple[bool, tuple[str, ...]]:
    missing: list[str] = []
    references = (
        case.payload.scenario_template_ref,
        case.payload.scenario_binding_ref,
        case.payload.baseline_run_ref,
        case.payload.candidate_run_ref,
        case.payload.comparison_ref,
        *case.payload.policy_refs,
        *case.payload.benchmark_series_refs,
    )
    for reference in references:
        if reference is None:
            continue
        try:
            artifact = loader(reference.artifact_id)
        except Exception:
            missing.append(reference.artifact_id)
            continue
        if not artifact.verify_integrity():
            missing.append(f"{reference.artifact_id}:integrity")
    return not missing, tuple(missing)


def build_release_manifest(
    *,
    release_key: str,
    package_version: str,
    demonstration_cases: Iterable[DemonstrationCaseArtifact],
    plugins: Iterable[PluginManifestArtifact],
    package_checksums: Mapping[str, str],
    documentation_paths: Iterable[str],
    validation_summary: Mapping[str, object],
    producer: ProducerIdentity,
    security_audit: SecurityAuditArtifact | None = None,
    trust_report: ArtifactTrustReportArtifact | None = None,
    status: ReleaseStatus = ReleaseStatus.CANDIDATE,
) -> ReleaseManifestArtifact:
    cases = tuple(demonstration_cases)
    plugin_artifacts = tuple(plugins)
    schemas = tuple(sorted(str(model.model_fields["schema_version"].default) for model in ARTIFACT_MODELS))
    payload = ReleaseManifestPayload(
        release_key=release_key,
        package_version=package_version,
        status=status,
        plugin_contract_version="planguard.plugin.v1",
        artifact_schema_versions=schemas,
        package_checksums=dict(sorted(package_checksums.items())),
        demonstration_case_refs=tuple(case.reference() for case in cases),
        plugin_manifest_refs=tuple(plugin.reference() for plugin in plugin_artifacts),
        documentation_paths=tuple(sorted(documentation_paths)),
        compatibility={
            "python": ">=3.11",
            "django": ">=5.2,<5.3",
            "postgresql": "FORMAT JSON plan compatibility with preserved unknown nodes",
            "artifact_reading": "Milestone A through G v1 schemas",
        },
        validation_summary=dict(validation_summary),
        security_audit_ref=security_audit.reference() if security_audit else None,
        trust_report_ref=trust_report.reference() if trust_report else None,
        release_notes=(
            "PlanGuard treats structural evidence as authoritative when timing comparability is degraded.",
            "Execution-capable laboratory and live plan collection remain explicitly gated.",
        ),
    )
    identity = content_derived_id(
        "rel",
        canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}),
        length=32,
    )
    inputs: list[ArtifactReference] = [case.reference() for case in cases]
    inputs.extend(plugin.reference() for plugin in plugin_artifacts)
    if security_audit:
        inputs.append(security_audit.reference())
    if trust_report:
        inputs.append(trust_report.reference())
    return ReleaseManifestArtifact(
        artifact_id=identity,
        created_at=semantic_epoch(),
        producer=producer,
        provenance=Provenance(input_refs=tuple(inputs), derivation_key="release-manifest.v1"),
        payload=payload,
    ).seal()
