"""Deterministic scenario algebra over canonical artifacts."""

from __future__ import annotations

from itertools import product
from typing import Any, Iterable

from planguard.artifacts.models import (
    AppliedMutation,
    ArtifactReference,
    MutationDefinitionArtifact,
    ParameterDomain,
    ParameterDomainKind,
    ProducerIdentity,
    Provenance,
    ScenarioBindingArtifact,
    ScenarioInstanceArtifact,
    ScenarioInstancePayload,
    ScenarioSeriesArtifact,
    ScenarioSeriesPayload,
    ScenarioTemplateArtifact,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def _value_in_domain(value: Any, domain: ParameterDomain) -> bool:
    if domain.kind == ParameterDomainKind.BOOLEAN:
        return isinstance(value, bool)
    if domain.kind == ParameterDomainKind.FINITE:
        return value in domain.values
    if domain.kind == ParameterDomainKind.INTEGER_RANGE:
        return isinstance(value, int) and not isinstance(value, bool) and domain.minimum <= value <= domain.maximum
    if domain.kind == ParameterDomainKind.FLOAT_RANGE:
        return isinstance(value, (int, float)) and not isinstance(value, bool) and domain.minimum <= value <= domain.maximum
    return True


def validate_binding(template: ScenarioTemplateArtifact, binding: ScenarioBindingArtifact) -> None:
    if binding.payload.template_ref.artifact_id != template.artifact_id:
        raise ValueError("Scenario binding references a different template artifact")
    expected_roles = {role.role_key for role in template.payload.roles if role.required}
    bound_roles = {item.role_key for item in binding.payload.role_bindings}
    missing_roles = sorted(expected_roles - bound_roles)
    if missing_roles:
        raise ValueError(f"Scenario binding is missing required roles: {missing_roles}")
    template_variants = {item.variant_key for item in template.payload.variants}
    bound_variants = {item.variant_key for item in binding.payload.variant_bindings}
    missing_variants = sorted(template_variants - bound_variants)
    if missing_variants:
        raise ValueError(f"Scenario binding is missing variants: {missing_variants}")


def instantiate(
    template: ScenarioTemplateArtifact,
    binding: ScenarioBindingArtifact,
    *,
    parameters: dict[str, Any] | None = None,
    variant_key: str,
    mutations: Iterable[tuple[MutationDefinitionArtifact, dict[str, Any]]] = (),
    seed: int,
    producer: ProducerIdentity,
    tags: tuple[str, ...] = (),
    series_key: str | None = None,
) -> ScenarioInstanceArtifact:
    validate_binding(template, binding)
    parameters = dict(parameters or {})
    known_parameters = {item.parameter_key: item for item in template.payload.parameters}
    unknown = sorted(set(parameters) - set(known_parameters))
    if unknown:
        raise ValueError(f"Unknown scenario parameters: {unknown}")
    for key, definition in known_parameters.items():
        if key not in parameters:
            if definition.domain.default is not None:
                parameters[key] = definition.domain.default
            elif definition.required:
                raise ValueError(f"Missing required scenario parameter: {key}")
        if key in parameters and not _value_in_domain(parameters[key], definition.domain):
            raise ValueError(f"Parameter {key!r} is outside its declared domain")
    variant_keys = {item.variant_key for item in template.payload.variants}
    if variant_key not in variant_keys:
        raise ValueError(f"Unknown variant {variant_key!r}")
    applied = tuple(
        AppliedMutation(mutation_ref=mutation.reference(), parameter_bindings=params, order=index)
        for index, (mutation, params) in enumerate(mutations)
    )
    payload = ScenarioInstancePayload(
        template_ref=template.reference(),
        binding_ref=binding.reference(),
        parameter_bindings=parameters,
        variant_key=variant_key,
        applied_mutations=applied,
        seed=seed,
        series_key=series_key,
        tags=tags,
    )
    artifact_id = content_derived_id("sci", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return ScenarioInstanceArtifact(
            created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(
            input_refs=(template.reference(), binding.reference(), *(item.mutation_ref for item in applied)),
            derivation_key="scenario-instantiate.v1",
        ),
        payload=payload,
    ).seal()


def scale(
    template: ScenarioTemplateArtifact,
    binding: ScenarioBindingArtifact,
    *,
    base_parameters: dict[str, Any],
    dimension: str,
    values: Iterable[Any],
    variant_key: str,
    seed: int,
    producer: ProducerIdentity,
    mutations: Iterable[tuple[MutationDefinitionArtifact, dict[str, Any]]] = (),
    series_key: str | None = None,
) -> tuple[ScenarioSeriesArtifact, tuple[ScenarioInstanceArtifact, ...]]:
    key = series_key or f"{template.payload.template_key}:{dimension}"
    instances = tuple(
        instantiate(
            template,
            binding,
            parameters={**base_parameters, dimension: value},
            variant_key=variant_key,
            mutations=mutations,
            seed=seed + index,
            producer=producer,
            series_key=key,
            tags=("scenario-series", dimension),
        )
        for index, value in enumerate(values)
    )
    series = ScenarioSeriesArtifact(
            created_at=semantic_epoch(),
        artifact_id=content_derived_id(
            "scs",
            canonical_json_bytes({"key": key, "instances": [item.artifact_id for item in instances], "producer": producer.model_dump(mode="python")}),
            length=32,
        ),
        producer=producer,
        provenance=Provenance(
            input_refs=(template.reference(), binding.reference(), *(item.reference() for item in instances)),
            derivation_key="scenario-scale.v1",
        ),
        payload=ScenarioSeriesPayload(
            series_key=key,
            template_ref=template.reference(),
            binding_ref=binding.reference(),
            independent_dimensions=(dimension,),
            instance_refs=tuple(item.reference() for item in instances),
            generation_strategy="ordered-scale.v1",
            seed=seed,
            metadata={"values": list(values), "variant_key": variant_key},
        ),
    ).seal()
    return series, instances


def pairwise_instances(
    template: ScenarioTemplateArtifact,
    binding: ScenarioBindingArtifact,
    *,
    axes: dict[str, tuple[Any, ...]],
    base_parameters: dict[str, Any],
    variant_key: str,
    seed: int,
    producer: ProducerIdentity,
    maximum_cases: int = 64,
) -> tuple[ScenarioInstanceArtifact, ...]:
    """Deterministic greedy pairwise covering array for finite axes."""
    if not axes:
        return (instantiate(template, binding, parameters=base_parameters, variant_key=variant_key, seed=seed, producer=producer),)
    keys = tuple(sorted(axes))
    candidates = [dict(zip(keys, values)) for values in product(*(axes[key] for key in keys))]
    required: set[tuple[str, Any, str, Any]] = set()
    for left_index, left in enumerate(keys):
        for right in keys[left_index + 1 :]:
            for left_value in axes[left]:
                for right_value in axes[right]:
                    required.add((left, left_value, right, right_value))
    selected: list[dict[str, Any]] = []
    while required and candidates and len(selected) < maximum_cases:
        def contribution(candidate: dict[str, Any]) -> tuple[int, tuple[str, ...]]:
            covered = {
                (left, candidate[left], right, candidate[right])
                for index, left in enumerate(keys)
                for right in keys[index + 1 :]
            }
            return len(covered & required), tuple(repr(candidate[key]) for key in keys)
        best = max(candidates, key=contribution)
        selected.append(best)
        candidates.remove(best)
        required -= {
            (left, best[left], right, best[right])
            for index, left in enumerate(keys)
            for right in keys[index + 1 :]
        }
    if required:
        raise ValueError("maximum_cases is insufficient to satisfy pairwise obligations")
    return tuple(
        instantiate(
            template,
            binding,
            parameters={**base_parameters, **candidate},
            variant_key=variant_key,
            seed=seed + index,
            producer=producer,
            tags=("pairwise-generated",),
        )
        for index, candidate in enumerate(selected)
    )


def contrast(left: ScenarioInstanceArtifact, right: ScenarioInstanceArtifact) -> dict[str, Any]:
    if left.payload.template_ref.artifact_id != right.payload.template_ref.artifact_id:
        raise ValueError("Contrast requires a shared scenario template")
    dimensions: dict[str, dict[str, Any]] = {}
    keys = set(left.payload.parameter_bindings) | set(right.payload.parameter_bindings)
    for key in sorted(keys):
        a = left.payload.parameter_bindings.get(key)
        b = right.payload.parameter_bindings.get(key)
        if a != b:
            dimensions[key] = {"left": a, "right": b}
    if left.payload.variant_key != right.payload.variant_key:
        dimensions["variant_key"] = {"left": left.payload.variant_key, "right": right.payload.variant_key}
    return {
        "template_ref": left.payload.template_ref.artifact_id,
        "binding_compatible": left.payload.binding_ref.artifact_id == right.payload.binding_ref.artifact_id,
        "changed_dimensions": dimensions,
        "left_mutations": [item.mutation_ref.artifact_id for item in left.payload.applied_mutations],
        "right_mutations": [item.mutation_ref.artifact_id for item in right.payload.applied_mutations],
    }
