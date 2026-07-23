"""Behavioral signatures, novelty classification, and counterexample capture."""

from __future__ import annotations

from collections import Counter
from typing import Iterable

from planguard.analysis.engine import AnalysisBundle
from planguard.artifacts.models import (
    ArtifactDocument,
    ArtifactReference,
    CounterexampleCandidateArtifact,
    CounterexampleCandidatePayload,
    CounterexampleLabel,
    NoveltySignatureArtifact,
    NoveltySignaturePayload,
    NoveltyStatus,
    PreservedPredicate,
    ProducerIdentity,
    Provenance,
    ScenarioInstanceArtifact,
    WorkflowStatus,
)
from planguard.canonical import canonical_json_bytes, content_hash
from planguard.ids import content_derived_id
from planguard.time import semantic_epoch


def _bucket(value: int) -> str:
    if value == 0:
        return "zero"
    if value == 1:
        return "one"
    if value <= 5:
        return "small"
    if value <= 25:
        return "medium"
    if value <= 100:
        return "large"
    return "very_large"


def _walk_plan_nodes(node) -> list[str]:
    output = [node.node_type]
    for child in node.children:
        output.extend(_walk_plan_nodes(child))
    return output


def feature_vector(bundle: AnalysisBundle) -> dict[str, object]:
    statements = Counter(item.payload.statement_kind for item in bundle.templates)
    family_buckets = Counter(_bucket(item.payload.aggregates.execution_count) for item in bundle.families)
    plan_nodes: Counter[str] = Counter()
    for plan in bundle.plan_observations:
        plan_nodes.update(_walk_plan_nodes(plan.payload.root))
    return {
        "query_count_bucket": _bucket(len(bundle.executions)),
        "template_count": len(bundle.templates),
        "family_count": len(bundle.families),
        "statement_kinds": dict(sorted(statements.items())),
        "query_shapes": sorted({item.payload.structural_shape_fingerprint for item in bundle.templates}),
        "family_execution_buckets": dict(sorted(family_buckets.items())),
        "motifs": sorted({item.payload.motif_key for item in bundle.workload_episodes}),
        "finding_mechanisms": sorted({item.payload.mechanism_key for item in bundle.findings}),
        "plan_node_types": dict(sorted(plan_nodes.items())),
        "plan_shape_fingerprints": sorted({item.payload.features.plan_shape_fingerprint for item in bundle.plan_observations}),
    }


def _feature_tokens(features: dict[str, object]) -> set[str]:
    tokens: set[str] = set()
    for key, value in features.items():
        if isinstance(value, dict):
            tokens.update(f"{key}:{subkey}={subvalue}" for subkey, subvalue in value.items())
        elif isinstance(value, list):
            tokens.update(f"{key}:{item}" for item in value)
        else:
            tokens.add(f"{key}:{value}")
    return tokens


def _distance(left: dict[str, object], right: dict[str, object]) -> float:
    a = _feature_tokens(left)
    b = _feature_tokens(right)
    if not a and not b:
        return 0.0
    return 1.0 - (len(a & b) / len(a | b))


def evaluate_novelty(
    *,
    subject: ArtifactDocument,
    bundle: AnalysisBundle,
    corpus: Iterable[NoveltySignatureArtifact],
    producer: ProducerIdentity,
) -> NoveltySignatureArtifact:
    features = feature_vector(bundle)
    signature_hash = content_hash(features)
    corpus_items = tuple(corpus)
    exact = [item for item in corpus_items if item.payload.signature_hash == signature_hash]
    nearest: list[tuple[float, NoveltySignatureArtifact]] = sorted(
        ((_distance(features, item.payload.feature_vector), item) for item in corpus_items),
        key=lambda item: (item[0], item[1].artifact_id),
    )
    if exact:
        status = NoveltyStatus.KNOWN
        novel_dimensions: tuple[str, ...] = ()
        distance = 0.0
        refs = tuple(item.reference() for item in exact[:5])
        explanation = ("An exact behavioral signature already exists in the corpus.",)
    else:
        distance = nearest[0][0] if nearest else None
        status = NoveltyStatus.PARTIAL if distance is not None and distance <= 0.25 else NoveltyStatus.NOVEL
        known_tokens = set().union(*(_feature_tokens(item.payload.feature_vector) for item in corpus_items)) if corpus_items else set()
        novel_dimensions = tuple(sorted(_feature_tokens(features) - known_tokens))
        refs = tuple(item.reference() for _, item in nearest[:5])
        explanation = (
            "No exact signature exists in the current corpus.",
            f"Nearest behavioral distance: {distance:.3f}." if distance is not None else "The corpus is empty.",
        )
    payload = NoveltySignaturePayload(
        subject_ref=subject.reference(),
        feature_vector=features,
        signature_hash=signature_hash,
        status=status,
        novel_dimensions=novel_dimensions,
        nearest_signature_refs=refs,
        distance=distance,
        corpus_size=len(corpus_items),
        explanation=explanation,
    )
    artifact_id = content_derived_id("nov", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return NoveltySignatureArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(input_refs=(subject.reference(), *refs), derivation_key="behavioral-novelty.v1"),
        payload=payload,
    ).seal()


def create_counterexample(
    *,
    source: ArtifactDocument,
    label: CounterexampleLabel,
    predicate: PreservedPredicate,
    producer: ProducerIdentity,
    scenario_instance: ScenarioInstanceArtifact | None = None,
    novelty: NoveltySignatureArtifact | None = None,
    notes: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
) -> CounterexampleCandidateArtifact:
    payload = CounterexampleCandidatePayload(
        source_ref=source.reference(),
        label=label,
        preserved_predicate=predicate,
        scenario_instance_ref=scenario_instance.reference() if scenario_instance else None,
        novelty_signature_ref=novelty.reference() if novelty else None,
        status=WorkflowStatus.CREATED,
        reporter_notes=notes,
        tags=tags,
    )
    artifact_id = content_derived_id("cex", canonical_json_bytes({"payload": payload, "producer": producer.model_dump(mode="python")}), length=32)
    return CounterexampleCandidateArtifact(
        created_at=semantic_epoch(),
        artifact_id=artifact_id,
        producer=producer,
        provenance=Provenance(
            input_refs=(source.reference(), *((scenario_instance.reference(),) if scenario_instance else ()), *((novelty.reference(),) if novelty else ())),
            derivation_key="counterexample-capture.v1",
        ),
        payload=payload,
    ).seal()
