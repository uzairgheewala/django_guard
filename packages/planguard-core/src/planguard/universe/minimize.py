"""Scenario counterexample minimization and corpus promotion."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from planguard.artifacts.models import (
    CorpusPromotionArtifact,
    CorpusPromotionPayload,
    CounterexampleCandidateArtifact,
    MinimizationRunArtifact,
    MinimizationRunPayload,
    MinimizationStep,
    ProducerIdentity,
    Provenance,
    ScenarioInstanceArtifact,
    ScenarioInstancePayload,
    WorkflowStatus,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch

PredicateEvaluator = Callable[[ScenarioInstanceArtifact], bool]


def scenario_complexity(instance: ScenarioInstanceArtifact) -> float:
    score = float(len(instance.payload.applied_mutations) * 10)
    for key, value in instance.payload.parameter_bindings.items():
        if isinstance(value, bool):
            score += 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            score += max(0.0, float(value))
        elif isinstance(value, str):
            ranks = {
                "tiny": 1,
                "small": 2,
                "medium": 3,
                "large": 4,
                "uniform": 1,
                "dominant": 2,
                "zipf": 3,
                "autocommit": 1,
                "short_atomic": 2,
                "long_atomic": 3,
            }
            score += ranks.get(value, 1)
        else:
            score += 1
    return score


def _candidate_values(key: str, value: Any) -> tuple[Any, ...]:
    if key == "scale_profile" and isinstance(value, str):
        order = ("tiny", "small", "medium", "large")
        if value in order:
            return order[: order.index(value)]
    if key == "tenant_skew" and value != "uniform":
        return ("uniform",)
    if key == "transaction_scope" and value != "autocommit":
        return ("autocommit", "short_atomic")
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        values = {0, 1, max(1, value // 2), value - 1}
        return tuple(sorted(item for item in values if item < value))
    if isinstance(value, float) and value > 0:
        return (0.0, value / 2)
    return ()


def _derived_instance(
    original: ScenarioInstanceArtifact,
    *,
    parameters: dict[str, Any],
    mutation_count: int,
    producer: ProducerIdentity,
) -> ScenarioInstanceArtifact:
    payload = ScenarioInstancePayload(
        template_ref=original.payload.template_ref,
        binding_ref=original.payload.binding_ref,
        parameter_bindings=parameters,
        variant_key=original.payload.variant_key,
        applied_mutations=original.payload.applied_mutations[:mutation_count],
        seed=original.payload.seed,
        series_key=original.payload.series_key,
        composed_from_refs=(original.reference(),),
        projected_dimensions=original.payload.projected_dimensions,
        expected_capabilities=original.payload.expected_capabilities,
        tags=tuple(sorted(set((*original.payload.tags, "minimized-candidate")))),
    )
    artifact_id = content_derived_id("sci", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return ScenarioInstanceArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(input_refs=(original.reference(),), derivation_key="scenario-minimize-candidate.v1"),
        payload=payload,
    ).seal()


def minimize_counterexample(
    *,
    candidate: CounterexampleCandidateArtifact,
    original: ScenarioInstanceArtifact,
    evaluator: PredicateEvaluator,
    producer: ProducerIdentity,
) -> tuple[MinimizationRunArtifact, ScenarioInstanceArtifact]:
    if candidate.payload.scenario_instance_ref and candidate.payload.scenario_instance_ref.artifact_id != original.artifact_id:
        raise ValueError("Counterexample references a different scenario instance")
    if not evaluator(original):
        payload = MinimizationRunPayload(
            candidate_ref=candidate.reference(),
            original_instance_ref=original.reference(),
            status=WorkflowStatus.REJECTED,
            original_complexity=scenario_complexity(original),
            minimized_complexity=None,
            preserved_predicate=candidate.payload.preserved_predicate,
            explanation=("The preserved predicate does not hold for the original instance.",),
        )
        artifact = MinimizationRunArtifact(producer=producer, provenance=Provenance(input_refs=(candidate.reference(), original.reference()), derivation_key="counterexample-minimize.v1"), payload=payload).seal()
        return artifact, original

    current = original
    steps: list[MinimizationStep] = []
    parameters = dict(current.payload.parameter_bindings)
    step_index = 0
    for key in sorted(parameters):
        while True:
            before_value = parameters[key]
            accepted = False
            for replacement in _candidate_values(key, before_value):
                trial_params = dict(parameters)
                trial_params[key] = replacement
                trial = _derived_instance(
                    current,
                    parameters=trial_params,
                    mutation_count=len(current.payload.applied_mutations),
                    producer=producer,
                )
                preserved = evaluator(trial)
                steps.append(MinimizationStep(
                    step_index=step_index,
                    mutation=f"shrink:{key}",
                    before={key: before_value},
                    after={key: replacement},
                    predicate_preserved=preserved,
                    explanation="Accepted because the predicate remained true." if preserved else "Rejected because the predicate no longer held.",
                ))
                step_index += 1
                if preserved:
                    current = trial
                    parameters = trial_params
                    accepted = True
                    break
            if not accepted:
                break
    while current.payload.applied_mutations:
        target_count = len(current.payload.applied_mutations) - 1
        trial = _derived_instance(current, parameters=parameters, mutation_count=target_count, producer=producer)
        preserved = evaluator(trial)
        removed = current.payload.applied_mutations[-1].mutation_ref.artifact_id
        steps.append(MinimizationStep(
            step_index=step_index,
            mutation="remove-mutation",
            before={"mutation": removed},
            after={"mutation": None},
            predicate_preserved=preserved,
            explanation="Accepted because the predicate remained true." if preserved else "Rejected because the predicate required the mutation.",
        ))
        step_index += 1
        if not preserved:
            break
        current = trial

    payload = MinimizationRunPayload(
        candidate_ref=candidate.reference(),
        original_instance_ref=original.reference(),
        minimized_instance_ref=current.reference(),
        status=WorkflowStatus.COMPLETED,
        steps=tuple(steps),
        original_complexity=scenario_complexity(original),
        minimized_complexity=scenario_complexity(current),
        preserved_predicate=candidate.payload.preserved_predicate,
        explanation=("Greedy deterministic shrinking completed.", "The minimizer proves only the configured preserved predicate."),
    )
    artifact_id = content_derived_id("min", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    artifact = MinimizationRunArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(input_refs=(candidate.reference(), original.reference(), current.reference()), derivation_key="counterexample-minimize.v1"),
        payload=payload,
    ).seal()
    return artifact, current


def promote_counterexample(
    *,
    candidate: CounterexampleCandidateArtifact,
    source_instance: ScenarioInstanceArtifact,
    producer: ProducerIdentity,
    minimization: MinimizationRunArtifact | None = None,
    target_collections: tuple[str, ...] = ("scenario_corpus", "detector_fixture"),
    reviewer_notes: tuple[str, ...] = (),
) -> CorpusPromotionArtifact:
    promoted_ref = minimization.payload.minimized_instance_ref if minimization and minimization.payload.minimized_instance_ref else source_instance.reference()
    payload = CorpusPromotionPayload(
        candidate_ref=candidate.reference(),
        minimization_ref=minimization.reference() if minimization else None,
        source_instance_ref=source_instance.reference(),
        status=WorkflowStatus.COMPLETED,
        target_collections=target_collections,  # type: ignore[arg-type]
        promoted_artifact_refs=(promoted_ref,),
        reviewer_notes=reviewer_notes,
        promotion_key=f"corpus:{candidate.artifact_id}",
    )
    artifact_id = content_derived_id("prom", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return CorpusPromotionArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(input_refs=(candidate.reference(), source_instance.reference(), *((minimization.reference(),) if minimization else ())), derivation_key="corpus-promotion.v1"),
        payload=payload,
    ).seal()
