"""Operational resource controls for local artifact stores."""

from __future__ import annotations

from dataclasses import dataclass

from planguard.store.filesystem import FilesystemArtifactStore


@dataclass(frozen=True, slots=True)
class StoreQuotaPolicy:
    max_artifacts: int = 100_000
    max_total_bytes: int = 10_000_000_000
    max_single_artifact_bytes: int = 100_000_000


@dataclass(frozen=True, slots=True)
class StoreQuotaAssessment:
    artifact_count: int
    total_bytes: int
    largest_artifact_bytes: int
    artifact_count_exceeded: bool
    total_bytes_exceeded: bool
    single_artifact_exceeded: bool

    @property
    def accepted(self) -> bool:
        return not (
            self.artifact_count_exceeded
            or self.total_bytes_exceeded
            or self.single_artifact_exceeded
        )


def assess_store_quota(
    store: FilesystemArtifactStore,
    policy: StoreQuotaPolicy = StoreQuotaPolicy(),
) -> StoreQuotaAssessment:
    files = tuple(store.artifacts_root.glob("*.json"))
    sizes = [path.stat().st_size for path in files]
    total = sum(sizes)
    largest = max(sizes, default=0)
    return StoreQuotaAssessment(
        artifact_count=len(files),
        total_bytes=total,
        largest_artifact_bytes=largest,
        artifact_count_exceeded=len(files) > policy.max_artifacts,
        total_bytes_exceeded=total > policy.max_total_bytes,
        single_artifact_exceeded=largest > policy.max_single_artifact_bytes,
    )
