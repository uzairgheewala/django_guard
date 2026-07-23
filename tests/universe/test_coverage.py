from __future__ import annotations

from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import instantiate
from planguard.universe import (
    build_django_postgres_universe,
    enumerate_coverage_cells,
    evaluate_coverage,
    generate_representative_set,
)


def test_declared_universe_generates_constrained_obligations() -> None:
    producer = ProducerIdentity(name="test", version="1", build="coverage")
    catalog = build_academic_catalog(producer=producer)
    universe = build_django_postgres_universe(
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
    )
    cells = enumerate_coverage_cells(universe, capabilities=universe.payload.target_capabilities)
    assert cells
    assert len(universe.payload.mutation_refs) == len(catalog.mutations)
    assert any(cell.coordinates == {"variant_key": "naive"} for cell in cells)
    assert any(len(cell.coordinates) == 2 for cell in cells)
    assert any(str(cell.status) == "inapplicable" for cell in cells)


def test_representatives_are_deterministic_and_cover_cells() -> None:
    producer = ProducerIdentity(name="test", version="1", build="coverage")
    catalog = build_academic_catalog(producer=producer)
    universe = build_django_postgres_universe(
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
    )
    first, first_instances = generate_representative_set(
        universe,
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
        maximum_cases=12,
        seed=42,
    )
    second, second_instances = generate_representative_set(
        universe,
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
        maximum_cases=12,
        seed=42,
    )
    assert first.artifact_id == second.artifact_id
    assert [item.artifact_id for item in first_instances] == [item.artifact_id for item in second_instances]
    assert first.payload.selections
    contributed: set[str] = set()
    for selection in first.payload.selections:
        marginal = set(selection.covered_cell_keys)
        assert selection.marginal_coverage == len(marginal)
        assert contributed.isdisjoint(marginal)
        contributed.update(marginal)
    assert contributed == set(first.payload.covered_cell_keys)

    report = evaluate_coverage(
        universe,
        instances=first_instances,
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        capabilities=universe.payload.target_capabilities,
        producer=producer,
        representative_set=first,
    )
    assert report.payload.status_counts["covered"] > 0
    assert sum(report.payload.status_counts.values()) == len(report.payload.cells)


def test_direct_instance_covers_declared_axis_values() -> None:
    producer = ProducerIdentity(name="test", version="1", build="coverage")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    instance = instantiate(
        template,
        binding,
        parameters={"scale_profile": "small", "tenant_skew": "dominant", "parent_count": 50},
        variant_key="optimized",
        seed=7,
        producer=producer,
    )
    universe = build_django_postgres_universe(
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
    )
    report = evaluate_coverage(
        universe,
        instances=(instance,),
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        capabilities=universe.payload.target_capabilities,
        producer=producer,
    )
    covered = [cell for cell in report.payload.cells if str(cell.status) == "covered"]
    assert any(cell.coordinates == {"variant_key": "optimized"} for cell in covered)
    assert any(cell.coordinates == {"parent_count": "medium"} for cell in covered)
