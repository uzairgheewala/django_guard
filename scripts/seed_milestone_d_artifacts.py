"""Seed the complete Milestone D scenario catalog and representative laboratory runs."""

from __future__ import annotations

from pathlib import Path

from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import ScenarioRunner, instantiate, pairwise_instances, scale
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex

ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = ROOT / "examples" / "store"


def main() -> None:
    producer = ProducerIdentity(name="planguard", version="0.4.0", build="milestone-d-seed")
    store = FilesystemArtifactStore(STORE_ROOT)
    catalog = build_academic_catalog(producer=producer)
    catalog.persist(store)
    runner = ScenarioRunner(registry=catalog.registry, store=store, producer=producer)

    base_parameters = {
        "scale_profile": "tiny",
        "tenant_skew": "uniform",
        "parent_count": 6,
        "relation_fanout": 6,
        "batch_size": 6,
        "page_offset": 250,
        "transaction_scope": "autocommit",
    }
    scenario_run_ids: list[str] = []
    for index, binding in enumerate(catalog.bindings):
        template = catalog.registry.template_for_ref(binding.payload.template_ref.artifact_id)
        variants = ("naive", "optimized") if index < 4 else ("naive",)
        for variant_index, variant in enumerate(variants):
            mutations = ()
            if template.payload.template_key == "tenant-skew-sensitivity.v1":
                mutation = catalog.registry.require_mutation("remove-composite-tenant-index.v1")
                mutations = ((mutation, {}),)
            if template.payload.template_key == "long-transaction-accumulation.v1":
                mutation = catalog.registry.require_mutation("extend-transaction-scope.v1")
                mutations = ((mutation, {}),)
            instance = instantiate(
                template,
                binding,
                parameters=base_parameters,
                variant_key=variant,
                mutations=mutations,
                seed=4000 + index * 10 + variant_index,
                producer=producer,
                tags=("milestone-d", "academic-lab", "representative"),
            )
            result = runner.run(instance)
            scenario_run_ids.append(result.scenario_run.artifact_id)

    fanout_template = catalog.registry.require_template("relation-access-fanout.v1")
    fanout_binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    series, series_instances = scale(
        fanout_template,
        fanout_binding,
        base_parameters={"scale_profile": "tiny", "relation_fanout": 12},
        dimension="parent_count",
        values=(0, 1, 4, 12),
        variant_key="optimized",
        seed=9000,
        producer=producer,
        series_key="milestone-d.fanout-scale.v1",
    )
    store.save(series)
    for item in series_instances:
        store.save(item)

    skew_template = catalog.registry.require_template("tenant-skew-sensitivity.v1")
    skew_binding = catalog.registry.require_binding("academic.institution-dashboard.v1")
    pairwise = pairwise_instances(
        skew_template,
        skew_binding,
        axes={
            "scale_profile": ("tiny", "small"),
            "tenant_skew": ("uniform", "dominant", "zipf"),
            "transaction_scope": ("autocommit", "long_atomic"),
        },
        base_parameters={},
        variant_key="optimized",
        seed=9500,
        producer=producer,
    )
    for item in pairwise:
        store.save(item)

    count = ArtifactIndex(STORE_ROOT / "registry.sqlite3").rebuild(store)
    print({"scenario_runs": scenario_run_ids, "artifact_count": count, "series": series.artifact_id, "pairwise_instances": len(pairwise)})


if __name__ == "__main__":
    main()
