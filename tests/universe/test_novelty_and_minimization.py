from __future__ import annotations

from planguard.artifacts.models import (
    CounterexampleLabel,
    PreservedPredicate,
    ProducerIdentity,
)
from planguard.capture import AnalysisSession
from planguard.lab.academic import build_academic_catalog
from planguard.scenario import instantiate
from planguard.universe import (
    create_counterexample,
    evaluate_novelty,
    minimize_counterexample,
    promote_counterexample,
)


def _captured(tmp_path, name: str, count: int):
    with AnalysisSession(name, store=tmp_path / name, attach_django=False) as session:
        for index in range(count):
            session.record_query("SELECT * FROM course WHERE id = %s", [index], duration_ms=1)
    return session


def test_novelty_distinguishes_exact_and_new_signatures(tmp_path) -> None:
    producer = ProducerIdentity(name="test", version="1", build="novelty")
    first = _captured(tmp_path, "first", 3)
    known = evaluate_novelty(
        subject=first.manifest,
        bundle=first.analysis,
        corpus=(),
        producer=producer,
    )
    assert str(known.payload.status) == "novel"

    same = evaluate_novelty(
        subject=first.manifest,
        bundle=first.analysis,
        corpus=(known,),
        producer=producer,
    )
    assert str(same.payload.status) == "known"

    second = _captured(tmp_path, "second", 20)
    changed = evaluate_novelty(
        subject=second.manifest,
        bundle=second.analysis,
        corpus=(known,),
        producer=producer,
    )
    assert str(changed.payload.status) in {"novel", "partial"}
    assert changed.payload.signature_hash != known.payload.signature_hash


def test_counterexample_minimization_and_promotion() -> None:
    producer = ProducerIdentity(name="test", version="1", build="minimize")
    catalog = build_academic_catalog(producer=producer)
    template = catalog.registry.require_template("relation-access-fanout.v1")
    binding = catalog.registry.require_binding("academic.plan-item-course.v1")
    instance = instantiate(
        template,
        binding,
        parameters={"parent_count": 100, "relation_fanout": 20, "scale_profile": "large"},
        variant_key="naive",
        seed=3,
        producer=producer,
    )
    predicate = PreservedPredicate(
        predicate_key="still-repeats",
        kind="custom",
        parameters={"minimum_parent_count": 2},
        description="The reduced case still has at least two parents.",
    )
    candidate = create_counterexample(
        source=instance,
        label=CounterexampleLabel.FALSE_POSITIVE,
        predicate=predicate,
        producer=producer,
        scenario_instance=instance,
    )

    minimization, minimized = minimize_counterexample(
        candidate=candidate,
        original=instance,
        evaluator=lambda item: int(item.payload.parameter_bindings.get("parent_count", 0)) >= 2,
        producer=producer,
    )
    assert str(minimization.payload.status) == "completed"
    assert minimization.payload.minimized_complexity < minimization.payload.original_complexity
    assert int(minimized.payload.parameter_bindings["parent_count"]) == 2

    promotion = promote_counterexample(
        candidate=candidate,
        source_instance=instance,
        minimization=minimization,
        producer=producer,
        reviewer_notes=("Reviewed in test.",),
    )
    assert str(promotion.payload.status) == "completed"
    assert promotion.payload.promoted_artifact_refs[0].artifact_id == minimized.artifact_id
