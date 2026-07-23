from __future__ import annotations

from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import AcademicDatasetGenerator, build_academic_catalog
from planguard.scenario import ScenarioRunner, instantiate
from planguard.store.filesystem import FilesystemArtifactStore


def test_dataset_generation_is_deterministic_and_tenant_scoped() -> None:
    producer = ProducerIdentity(name="test", version="1")
    generator = AcademicDatasetGenerator(producer)
    left, left_manifest = generator.generate(seed=42, scale_profile="small", tenant_skew="dominant")
    right, right_manifest = generator.generate(seed=42, scale_profile="small", tenant_skew="dominant")
    assert left_manifest.payload.dataset_fingerprint == right_manifest.payload.dataset_fingerprint
    assert left_manifest.artifact_id == right_manifest.artifact_id
    assert all(item.institution_id == left.course(item.course_id).institution_id for item in left.plan_items)
    assert left.metadata["tenant_student_counts"][0] > left.metadata["tenant_student_counts"][1]


def test_every_academic_binding_executes_both_variants(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    store = FilesystemArtifactStore(tmp_path)
    catalog.persist(store)
    runner = ScenarioRunner(registry=catalog.registry, store=store, producer=producer)
    results = []
    for binding in catalog.bindings:
        template = catalog.registry.template_for_ref(binding.payload.template_ref.artifact_id)
        for variant in ("naive", "optimized"):
            instance = instantiate(template, binding, parameters={"parent_count": 4, "batch_size": 4, "page_offset": 100}, variant_key=variant, seed=100, producer=producer)
            result = runner.run(instance)
            results.append(result)
            assert result.captured_run is not None
            assert result.scenario_run.payload.analysis_run_ref is not None
            assert result.scenario_run.payload.status in {"succeeded", "failed"}
            assert all(item.status == "satisfied" for item in result.scenario_run.payload.oracle_evaluations[:2])
    assert len(results) == len(catalog.bindings) * 2
    assert len(catalog.templates) >= 8


def test_ordered_mutations_are_applied_and_receipted(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    mutation = catalog.registry.require_mutation("remove-eager-loading.v1")
    instance = instantiate(template, binding, parameters={"parent_count": 5}, variant_key="optimized", mutations=((mutation, {}),), seed=9, producer=producer)
    result = ScenarioRunner(registry=catalog.registry, store=FilesystemArtifactStore(tmp_path), producer=producer).run(instance)
    assert result.captured_run is not None
    assert result.captured_run.analysis.summary.payload.query_count == 6
    apply_receipt = next(item for item in result.receipts if item.payload.phase_key == "apply_mutations")
    assert apply_receipt.payload.statistics["applied_mutations"] == ["remove-eager-loading.v1"]
