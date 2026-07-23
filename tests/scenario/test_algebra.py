from __future__ import annotations

from planguard.artifacts.models import ProducerIdentity
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import contrast, instantiate, pairwise_instances, scale


def test_instance_identity_is_deterministic_and_validates_domains() -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    first = instantiate(template, binding, parameters={"parent_count": 12}, variant_key="naive", seed=7, producer=producer)
    second = instantiate(template, binding, parameters={"parent_count": 12}, variant_key="naive", seed=7, producer=producer)
    assert first.artifact_id == second.artifact_id
    assert first.content_hash == second.content_hash


def test_scale_and_contrast_preserve_explicit_changed_dimensions() -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    series, instances = scale(template, binding, base_parameters={}, dimension="parent_count", values=(1, 10, 100), variant_key="optimized", seed=10, producer=producer)
    assert len(instances) == 3
    assert series.payload.independent_dimensions == ("parent_count",)
    difference = contrast(instances[0], instances[-1])
    assert difference["changed_dimensions"]["parent_count"] == {"left": 1, "right": 100}


def test_pairwise_generator_covers_every_pair() -> None:
    producer = ProducerIdentity(name="test", version="1")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("tenant-skew-sensitivity.v1")
    binding = catalog.registry.require_binding("academic.institution-dashboard.v1")
    axes = {"scale_profile": ("tiny", "small"), "tenant_skew": ("uniform", "dominant", "zipf"), "transaction_scope": ("autocommit", "long_atomic")}
    instances = pairwise_instances(template, binding, axes=axes, base_parameters={}, variant_key="optimized", seed=20, producer=producer)
    for left, left_values in axes.items():
        for right, right_values in axes.items():
            if left >= right:
                continue
            observed = {(item.payload.parameter_bindings[left], item.payload.parameter_bindings[right]) for item in instances}
            assert observed == {(a, b) for a in left_values for b in right_values}
