"""Minimal third-party PlanGuard reporter plugin."""

from __future__ import annotations

from typing import Any

from planguard.artifacts.models import (
    PluginComponentType,
    PluginDeterminism,
    PluginManifestArtifact,
    PluginManifestPayload,
    ProducerIdentity,
    Provenance,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def render_summary(artifact: Any) -> str:
    """Render one intentionally small summary for demonstration purposes."""
    kind = getattr(artifact, "artifact_kind", type(artifact).__name__)
    identity = getattr(artifact, "artifact_id", "unknown")
    return f"{kind}: {identity}"


def plugin():
    producer = ProducerIdentity(name="planguard-sample-reporter", version="0.1.0")
    payload = PluginManifestPayload(
        plugin_key="example.sample-reporter.v1",
        plugin_version="0.1.0",
        package_name="planguard-sample-reporter",
        entry_point_name="sample-reporter",
        component_type=PluginComponentType.REPORTER,
        accepted_schema_versions=("planguard.any-artifact.v1",),
        emitted_schema_versions=(),
        determinism=PluginDeterminism.DETERMINISTIC,
        configuration_schema={"type": "object", "additionalProperties": False},
        safety_profile={"network_access": False, "filesystem_write": False},
        enabled_by_default=False,
        description="Minimal deterministic reporter used to document the public plugin contract.",
        tags=("example", "reporter"),
    )
    artifact_id = content_derived_id(
        "plugin",
        canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}),
        length=32,
    )
    manifest = PluginManifestArtifact(
        artifact_id=artifact_id,
        created_at=semantic_epoch(),
        producer=producer,
        provenance=Provenance(derivation_key="sample-plugin-manifest.v1"),
        payload=payload,
    ).seal()
    return manifest, render_summary
