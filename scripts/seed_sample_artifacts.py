#!/usr/bin/env python
from __future__ import annotations

import argparse
import platform
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "planguard-core" / "src"))

from planguard.artifacts.models import (  # noqa: E402
    ArtifactInventory,
    BundleIntegrity,
    CapabilityGap,
    CapabilityGapArtifact,
    CapabilityGapPayload,
    CapabilityState,
    CapabilityStatus,
    CapturePolicyArtifact,
    CapturePolicyPayload,
    DatabaseIdentity,
    EnvironmentProfileArtifact,
    EnvironmentProfilePayload,
    ProducerIdentity,
    Provenance,
    RunManifestArtifact,
    RunManifestPayload,
    RunStatus,
    RunSummary,
    RuntimeComponent,
)
from planguard.store.filesystem import FilesystemArtifactStore  # noqa: E402

PRODUCER = ProducerIdentity(name="planguard", version="0.1.0", build="milestone-a")
CREATED_AT = datetime(2026, 7, 23, 12, 0, tzinfo=UTC)


def seed(root: Path, *, clean: bool = True) -> tuple[str, ...]:
    if clean and root.exists():
        shutil.rmtree(root)
    store = FilesystemArtifactStore(root)

    environment = EnvironmentProfileArtifact(
        artifact_id="env_demo_001",
        created_at=CREATED_AT,
        producer=PRODUCER,
        payload=EnvironmentProfilePayload(
            operating_system=platform.system() or "Linux",
            architecture=platform.machine() or "x86_64",
            python_version=platform.python_version(),
            runtime_components=(
                RuntimeComponent(name="planguard", version="0.1.0"),
                RuntimeComponent(name="django", version="5.2.x", details={"optional": True}),
                RuntimeComponent(name="react-workbench", version="milestone-a"),
            ),
            database=DatabaseIdentity(
                vendor="postgresql",
                version=None,
                database_hash=None,
                connection_aliases=("default",),
            ),
            environment_variables={"PLANGUARD_MODE": "explorer"},
            machine_profile={"sample": True, "purpose": "artifact-inspector-demo"},
            notes=("Synthetic environment profile for Milestone A.",),
        ),
        extensions={
            "dev.planguard.demo": {
                "label": "Sample environment",
                "safe_to_share": True,
            }
        },
    )
    environment_record = store.save(environment)
    environment = store.load(environment_record.artifact_id)

    policy = CapturePolicyArtifact(
        artifact_id="cap_demo_001",
        created_at=CREATED_AT,
        producer=PRODUCER,
        payload=CapturePolicyPayload(
            policy_key="safe-local-default.v1",
            application_roots=("academic_lab",),
            exclude_module_patterns=("django.*", "pytest.*"),
            hmac_key_id="local-demo-key",
            notes=("No SQL capture exists in Milestone A; this is the future contract.",),
        ),
    )
    policy_record = store.save(policy)
    policy = store.load(policy_record.artifact_id)

    gap = CapabilityGapArtifact(
        artifact_id="gap_demo_001",
        created_at=CREATED_AT,
        producer=PRODUCER,
        provenance=Provenance(
            configuration_ref=policy.reference(),
            code_revision="git:milestone-a",
            derivation_key="planguard.bootstrap-capability-audit.v1",
        ),
        payload=CapabilityGapPayload(
            gaps=(
                CapabilityGap(
                    capability="query.capture.django",
                    status="unsupported",
                    reason="SQL capture begins in Phase 2 / Milestone B.",
                    impact=(
                        "Run manifests cannot yet contain query observations.",
                        "Query families and findings are not evaluated.",
                    ),
                ),
                CapabilityGap(
                    capability="plan.postgresql",
                    status="unsupported",
                    reason="PostgreSQL plan analysis begins in Phase 10.",
                    impact=("Plan artifacts are unavailable.",),
                ),
            )
        ),
    )
    gap_record = store.save(gap)
    gap = store.load(gap_record.artifact_id)

    run = RunManifestArtifact(
        artifact_id="run_demo_001",
        created_at=CREATED_AT,
        producer=PRODUCER,
        provenance=Provenance(
            input_refs=(environment.reference(), policy.reference(), gap.reference()),
            configuration_ref=policy.reference(),
            code_revision="git:milestone-a",
            derivation_key="planguard.sample-run.v1",
        ),
        payload=RunManifestPayload(
            run=RunSummary(
                name="Milestone A artifact-inspector demonstration",
                mode="bootstrap",
                started_at=CREATED_AT,
                completed_at=CREATED_AT,
                status=RunStatus.COMPLETED,
                tags=("sample", "milestone-a", "artifact-kernel"),
            ),
            environment_ref=environment.reference(),
            capture_policy_ref=policy.reference(),
            artifact_inventory=ArtifactInventory(
                by_kind={
                    "environment_profile": 1,
                    "capture_policy": 1,
                    "capability_gap": 1,
                },
                total_count=3,
            ),
            capability_status={
                "artifact.canonicalization": CapabilityStatus(
                    state=CapabilityState.SUPPORTED,
                    reason="Canonical JSON and SHA-256 sealing are active.",
                ),
                "artifact.extensions": CapabilityStatus(
                    state=CapabilityState.SUPPORTED,
                    reason="Unknown extension namespaces are preserved.",
                ),
                "query.capture.django": CapabilityStatus(
                    state=CapabilityState.UNSUPPORTED,
                    reason="Deferred to Milestone B.",
                ),
            },
            capability_gap_refs=(gap.reference(),),
            integrity=BundleIntegrity(verified=False),
        ),
    )
    run_record = store.save(run)
    return (
        environment_record.artifact_id,
        policy_record.artifact_id,
        gap_record.artifact_id,
        run_record.artifact_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, default=ROOT / "examples" / "store")
    parser.add_argument("--no-clean", action="store_true")
    args = parser.parse_args()
    artifact_ids = seed(args.store, clean=not args.no_clean)
    print("Seeded artifacts:")
    for artifact_id in artifact_ids:
        print(f"  {artifact_id}")


if __name__ == "__main__":
    main()
