"""Portable run-bundle export helpers."""

from __future__ import annotations

import io
import json
import zipfile
from typing import Any

from planguard.analysis.load import load_analysis_bundle
from planguard.canonical import canonical_data, canonical_json_text
from planguard.store.filesystem import FilesystemArtifactStore


def export_run_bundle(store: FilesystemArtifactStore, run_id: str) -> bytes:
    manifest, bundle = load_analysis_bundle(store, run_id)
    artifacts = [manifest, *bundle.executions, *bundle.all_derived_artifacts()]
    # De-duplicate content-addressed/global motif artifacts while preserving order.
    unique: dict[str, Any] = {item.artifact_id: item for item in artifacts}
    inventory: dict[str, int] = {}
    for artifact in unique.values():
        inventory[artifact.artifact_kind] = inventory.get(artifact.artifact_kind, 0) + 1
    bundle_manifest = {
        "schema_version": "planguard.portable-run-bundle.v1",
        "run_id": run_id,
        "artifact_count": len(unique),
        "inventory": dict(sorted(inventory.items())),
        "artifacts": [
            {
                "artifact_id": artifact.artifact_id,
                "artifact_kind": artifact.artifact_kind,
                "schema_version": artifact.schema_version,
                "content_hash": artifact.content_hash,
                "path": f"artifacts/{artifact.artifact_id}.json",
            }
            for artifact in unique.values()
        ],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("bundle-manifest.json", json.dumps(bundle_manifest, sort_keys=True, indent=2) + "\n")
        for artifact in unique.values():
            archive.writestr(
                f"artifacts/{artifact.artifact_id}.json",
                canonical_json_text(artifact, pretty=True) + "\n",
            )
    return buffer.getvalue()
