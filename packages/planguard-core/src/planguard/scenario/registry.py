"""Open registries for scenario templates, bindings, mutations, and adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any

from planguard.artifacts.models import (
    MutationDefinitionArtifact,
    ScenarioBindingArtifact,
    ScenarioTemplateArtifact,
)
from planguard.errors import RegistryConflictError


class ScenarioAdapter(Protocol):
    adapter_key: str

    def prepare_environment(self, context: Any) -> dict[str, Any]: ...
    def prepare_dataset(self, context: Any) -> Any: ...
    def apply_mutation(self, context: Any, mutation: MutationDefinitionArtifact, parameters: dict[str, Any]) -> Any: ...
    def execute(self, context: Any, session: Any) -> Any: ...
    def evaluate_oracle(self, context: Any, oracle: Any, result: Any) -> Any: ...
    def cleanup(self, context: Any) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ScenarioRegistrySnapshot:
    template_keys: tuple[str, ...]
    binding_keys: tuple[str, ...]
    mutation_keys: tuple[str, ...]
    adapter_keys: tuple[str, ...]


class ScenarioRegistry:
    def __init__(self) -> None:
        self._templates: dict[str, ScenarioTemplateArtifact] = {}
        self._bindings: dict[str, ScenarioBindingArtifact] = {}
        self._mutations: dict[str, MutationDefinitionArtifact] = {}
        self._adapters: dict[str, ScenarioAdapter] = {}

    @staticmethod
    def _put(mapping: dict[str, Any], key: str, value: Any, *, overwrite: bool) -> Any:
        if key in mapping and not overwrite:
            raise RegistryConflictError(key)
        mapping[key] = value
        return value

    def register_template(self, artifact: ScenarioTemplateArtifact, *, overwrite: bool = False) -> ScenarioTemplateArtifact:
        return self._put(self._templates, artifact.payload.template_key, artifact, overwrite=overwrite)

    def register_binding(self, artifact: ScenarioBindingArtifact, *, overwrite: bool = False) -> ScenarioBindingArtifact:
        return self._put(self._bindings, artifact.payload.binding_key, artifact, overwrite=overwrite)

    def register_mutation(self, artifact: MutationDefinitionArtifact, *, overwrite: bool = False) -> MutationDefinitionArtifact:
        return self._put(self._mutations, artifact.payload.mutation_key, artifact, overwrite=overwrite)

    def register_adapter(self, adapter: ScenarioAdapter, *, overwrite: bool = False) -> ScenarioAdapter:
        return self._put(self._adapters, adapter.adapter_key, adapter, overwrite=overwrite)

    def require_template(self, key: str) -> ScenarioTemplateArtifact:
        try:
            return self._templates[key]
        except KeyError as exc:
            raise KeyError(f"Unknown scenario template: {key}") from exc

    def require_binding(self, key: str) -> ScenarioBindingArtifact:
        try:
            return self._bindings[key]
        except KeyError as exc:
            raise KeyError(f"Unknown scenario binding: {key}") from exc

    def require_mutation(self, key: str) -> MutationDefinitionArtifact:
        try:
            return self._mutations[key]
        except KeyError as exc:
            raise KeyError(f"Unknown scenario mutation: {key}") from exc

    def require_adapter(self, key: str) -> ScenarioAdapter:
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise KeyError(f"Unknown scenario adapter: {key}") from exc

    def template_for_ref(self, artifact_id: str) -> ScenarioTemplateArtifact:
        for item in self._templates.values():
            if item.artifact_id == artifact_id:
                return item
        raise KeyError(f"Unknown scenario template artifact: {artifact_id}")

    def binding_for_ref(self, artifact_id: str) -> ScenarioBindingArtifact:
        for item in self._bindings.values():
            if item.artifact_id == artifact_id:
                return item
        raise KeyError(f"Unknown scenario binding artifact: {artifact_id}")

    def mutation_for_ref(self, artifact_id: str) -> MutationDefinitionArtifact:
        for item in self._mutations.values():
            if item.artifact_id == artifact_id:
                return item
        raise KeyError(f"Unknown mutation artifact: {artifact_id}")

    def snapshot(self) -> ScenarioRegistrySnapshot:
        return ScenarioRegistrySnapshot(
            template_keys=tuple(sorted(self._templates)),
            binding_keys=tuple(sorted(self._bindings)),
            mutation_keys=tuple(sorted(self._mutations)),
            adapter_keys=tuple(sorted(self._adapters)),
        )

    def templates(self) -> tuple[ScenarioTemplateArtifact, ...]:
        return tuple(self._templates[key] for key in sorted(self._templates))

    def bindings(self) -> tuple[ScenarioBindingArtifact, ...]:
        return tuple(self._bindings[key] for key in sorted(self._bindings))

    def mutations(self) -> tuple[MutationDefinitionArtifact, ...]:
        return tuple(self._mutations[key] for key in sorted(self._mutations))
