"""Create and optionally persist the complete academic scenario catalog."""

from __future__ import annotations

from dataclasses import dataclass

from planguard.artifacts.models import (
    MutationDefinitionArtifact,
    ProducerIdentity,
    ScenarioBindingArtifact,
    ScenarioTemplateArtifact,
)
from planguard.lab.academic.adapter import AcademicScenarioAdapter
from planguard.lab.academic.catalog import builtin_bindings, builtin_mutations, builtin_templates
from planguard.scenario.registry import ScenarioRegistry
from planguard.store.filesystem import FilesystemArtifactStore


@dataclass(frozen=True, slots=True)
class AcademicCatalog:
    registry: ScenarioRegistry
    templates: tuple[ScenarioTemplateArtifact, ...]
    bindings: tuple[ScenarioBindingArtifact, ...]
    mutations: tuple[MutationDefinitionArtifact, ...]

    def persist(self, store: FilesystemArtifactStore) -> int:
        artifacts = (*self.templates, *self.bindings, *self.mutations)
        for artifact in artifacts:
            store.save(artifact)
        return len(artifacts)


def build_academic_catalog(*, producer: ProducerIdentity | None = None) -> AcademicCatalog:
    producer = producer or ProducerIdentity(name="planguard", version="0.4.0", build="milestone-d")
    templates = builtin_templates(producer)
    bindings = builtin_bindings(producer, templates)
    mutations = builtin_mutations(producer)
    registry = ScenarioRegistry()
    for artifact in templates:
        registry.register_template(artifact)
    for artifact in bindings:
        registry.register_binding(artifact)
    for artifact in mutations:
        registry.register_mutation(artifact)
    registry.register_adapter(AcademicScenarioAdapter())
    return AcademicCatalog(registry=registry, templates=templates, bindings=bindings, mutations=mutations)
