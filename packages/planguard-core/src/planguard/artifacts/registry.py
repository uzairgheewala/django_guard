"""Open registries for artifact contracts and namespaced extensions."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from planguard.errors import ArtifactValidationError, RegistryConflictError

_NAMESPACE = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{0,126}[a-z0-9])?$")
ModelT = TypeVar("ModelT", bound=BaseModel)


@dataclass(frozen=True, slots=True)
class ArtifactContract(Generic[ModelT]):
    artifact_kind: str
    schema_version: str
    model: type[ModelT]


class ArtifactTypeRegistry:
    def __init__(self) -> None:
        self._contracts: dict[tuple[str, str], ArtifactContract[Any]] = {}

    def register(
        self,
        *,
        artifact_kind: str,
        schema_version: str,
        model: type[ModelT],
        overwrite: bool = False,
    ) -> ArtifactContract[ModelT]:
        key = (artifact_kind, schema_version)
        if key in self._contracts and not overwrite:
            raise RegistryConflictError(f"{artifact_kind}/{schema_version}")
        contract = ArtifactContract(
            artifact_kind=artifact_kind,
            schema_version=schema_version,
            model=model,
        )
        self._contracts[key] = contract
        return contract

    def get(self, artifact_kind: str, schema_version: str) -> ArtifactContract[Any] | None:
        return self._contracts.get((artifact_kind, schema_version))

    def require(self, artifact_kind: str, schema_version: str) -> ArtifactContract[Any]:
        contract = self.get(artifact_kind, schema_version)
        if contract is None:
            raise ArtifactValidationError(
                "Artifact contract is not registered",
                {
                    "artifact_kind": artifact_kind,
                    "schema_version": schema_version,
                },
            )
        return contract

    def keys(self) -> tuple[tuple[str, str], ...]:
        return tuple(sorted(self._contracts))


@dataclass(frozen=True, slots=True)
class ExtensionContract(Generic[ModelT]):
    namespace: str
    model: type[ModelT]


class ExtensionRegistry:
    """Validates optional namespaced artifact extensions without owning them."""

    def __init__(self) -> None:
        self._contracts: dict[str, ExtensionContract[Any]] = {}

    def register(
        self,
        namespace: str,
        model: type[ModelT],
        *,
        overwrite: bool = False,
    ) -> ExtensionContract[ModelT]:
        if not _NAMESPACE.fullmatch(namespace):
            raise ValueError(f"Invalid extension namespace: {namespace!r}")
        if namespace in self._contracts and not overwrite:
            raise RegistryConflictError(namespace)
        contract = ExtensionContract(namespace=namespace, model=model)
        self._contracts[namespace] = contract
        return contract

    def get(self, namespace: str) -> ExtensionContract[Any] | None:
        return self._contracts.get(namespace)

    def validate(
        self,
        extensions: dict[str, dict[str, Any]],
        *,
        preserve_unknown: bool = True,
        on_unknown: Callable[[str], None] | None = None,
    ) -> dict[str, dict[str, Any]]:
        validated: dict[str, dict[str, Any]] = {}
        for namespace, payload in extensions.items():
            contract = self.get(namespace)
            if contract is None:
                if on_unknown is not None:
                    on_unknown(namespace)
                if preserve_unknown:
                    validated[namespace] = payload
                continue
            try:
                model = contract.model.model_validate(payload)
            except ValidationError as exc:
                raise ArtifactValidationError(
                    f"Invalid extension payload for {namespace}",
                    {"namespace": namespace, "errors": exc.errors()},
                ) from exc
            validated[namespace] = model.model_dump(mode="json", exclude_none=False)
        return validated

    def namespaces(self) -> tuple[str, ...]:
        return tuple(sorted(self._contracts))
