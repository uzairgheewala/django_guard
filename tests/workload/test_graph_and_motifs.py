from __future__ import annotations

from planguard.analysis.engine import AnalysisEngine
from planguard.analysis.workload import build_workload
from planguard.artifacts.models import (
    ParameterDescriptor,
    ProducerIdentity,
    QueryConnection,
    QueryExecutionArtifact,
    QueryExecutionPayload,
    QueryOutcome,
    QueryTiming,
    QueryTransaction,
    RawSqlMode,
    WorkloadEdgeKind,
)


def execution(run_id: str, sequence: int, sql: str, parameter: int, *, rows: int, transaction: bool = True):
    return QueryExecutionArtifact(
        producer=ProducerIdentity(name="test", version="1"),
        payload=QueryExecutionPayload(
            run_id=run_id,
            sequence_number=sequence,
            connection=QueryConnection(alias="default", vendor="postgresql"),
            timing=QueryTiming(started_offset_ms=float(sequence), duration_ms=1.0),
            raw_sql_mode=RawSqlMode.PRESERVE,
            sql=sql,
            parameters=(ParameterDescriptor(type_name="int", value_hash=f"h{parameter}"),),
            parameter_binding_fingerprint=f"binding-{parameter}",
            transaction=QueryTransaction(
                transaction_id=f"{run_id}:txn:1" if transaction else None,
                depth=1 if transaction else 0,
                autocommit=not transaction,
            ),
            outcome=QueryOutcome(status="succeeded", row_count=rows),
        ),
    ).seal()


def test_workload_graph_preserves_inference_and_episode_separation() -> None:
    run_id = "run_workload_test"
    executions = [
        execution(run_id, 1, "SELECT id FROM parent WHERE owner_id = %s", 1, rows=4),
        *[
            execution(run_id, index + 2, "SELECT * FROM child WHERE id = %s", index, rows=1)
            for index in range(4)
        ],
        *[
            execution(run_id, index + 6, "UPDATE child SET seen = true WHERE id = %s", index, rows=1)
            for index in range(3)
        ],
    ]
    producer = ProducerIdentity(name="test", version="1")
    bundle = AnalysisEngine(producer=producer).analyze(executions, run_id=run_id)

    assert len(bundle.workload_graphs) == 1
    graph = bundle.workload_graphs[0]
    node_ids = [node.node_id for node in graph.payload.nodes]
    assert len(node_ids) == len(set(node_ids))
    inferred = [edge for edge in graph.payload.edges if edge.kind == WorkloadEdgeKind.POSSIBLE_RESULT_DRIVES]
    assert inferred
    assert all(edge.inference_method == "inferred" for edge in inferred)
    motif_keys = {episode.payload.motif_key for episode in bundle.workload_episodes}
    assert "parent-driven-repeated-lookup.v1" in motif_keys
    assert "per-item-write-loop.v1" in motif_keys
    assert all(item.artifact_kind == "workload_episode" for item in bundle.workload_episodes)
    assert all(item.artifact_kind == "finding" for item in bundle.findings)


def test_alternate_family_lens_builds_without_recapture() -> None:
    run_id = "run_lens_test"
    executions = [
        execution(run_id, 1, "SELECT * FROM course WHERE id = %s", 1, rows=1, transaction=False),
        execution(run_id, 2, "SELECT * FROM course WHERE id = %s", 2, rows=1, transaction=False),
    ]
    producer = ProducerIdentity(name="test", version="1")
    bundle = AnalysisEngine(producer=producer).analyze(executions, run_id=run_id)
    projected = build_workload(
        run_id=run_id,
        executions=bundle.executions,
        templates=bundle.templates,
        families=bundle.families,
        findings=bundle.findings,
        producer=producer,
        family_scheme_key="structural-shape.v1",
    )
    assert projected.graph.payload.family_scheme_key == "structural-shape.v1"
    family_nodes = [node for node in projected.graph.payload.nodes if node.kind == "query_family"]
    assert len(family_nodes) == 1
