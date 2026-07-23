from __future__ import annotations

from planguard.artifacts.models import (
    DemonstrationCaseArtifact,
    DemonstrationCasePayload,
    ProducerIdentity,
    ReleaseStatus,
)
from planguard.lab.academic import build_academic_catalog
from planguard.plugins import builtin_plugin_manifests
from planguard.release import build_release_manifest, verify_demonstration_case
from planguard.store.filesystem import FilesystemArtifactStore


def test_demonstration_case_and_release_manifest(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.templates[0]
    binding = next(item for item in catalog.bindings if item.payload.template_ref.artifact_id == template.artifact_id)
    store = FilesystemArtifactStore(tmp_path)
    store.save(template); store.save(binding)
    case = DemonstrationCaseArtifact(
        producer=producer,
        payload=DemonstrationCasePayload(
            case_key="relation-fanout.v1",
            title="Relation fan-out",
            description="Generic case bound to the academic laboratory.",
            scenario_template_ref=template.reference(),
            scenario_binding_ref=binding.reference(),
            documentation_path="docs/cases/relation-fanout.md",
            expected_mechanisms=("round-trip-amplification",),
            verified=True,
        ),
    ).seal()
    store.save(case)
    valid, missing = verify_demonstration_case(case, store.load)
    assert valid and not missing
    plugins = builtin_plugin_manifests(producer)
    release = build_release_manifest(
        release_key="test-0.7.0",
        package_version="0.7.0",
        demonstration_cases=(case,),
        plugins=plugins,
        package_checksums={"wheel": "sha256:" + "0" * 64},
        documentation_paths=("README.md",),
        validation_summary={"tests": 1},
        producer=producer,
        status=ReleaseStatus.VERIFIED,
    )
    assert release.payload.demonstration_case_refs[0].artifact_id == case.artifact_id
    assert "planguard.release-manifest.v1" in release.payload.artifact_schema_versions
    assert release.verify_integrity()
