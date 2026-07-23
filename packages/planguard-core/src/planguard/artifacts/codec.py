"""Artifact encoding, decoding, sealing, and integrity verification."""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from planguard.artifacts.models import ARTIFACT_MODELS, ArtifactDocument
from planguard.artifacts.registry import ArtifactTypeRegistry, ExtensionRegistry
from planguard.canonical import canonical_json_bytes, canonical_json_text
from planguard.errors import (
    ArtifactIntegrityError,
    ArtifactValidationError,
    UnsupportedArtifactError,
)


class ArtifactCodec:
    def __init__(
        self,
        *,
        artifact_registry: ArtifactTypeRegistry | None = None,
        extension_registry: ExtensionRegistry | None = None,
    ) -> None:
        self.artifact_registry = artifact_registry or ArtifactTypeRegistry()
        self.extension_registry = extension_registry or ExtensionRegistry()

    def register_core_contracts(self) -> None:
        for model in ARTIFACT_MODELS:
            fields = model.model_fields
            kind_default = fields["artifact_kind"].default
            version_default = fields["schema_version"].default
            self.artifact_registry.register(
                artifact_kind=str(kind_default),
                schema_version=str(version_default),
                model=model,
                overwrite=True,
            )

    def seal(self, artifact: ArtifactDocument[Any]) -> ArtifactDocument[Any]:
        extensions = self.extension_registry.validate(dict(artifact.extensions))
        updated = artifact.model_copy(update={"extensions": extensions})
        return updated.seal()

    def encode(self, artifact: ArtifactDocument[Any], *, pretty: bool = False) -> bytes:
        sealed = self.seal(artifact)
        if pretty:
            return (canonical_json_text(sealed, pretty=True) + "\n").encode("utf-8")
        return canonical_json_bytes(sealed)

    def decode(self, raw: bytes | str | dict[str, Any]) -> ArtifactDocument[Any]:
        if isinstance(raw, bytes):
            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ArtifactValidationError("Artifact is not valid UTF-8 JSON") from exc
        elif isinstance(raw, str):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ArtifactValidationError("Artifact is not valid JSON") from exc
        else:
            data = raw

        if not isinstance(data, dict):
            raise ArtifactValidationError("Artifact root must be a JSON object")

        artifact_kind = data.get("artifact_kind")
        schema_version = data.get("schema_version")
        if not isinstance(artifact_kind, str) or not isinstance(schema_version, str):
            raise ArtifactValidationError(
                "Artifact requires string artifact_kind and schema_version fields"
            )

        contract = self.artifact_registry.get(artifact_kind, schema_version)
        if contract is None:
            raise UnsupportedArtifactError(artifact_kind, schema_version)

        extensions = data.get("extensions", {})
        if not isinstance(extensions, dict):
            raise ArtifactValidationError("Artifact extensions must be an object")
        data = dict(data)
        data["extensions"] = self.extension_registry.validate(extensions)

        try:
            artifact = contract.model.model_validate(data)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            if any("content_hash does not match" in str(error.get("msg", "")) for error in errors):
                raise ArtifactIntegrityError(
                    "Artifact content hash does not match canonical document content",
                    {"artifact_id": data.get("artifact_id")},
                ) from exc
            raise ArtifactValidationError(
                "Artifact failed contract validation",
                {"errors": errors},
            ) from exc

        if not artifact.verify_integrity():
            raise ArtifactIntegrityError(
                "Artifact content hash is missing or invalid",
                {"artifact_id": artifact.artifact_id},
            )
        return artifact


def build_default_codec() -> ArtifactCodec:
    codec = ArtifactCodec()
    codec.register_core_contracts()
    return codec


default_codec = build_default_codec()
