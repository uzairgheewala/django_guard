"""Constrained universe enumeration, coverage evaluation, and greedy representatives."""

from __future__ import annotations

from collections import defaultdict
from itertools import combinations, product
from typing import Any, Iterable

from planguard.artifacts.models import (
    ArtifactReference,
    CoverageCell,
    CoverageCellStatus,
    CoverageReportArtifact,
    CoverageReportPayload,
    DimensionCoverage,
    InteractionCoverage,
    MutationDefinitionArtifact,
    ParameterDomain,
    ParameterDomainKind,
    ProducerIdentity,
    Provenance,
    RepresentativeSelection,
    RepresentativeSetArtifact,
    RepresentativeSetPayload,
    ScenarioBindingArtifact,
    ScenarioInstanceArtifact,
    ScenarioRunArtifact,
    ScenarioTemplateArtifact,
    UniverseAxis,
    UniverseConstraint,
    UniversePredicate,
    UniverseProfileArtifact,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.scenario.algebra import instantiate
from planguard.time import semantic_epoch


def _partition_for_value(domain: ParameterDomain, value: Any) -> str:
    if domain.kind != ParameterDomainKind.PARTITIONED:
        return str(value)
    for partition in domain.partitions:
        if value is None:
            continue
        lower = partition.minimum is None or value > partition.minimum or (partition.include_minimum and value == partition.minimum)
        upper = partition.maximum is None or value < partition.maximum or (partition.include_maximum and value == partition.maximum)
        if lower and upper:
            return partition.key
    return "unknown"


def representative_values(axis: UniverseAxis) -> tuple[tuple[str, Any], ...]:
    domain = axis.domain
    if domain.kind == ParameterDomainKind.FINITE:
        return tuple((str(value), value) for value in domain.values)
    if domain.kind == ParameterDomainKind.BOOLEAN:
        return (("false", False), ("true", True))
    if domain.kind == ParameterDomainKind.PARTITIONED:
        output: list[tuple[str, Any]] = []
        for partition in domain.partitions:
            if partition.representative_values:
                output.append((partition.key, partition.representative_values[0]))
            elif partition.minimum is not None:
                output.append((partition.key, partition.minimum))
        return tuple(output)
    if domain.kind in {ParameterDomainKind.INTEGER_RANGE, ParameterDomainKind.FLOAT_RANGE}:
        values = [domain.minimum, domain.default, domain.maximum]
        unique: list[Any] = []
        for value in values:
            if value is not None and value not in unique:
                unique.append(value)
        return tuple((str(value), value) for value in unique)
    return (("default", domain.default),) if domain.default is not None else ()


def coordinates_for_instance(
    instance: ScenarioInstanceArtifact,
    *,
    template: ScenarioTemplateArtifact,
    binding: ScenarioBindingArtifact,
) -> dict[str, Any]:
    coordinates: dict[str, Any] = {
        "template_key": template.payload.template_key,
        "binding_key": binding.payload.binding_key,
        "variant_key": instance.payload.variant_key,
        "mutation_key": (
            instance.payload.applied_mutations[0].mutation_ref.artifact_id
            if instance.payload.applied_mutations
            else "none"
        ),
    }
    for key, value in instance.payload.parameter_bindings.items():
        coordinates[key] = value
    return coordinates


def _lookup(mapping: dict[str, Any], field: str) -> Any:
    return mapping.get(field)


def _predicate_matches(predicate: UniversePredicate, coordinates: dict[str, Any]) -> bool:
    actual = _lookup(coordinates, predicate.field)
    expected = predicate.value
    if predicate.operator == "exists":
        return predicate.field in coordinates
    if predicate.field not in coordinates:
        return False
    if predicate.operator == "equals":
        return actual == expected
    if predicate.operator == "not_equals":
        return actual != expected
    if predicate.operator == "in":
        return actual in tuple(expected or ())
    if predicate.operator == "not_in":
        return actual not in tuple(expected or ())
    if actual is None:
        return False
    if predicate.operator == "greater_than":
        return actual > expected
    if predicate.operator == "greater_or_equal":
        return actual >= expected
    if predicate.operator == "less_than":
        return actual < expected
    if predicate.operator == "less_or_equal":
        return actual <= expected
    return False


def constraint_status(
    coordinates: dict[str, Any],
    constraints: tuple[UniverseConstraint, ...],
    *,
    capabilities: set[str],
) -> tuple[CoverageCellStatus | None, tuple[str, ...], tuple[str, ...]]:
    reasons: list[str] = []
    gaps: list[str] = []
    for constraint in constraints:
        when_applies = all(_predicate_matches(item, coordinates) for item in constraint.when)
        if not when_applies:
            continue
        missing = sorted(set(constraint.required_capabilities) - capabilities)
        if missing:
            gaps.extend(missing)
            reasons.append(constraint.explanation)
            return CoverageCellStatus.UNSUPPORTED, tuple(reasons), tuple(gaps)
        if constraint.require and not all(_predicate_matches(item, coordinates) for item in constraint.require):
            reasons.append(constraint.explanation)
            if constraint.kind.value in {"exclusion", "applicability"}:
                return CoverageCellStatus.INAPPLICABLE, tuple(reasons), tuple(gaps)
            return CoverageCellStatus.UNKNOWN, tuple(reasons), tuple(gaps)
        if constraint.excluded:
            reasons.append(constraint.explanation)
            return CoverageCellStatus.INAPPLICABLE, tuple(reasons), tuple(gaps)
    return None, tuple(reasons), tuple(gaps)


def enumerate_coverage_cells(
    universe: UniverseProfileArtifact,
    *,
    capabilities: Iterable[str] = (),
) -> tuple[CoverageCell, ...]:
    """Enumerate obligation cells without constructing a full Cartesian product."""

    axis_values = {axis.axis_key: representative_values(axis) for axis in universe.payload.axes}
    axis_by_key = {axis.axis_key: axis for axis in universe.payload.axes}
    cells: list[CoverageCell] = []
    capability_set = set(capabilities)

    def append_cell(coordinates: dict[str, str], strategy_key: str) -> None:
        status, reasons, gaps = constraint_status(coordinates, universe.payload.constraints, capabilities=capability_set)
        risk = 1.0
        for key in coordinates:
            if key in axis_by_key:
                risk *= max(axis_by_key[key].risk_weight, 0.01)
        raw = {"coordinates": coordinates, "strategy": strategy_key}
        cell_key = content_derived_id("cell", canonical_json_bytes(raw), length=24)
        cells.append(CoverageCell(
            cell_key=cell_key,
            coordinates=coordinates,
            status=status or CoverageCellStatus.UNCOVERED,
            strategy_keys=(strategy_key,),
            capability_gaps=gaps,
            reasons=reasons,
            risk_weight=risk,
        ))

    for strategy in sorted(universe.payload.strategies, key=lambda item: (item.priority, item.strategy_key)):
        dimensions = tuple(item for item in strategy.dimensions if item in axis_values)
        if strategy.kind in {"partition", "boundary", "motif", "mutation"}:
            for dimension in dimensions:
                for label, _value in axis_values[dimension]:
                    append_cell({dimension: label}, strategy.strategy_key)
        elif strategy.kind in {"pairwise", "metamorphic"}:
            for left, right in combinations(dimensions, 2):
                for (left_label, _), (right_label, _) in product(axis_values[left], axis_values[right]):
                    append_cell({left: left_label, right: right_label}, strategy.strategy_key)
        elif strategy.kind == "three_way":
            for dims in combinations(dimensions, 3):
                for values in product(*(axis_values[item] for item in dims)):
                    append_cell({key: value[0] for key, value in zip(dims, values, strict=True)}, strategy.strategy_key)

    merged: dict[tuple[tuple[str, str], ...], CoverageCell] = {}
    for cell in cells:
        key = tuple(sorted((str(k), str(v)) for k, v in cell.coordinates.items()))
        existing = merged.get(key)
        if existing is None:
            merged[key] = cell
        else:
            merged[key] = existing.model_copy(update={
                "strategy_keys": tuple(sorted(set(existing.strategy_keys + cell.strategy_keys))),
                "risk_weight": max(existing.risk_weight, cell.risk_weight),
            })
    return tuple(sorted(merged.values(), key=lambda item: item.cell_key))


def _instance_axis_coordinates(
    universe: UniverseProfileArtifact,
    instance: ScenarioInstanceArtifact,
    template: ScenarioTemplateArtifact,
    binding: ScenarioBindingArtifact,
    mutation_by_id: dict[str, MutationDefinitionArtifact],
) -> dict[str, str]:
    axis_by_key = {axis.axis_key: axis for axis in universe.payload.axes}
    coords = coordinates_for_instance(instance, template=template, binding=binding)
    if instance.payload.applied_mutations:
        mutation = mutation_by_id.get(instance.payload.applied_mutations[0].mutation_ref.artifact_id)
        coords["mutation_key"] = mutation.payload.mutation_key if mutation else "unknown"
    for key, value in tuple(coords.items()):
        axis = axis_by_key.get(key)
        if axis:
            coords[key] = _partition_for_value(axis.domain, value) if axis.domain.kind == ParameterDomainKind.PARTITIONED else str(value)
    return coords


def _cell_matches(cell: CoverageCell, coordinates: dict[str, str]) -> bool:
    return all(coordinates.get(key) == str(value) for key, value in cell.coordinates.items())


def evaluate_coverage(
    universe: UniverseProfileArtifact,
    *,
    instances: Iterable[ScenarioInstanceArtifact],
    runs: Iterable[ScenarioRunArtifact] = (),
    templates: Iterable[ScenarioTemplateArtifact],
    bindings: Iterable[ScenarioBindingArtifact],
    mutations: Iterable[MutationDefinitionArtifact] = (),
    capabilities: Iterable[str] = (),
    producer: ProducerIdentity,
    representative_set: RepresentativeSetArtifact | None = None,
    novelty_refs: tuple[ArtifactReference, ...] = (),
) -> CoverageReportArtifact:
    cells = list(enumerate_coverage_cells(universe, capabilities=capabilities))
    template_by_id = {item.artifact_id: item for item in templates}
    binding_by_id = {item.artifact_id: item for item in bindings}
    mutation_by_id = {item.artifact_id: item for item in mutations}
    instance_list = tuple(instances)
    runs_by_instance: dict[str, list[ScenarioRunArtifact]] = defaultdict(list)
    for run in runs:
        runs_by_instance[run.payload.scenario_instance_ref.artifact_id].append(run)

    for index, cell in enumerate(cells):
        if cell.status in {CoverageCellStatus.INAPPLICABLE, CoverageCellStatus.UNSUPPORTED}:
            continue
        instance_refs: list[ArtifactReference] = []
        run_refs: list[ArtifactReference] = []
        for instance in instance_list:
            template = template_by_id.get(instance.payload.template_ref.artifact_id)
            binding = binding_by_id.get(instance.payload.binding_ref.artifact_id)
            if not template or not binding:
                continue
            coords = _instance_axis_coordinates(universe, instance, template, binding, mutation_by_id)
            if _cell_matches(cell, coords):
                instance_refs.append(instance.reference())
                run_refs.extend(item.reference() for item in runs_by_instance.get(instance.artifact_id, ()))
        if instance_refs:
            cells[index] = cell.model_copy(update={
                "status": CoverageCellStatus.COVERED,
                "scenario_instance_refs": tuple(instance_refs),
                "scenario_run_refs": tuple(run_refs),
                "reasons": (*cell.reasons, f"Covered by {len(instance_refs)} scenario instance(s)."),
            })

    axis_values: dict[str, set[str]] = defaultdict(set)
    status_axis_values: dict[str, dict[CoverageCellStatus, set[str]]] = defaultdict(lambda: defaultdict(set))
    for cell in cells:
        if len(cell.coordinates) == 1:
            axis, value = next(iter(cell.coordinates.items()))
            axis_values[axis].add(str(value))
            status_axis_values[axis][cell.status].add(str(value))
    dimensions = tuple(
        DimensionCoverage(
            axis_key=axis,
            covered_values=tuple(sorted(status_axis_values[axis][CoverageCellStatus.COVERED])),
            uncovered_values=tuple(sorted(status_axis_values[axis][CoverageCellStatus.UNCOVERED])),
            unsupported_values=tuple(sorted(status_axis_values[axis][CoverageCellStatus.UNSUPPORTED])),
            inapplicable_values=tuple(sorted(status_axis_values[axis][CoverageCellStatus.INAPPLICABLE])),
        )
        for axis in sorted(axis_values)
    )
    interactions: list[InteractionCoverage] = []
    for strategy in universe.payload.strategies:
        matching = [cell for cell in cells if strategy.strategy_key in cell.strategy_keys and len(cell.coordinates) > 1 and cell.status != CoverageCellStatus.INAPPLICABLE]
        covered = sum(cell.status == CoverageCellStatus.COVERED for cell in matching)
        total = len(matching)
        interactions.append(InteractionCoverage(strategy_key=strategy.strategy_key, covered=covered, total=total, ratio=(covered / total if total else 1.0)))
    counts: dict[str, int] = {}
    for cell in cells:
        counts[str(cell.status)] = counts.get(str(cell.status), 0) + 1
    payload = CoverageReportPayload(
        universe_ref=universe.reference(),
        representative_set_ref=representative_set.reference() if representative_set else None,
        evaluated_instance_refs=tuple(item.reference() for item in instance_list),
        evaluated_run_refs=tuple(item.reference() for item in runs),
        cells=tuple(cells),
        dimension_coverage=dimensions,
        interaction_coverage=tuple(interactions),
        status_counts=counts,
        capability_gaps=tuple(sorted(set(gap for cell in cells for gap in cell.capability_gaps))),
        novel_observation_refs=novelty_refs,
        limitations=("Coverage is relative to the declared profile and available application bindings.",),
    )
    artifact_id = content_derived_id("cov", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return CoverageReportArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(
            input_refs=(universe.reference(), *(item.reference() for item in instance_list), *(item.reference() for item in runs), *((representative_set.reference(),) if representative_set else ())),
            derivation_key="universe-coverage-evaluate.v1",
        ),
        payload=payload,
    ).seal()


def generate_representative_set(
    universe: UniverseProfileArtifact,
    *,
    templates: Iterable[ScenarioTemplateArtifact],
    bindings: Iterable[ScenarioBindingArtifact],
    mutations: Iterable[MutationDefinitionArtifact],
    producer: ProducerIdentity,
    maximum_cases: int = 24,
    seed: int = 1,
    strategy_keys: tuple[str, ...] = ("axis-partitions.v1", "high-risk-pairwise.v1", "mutation-coverage.v1"),
) -> tuple[RepresentativeSetArtifact, tuple[ScenarioInstanceArtifact, ...]]:
    templates_by_id = {item.artifact_id: item for item in templates}
    bindings_list = tuple(bindings)
    mutations_list = tuple(mutations)
    mutation_by_key = {item.payload.mutation_key: item for item in mutations_list}
    cells = tuple(cell for cell in enumerate_coverage_cells(universe, capabilities=universe.payload.target_capabilities) if cell.status == CoverageCellStatus.UNCOVERED and set(cell.strategy_keys).intersection(strategy_keys))
    axis_by_key = {axis.axis_key: axis for axis in universe.payload.axes}

    candidates: list[ScenarioInstanceArtifact] = []
    for binding in bindings_list:
        template = templates_by_id.get(binding.payload.template_ref.artifact_id)
        if not template:
            continue
        common_defaults = {item.parameter_key: item.domain.default for item in template.payload.parameters if item.domain.default is not None}
        variations: list[dict[str, Any]] = [dict(common_defaults)]
        for key in ("scale_profile", "tenant_skew", "parent_count", "relation_fanout", "transaction_scope"):
            axis = axis_by_key.get(key)
            if not axis:
                continue
            for _label, value in representative_values(axis):
                params = dict(common_defaults)
                params[key] = value
                variations.append(params)
        for variant in ("naive", "optimized"):
            for index, params in enumerate(variations):
                candidates.append(instantiate(template, binding, parameters=params, variant_key=variant, seed=seed + index, producer=producer, tags=("representative-candidate",)))
        for mutation in mutations_list:
            compatible = mutation.payload.compatible_template_keys
            if compatible and template.payload.template_key not in compatible:
                continue
            params = dict(common_defaults)
            if mutation.payload.mutation_key == "increase-tenant-skew.v1":
                params["tenant_skew"] = "dominant"
            if mutation.payload.mutation_key == "extend-transaction-scope.v1":
                params["transaction_scope"] = "long_atomic"
            candidates.append(instantiate(template, binding, parameters=params, variant_key="naive", mutations=((mutation, {}),), seed=seed + 100 + len(candidates), producer=producer, tags=("representative-candidate", "mutation")))

    def candidate_cells(instance: ScenarioInstanceArtifact) -> set[str]:
        template = templates_by_id[instance.payload.template_ref.artifact_id]
        binding = next(item for item in bindings_list if item.artifact_id == instance.payload.binding_ref.artifact_id)
        coords = _instance_axis_coordinates(universe, instance, template, binding, {item.artifact_id: item for item in mutations_list})
        return {cell.cell_key for cell in cells if _cell_matches(cell, coords)}

    remaining = {cell.cell_key for cell in cells}
    selected: list[tuple[ScenarioInstanceArtifact, set[str], float]] = []
    candidate_map = [(item, candidate_cells(item)) for item in candidates]
    while remaining and len(selected) < maximum_cases:
        best = None
        for candidate, covered in candidate_map:
            marginal = covered & remaining
            if not marginal:
                continue
            score = sum(next(cell.risk_weight for cell in cells if cell.cell_key == key) for key in marginal)
            rank = (score, len(marginal), candidate.artifact_id)
            if best is None or rank > best[0]:
                best = (rank, candidate, covered, marginal)
        if best is None:
            break
        _, candidate, covered, marginal = best
        selected.append((candidate, marginal, float(best[0][0])))
        remaining -= marginal
        candidate_map = [(item, cells_for_item) for item, cells_for_item in candidate_map if item.artifact_id != candidate.artifact_id]

    selections = tuple(
        RepresentativeSelection(
            scenario_instance_ref=instance.reference(),
            covered_cell_keys=tuple(sorted(covered)),
            marginal_coverage=len(covered),
            score=score,
            rationale=("Greedy maximum-risk-weight coverage selection.",),
        )
        for instance, covered, score in selected
    )
    payload = RepresentativeSetPayload(
        universe_ref=universe.reference(),
        strategy_keys=strategy_keys,
        maximum_cases=maximum_cases,
        seed=seed,
        selections=selections,
        covered_cell_keys=tuple(sorted(set().union(*(covered for _, covered, _ in selected)) if selected else set())),
        uncovered_cell_keys=tuple(sorted(remaining)),
        unsupported_cell_keys=(),
        generation_notes=("Candidates are application bindings of generic templates; selection is deterministic for a fixed catalog and seed.",),
    )
    artifact_id = content_derived_id("rset", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    artifact = RepresentativeSetArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(
            input_refs=(universe.reference(), *(item.reference() for item in templates), *(item.reference() for item in bindings), *(item.reference() for item in mutations)),
            derivation_key="representative-set-greedy.v1",
        ),
        payload=payload,
    ).seal()
    return artifact, tuple(item[0] for item in selected)
