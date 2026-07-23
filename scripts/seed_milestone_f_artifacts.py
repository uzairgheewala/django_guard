"""Seed Milestone F universe, coverage, novelty, and corpus-evolution artifacts."""

from __future__ import annotations

from pathlib import Path

from planguard.analysis.load import load_analysis_bundle
from planguard.artifacts.models import (
    CounterexampleLabel,
    MutationDefinitionArtifact,
    NoveltySignatureArtifact,
    PreservedPredicate,
    ProducerIdentity,
    ScenarioBindingArtifact,
    ScenarioInstanceArtifact,
    ScenarioRunArtifact,
    ScenarioTemplateArtifact,
)
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import ScenarioRunner
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex
from planguard.universe import (
    build_django_postgres_universe,
    create_counterexample,
    evaluate_coverage,
    evaluate_novelty,
    generate_representative_set,
    minimize_counterexample,
    promote_counterexample,
)

ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = ROOT / "examples" / "store"


def all_of(store: FilesystemArtifactStore, kind: str, model):
    return tuple(
        item
        for item in (store.load(record.artifact_id) for record in store.list(artifact_kind=kind))
        if isinstance(item, model)
    )


def main() -> None:
    producer = ProducerIdentity(name="planguard", version="0.6.0", build="milestone-f-seed")
    store = FilesystemArtifactStore(STORE_ROOT)
    catalog = build_academic_catalog(producer=producer)
    catalog.persist(store)

    universe = build_django_postgres_universe(
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
    )
    store.save(universe)

    representative, instances = generate_representative_set(
        universe,
        templates=catalog.templates,
        bindings=catalog.bindings,
        mutations=catalog.mutations,
        producer=producer,
        maximum_cases=16,
        seed=20260723,
    )
    store.save(representative)
    for instance in instances:
        store.save(instance)

    runner = ScenarioRunner(registry=catalog.registry, store=store, producer=producer)
    execution_results = tuple(runner.run(instance) for instance in instances[:4])

    novelty_items: list[NoveltySignatureArtifact] = []
    for result in execution_results:
        if not result.captured_run:
            continue
        manifest, bundle = load_analysis_bundle(store, result.captured_run.manifest.artifact_id)
        novelty = evaluate_novelty(
            subject=manifest,
            bundle=bundle,
            corpus=tuple(novelty_items),
            producer=producer,
        )
        store.save(novelty)
        novelty_items.append(novelty)

    templates = all_of(store, "scenario_template", ScenarioTemplateArtifact)
    bindings = all_of(store, "scenario_binding", ScenarioBindingArtifact)
    mutations = all_of(store, "mutation_definition", MutationDefinitionArtifact)
    all_instances = all_of(store, "scenario_instance", ScenarioInstanceArtifact)
    all_runs = all_of(store, "scenario_run", ScenarioRunArtifact)
    coverage = evaluate_coverage(
        universe,
        instances=all_instances,
        runs=all_runs,
        templates=templates,
        bindings=bindings,
        mutations=mutations,
        capabilities=universe.payload.target_capabilities,
        producer=producer,
        representative_set=representative,
        novelty_refs=tuple(item.reference() for item in novelty_items if str(item.payload.status) in {"novel", "partial"}),
    )
    store.save(coverage)

    source_result = execution_results[0]
    source_manifest = source_result.captured_run.manifest if source_result.captured_run else source_result.scenario_run
    source_instance = instances[0]
    predicate = PreservedPredicate(
        predicate_key="minimum-parent-count.v1",
        kind="custom",
        parameters={"minimum_parent_count": 2},
        description="The minimized workload retains at least two parent rows.",
    )
    candidate = create_counterexample(
        source=source_manifest,
        label=CounterexampleLabel.FALSE_POSITIVE,
        predicate=predicate,
        producer=producer,
        scenario_instance=source_instance,
        novelty=novelty_items[0] if novelty_items else None,
        notes=("Seeded example of the counterexample lifecycle.",),
        tags=("milestone-f", "seeded"),
    )
    store.save(candidate)
    minimization, minimized = minimize_counterexample(
        candidate=candidate,
        original=source_instance,
        evaluator=lambda item: int(item.payload.parameter_bindings.get("parent_count", 0)) >= 2,
        producer=producer,
    )
    store.save(minimized)
    store.save(minimization)
    promotion = promote_counterexample(
        candidate=candidate,
        source_instance=source_instance,
        minimization=minimization,
        producer=producer,
        reviewer_notes=("Seed promotion reviewed for the example corpus.",),
    )
    store.save(promotion)

    count = ArtifactIndex(STORE_ROOT / "registry.sqlite3").rebuild(store)
    print({
        "universe_id": universe.artifact_id,
        "representative_set_id": representative.artifact_id,
        "coverage_report_id": coverage.artifact_id,
        "selected_cases": len(instances),
        "executed_cases": len(execution_results),
        "novelty_signatures": len(novelty_items),
        "counterexample_id": candidate.artifact_id,
        "minimization_id": minimization.artifact_id,
        "promotion_id": promotion.artifact_id,
        "artifact_count": count,
    })


if __name__ == "__main__":
    main()
