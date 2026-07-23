"""Domain exceptions with stable error codes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class PlanGuardError(Exception):
    """Base exception carrying a machine-readable code and optional details."""

    message: str
    code: str = "planguard_error"
    details: dict[str, Any] | None = None

    def __str__(self) -> str:
        return self.message


class ArtifactValidationError(PlanGuardError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="artifact_validation_error", details=details)


class ArtifactIntegrityError(PlanGuardError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="artifact_integrity_error", details=details)


class ArtifactNotFoundError(PlanGuardError):
    def __init__(self, artifact_id: str) -> None:
        super().__init__(
            message=f"Artifact not found: {artifact_id}",
            code="artifact_not_found",
            details={"artifact_id": artifact_id},
        )


class RegistryConflictError(PlanGuardError):
    def __init__(self, key: str) -> None:
        super().__init__(
            message=f"Registry key is already registered: {key}",
            code="registry_conflict",
            details={"key": key},
        )


class UnsupportedArtifactError(PlanGuardError):
    def __init__(self, artifact_kind: str, schema_version: str) -> None:
        super().__init__(
            message=f"Unsupported artifact contract: {artifact_kind} / {schema_version}",
            code="unsupported_artifact",
            details={
                "artifact_kind": artifact_kind,
                "schema_version": schema_version,
            },
        )
