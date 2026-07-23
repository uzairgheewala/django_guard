"""Workload graph construction and reusable motif matching.

The graph preserves observed facts separately from derived and inferred edges.
Motif occurrences are episodes, not findings: detector or policy layers may
interpret the same episode differently.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from planguard.artifacts.models import (
    ArtifactReference,
    ConstraintEvaluation,
    FindingArtifact,
    InferenceMethod,
    MotifConstraintDefinition,
    MotifEdgePattern,
    MotifNodeRole,
    ObservedQueryFamilyArtifact,
    ProducerIdentity,
    Provenance,
    QueryExecutionArtifact,
    QueryTemplateArtifact,
    WorkloadEdge,
    WorkloadEdgeKind,
    WorkloadEpisodeArtifact,
    WorkloadEpisodePayload,
    WorkloadGraphArtifact,
    WorkloadGraphPayload,
    WorkloadMotifArtifact,
    WorkloadMotifPayload,
    WorkloadNode,
    WorkloadNodeKind,
)
from planguard.canonical import canonical_json_bytes
from planguard.ids import content_derived_id


DEFAULT_GRAPH_FAMILY_SCHEME = "shape-origin.v1"


@dataclass(frozen=True, slots=True)
class WorkloadBuildResult:
    graph: WorkloadGraphArtifact
    motifs: tuple[WorkloadMotifArtifact, ...]
    episodes: tuple[WorkloadEpisodeArtifact, ...]


def _stable_id(prefix: str, value: object, *, length: int = 28) -> str:
    return content_derived_id(prefix, canonical_json_bytes(value), length=length)


def _edge(
    *,
    run_id: str,
    from_node: str,
    to_node: str,
    kind: WorkloadEdgeKind,
    method: InferenceMethod = InferenceMethod.OBSERVED,
    confidence: float = 1.0,
    evidence_refs: tuple[ArtifactReference, ...] = (),
    attributes: dict[str, object] | None = None,
) -> WorkloadEdge:
    material = {
        "run_id": run_id,
        "from": from_node,
        "to": to_node,
        "kind": kind,
        "method": method,
        "attributes": attributes or {},
    }
    return WorkloadEdge(
        edge_id=_stable_id("wedge", material),
        from_node=from_node,
        to_node=to_node,
        kind=kind,
        confidence=confidence,
        inference_method=method,
        evidence_refs=evidence_refs,
        attributes=attributes or {},
    )


def builtin_motifs(producer: ProducerIdentity) -> tuple[WorkloadMotifArtifact, ...]:
    definitions = (
        WorkloadMotifPayload(
            motif_key="exact-duplicate-cluster.v1",
            title="Exact duplicate query cluster",
            description="One exact-execution family contains more than one member.",
            node_roles=(MotifNodeRole(role_key="family", allowed_kinds=(WorkloadNodeKind.QUERY_FAMILY,)),),
            constraints=(MotifConstraintDefinition(constraint_key="repeated", kind="execution_count_gt", parameters={"value": 1}),),
            mechanism_keys=("redundant-execution",),
        ),
        WorkloadMotifPayload(
            motif_key="parameterized-repetition.v1",
            title="Parameterized structural repetition",
            description="One structural or origin-sensitive family repeats with varying bindings.",
            node_roles=(MotifNodeRole(role_key="family", allowed_kinds=(WorkloadNodeKind.QUERY_FAMILY,)),),
            constraints=(
                MotifConstraintDefinition(constraint_key="repeated", kind="execution_count_gt", parameters={"value": 1}),
                MotifConstraintDefinition(constraint_key="binding-diversity", kind="distinct_bindings_gt", parameters={"value": 1}),
            ),
            mechanism_keys=("round-trip-amplification",),
        ),
        WorkloadMotifPayload(
            motif_key="parent-driven-repeated-lookup.v1",
            title="Parent-driven repeated lookup",
            description="A parent result cardinality plausibly drives a later repeated lookup family.",
            node_roles=(
                MotifNodeRole(role_key="parent", allowed_kinds=(WorkloadNodeKind.QUERY_EXECUTION,)),
                MotifNodeRole(role_key="child_family", allowed_kinds=(WorkloadNodeKind.QUERY_FAMILY,)),
            ),
            edge_patterns=(
                MotifEdgePattern(
                    from_role="parent",
                    to_role="child_family",
                    allowed_kinds=(WorkloadEdgeKind.POSSIBLE_RESULT_DRIVES,),
                    minimum_confidence=0.5,
                ),
            ),
            constraints=(MotifConstraintDefinition(constraint_key="cardinality-alignment", kind="edge_present"),),
            mechanism_keys=("round-trip-amplification", "relation-fanout"),
        ),
        WorkloadMotifPayload(
            motif_key="per-item-write-loop.v1",
            title="Per-item write loop",
            description="A repeated write family executes several times inside one operation.",
            node_roles=(MotifNodeRole(role_key="family", allowed_kinds=(WorkloadNodeKind.QUERY_FAMILY,)),),
            constraints=(
                MotifConstraintDefinition(constraint_key="write-statement", kind="statement_in", parameters={"values": ["insert", "update", "delete"]}),
                MotifConstraintDefinition(constraint_key="repeated", kind="execution_count_gte", parameters={"value": 3}),
            ),
            mechanism_keys=("write-amplification",),
        ),
        WorkloadMotifPayload(
            motif_key="long-transaction-accumulation.v1",
            title="Long transaction query accumulation",
            description="One transaction contains many captured executions.",
            node_roles=(MotifNodeRole(role_key="transaction", allowed_kinds=(WorkloadNodeKind.TRANSACTION,)),),
            constraints=(MotifConstraintDefinition(constraint_key="query-count", kind="transaction_members_gte", parameters={"value": 5}),),
            mechanism_keys=("excessive-transaction-scope",),
        ),
    )
    output: list[WorkloadMotifArtifact] = []
    for payload in definitions:
        artifact_id = _stable_id("wmotif", payload.model_dump(mode="python"), length=32)
        output.append(
            WorkloadMotifArtifact(
                artifact_id=artifact_id,
                producer=producer,
                provenance=Provenance(derivation_key="builtin-workload-motif.v1"),
                payload=payload,
            ).seal()
        )
    return tuple(output)


def build_workload(
    *,
    run_id: str,
    executions: Iterable[QueryExecutionArtifact],
    templates: Iterable[QueryTemplateArtifact],
    families: Iterable[ObservedQueryFamilyArtifact],
    findings: Iterable[FindingArtifact],
    producer: ProducerIdentity,
    family_scheme_key: str = DEFAULT_GRAPH_FAMILY_SCHEME,
) -> WorkloadBuildResult:
    executions = tuple(sorted(executions, key=lambda item: item.payload.sequence_number))
    templates_by_id = {item.artifact_id: item for item in templates}
    all_families = tuple(families)
    selected = tuple(item for item in all_families if item.payload.family_scheme_key == family_scheme_key)
    findings = tuple(findings)

    nodes: list[WorkloadNode] = []
    edges: list[WorkloadEdge] = []
    operation_node = f"operation:{run_id}"
    nodes.append(
        WorkloadNode(
            node_id=operation_node,
            kind=WorkloadNodeKind.OPERATION,
            label=f"Operation {run_id}",
            attributes={"run_id": run_id, "query_count": len(executions)},
        )
    )

    execution_nodes: dict[str, str] = {}
    execution_by_id = {item.artifact_id: item for item in executions}
    for execution in executions:
        node_id = f"execution:{execution.artifact_id}"
        execution_nodes[execution.artifact_id] = node_id
        sql = execution.payload.sql or "<SQL omitted>"
        nodes.append(
            WorkloadNode(
                node_id=node_id,
                kind=WorkloadNodeKind.QUERY_EXECUTION,
                label=f"#{execution.payload.sequence_number} {sql[:100]}",
                artifact_ref=execution.reference(),
                attributes={
                    "sequence_number": execution.payload.sequence_number,
                    "duration_ms": execution.payload.timing.duration_ms,
                    "started_offset_ms": execution.payload.timing.started_offset_ms,
                    "row_count": execution.payload.outcome.row_count,
                    "status": execution.payload.outcome.status,
                    "connection_alias": execution.payload.connection.alias,
                    "transaction_id": execution.payload.transaction.transaction_id,
                },
            )
        )
        edges.append(_edge(run_id=run_id, from_node=operation_node, to_node=node_id, kind=WorkloadEdgeKind.EMITS))

    for left, right in zip(executions, executions[1:]):
        edges.append(
            _edge(
                run_id=run_id,
                from_node=execution_nodes[left.artifact_id],
                to_node=execution_nodes[right.artifact_id],
                kind=WorkloadEdgeKind.TEMPORALLY_PRECEDES,
                attributes={"sequence_delta": right.payload.sequence_number - left.payload.sequence_number},
            )
        )

    transaction_members: dict[str, list[QueryExecutionArtifact]] = defaultdict(list)
    for execution in executions:
        transaction_id = execution.payload.transaction.transaction_id
        if transaction_id:
            transaction_members[transaction_id].append(execution)
    for transaction_id, members in sorted(transaction_members.items()):
        node_id = f"transaction:{transaction_id}"
        nodes.append(
            WorkloadNode(
                node_id=node_id,
                kind=WorkloadNodeKind.TRANSACTION,
                label=f"Transaction {transaction_id}",
                attributes={"query_count": len(members)},
            )
        )
        edges.append(_edge(run_id=run_id, from_node=operation_node, to_node=node_id, kind=WorkloadEdgeKind.CONTAINS))
        for member in members:
            edges.append(
                _edge(
                    run_id=run_id,
                    from_node=node_id,
                    to_node=execution_nodes[member.artifact_id],
                    kind=WorkloadEdgeKind.SAME_TRANSACTION,
                )
            )

    family_nodes: dict[str, str] = {}
    for family in selected:
        node_id = f"family:{family.artifact_id}"
        family_nodes[family.artifact_id] = node_id
        template = templates_by_id.get(family.payload.query_template_ref.artifact_id)
        statement_kind = template.payload.statement_kind if template else "unknown"
        nodes.append(
            WorkloadNode(
                node_id=node_id,
                kind=WorkloadNodeKind.QUERY_FAMILY,
                label=f"{statement_kind.upper()} family ×{family.payload.aggregates.execution_count}",
                artifact_ref=family.reference(),
                attributes={
                    "family_scheme_key": family_scheme_key,
                    "execution_count": family.payload.aggregates.execution_count,
                    "distinct_parameter_bindings": family.payload.aggregates.distinct_parameter_bindings,
                    "total_duration_ms": family.payload.aggregates.total_duration_ms,
                    "first_sequence": family.payload.temporal.first_sequence,
                    "last_sequence": family.payload.temporal.last_sequence,
                    "statement_kind": statement_kind,
                    "dimension_values": family.payload.dimension_values,
                },
            )
        )
        edges.append(_edge(run_id=run_id, from_node=operation_node, to_node=node_id, kind=WorkloadEdgeKind.CONTAINS))
        if family.payload.aggregates.execution_count > 1:
            edges.append(
                _edge(
                    run_id=run_id,
                    from_node=operation_node,
                    to_node=node_id,
                    kind=WorkloadEdgeKind.REPEATED_WITHIN,
                    method=InferenceMethod.DERIVED,
                    evidence_refs=(family.reference(),),
                    attributes={"execution_count": family.payload.aggregates.execution_count},
                )
            )
        for ref in family.payload.member_execution_refs:
            member_node = execution_nodes.get(ref.artifact_id)
            if member_node:
                edges.append(
                    _edge(
                        run_id=run_id,
                        from_node=member_node,
                        to_node=node_id,
                        kind=WorkloadEdgeKind.MEMBER_OF,
                        evidence_refs=(ref, family.reference()),
                    )
                )

    # Infer parent-result relationships conservatively. We require a concrete row
    # count, an earlier execution, and cardinality agreement within max(2, 20%).
    for family in selected:
        if family.payload.aggregates.execution_count < 3:
            continue
        first_sequence = family.payload.temporal.first_sequence
        child_count = family.payload.aggregates.execution_count
        candidates: list[tuple[float, QueryExecutionArtifact]] = []
        for execution in executions:
            rows = execution.payload.outcome.row_count
            if rows is None or rows <= 0 or execution.payload.sequence_number >= first_sequence:
                continue
            tolerance = max(2.0, rows * 0.2)
            delta = abs(rows - child_count)
            if delta <= tolerance:
                candidates.append((delta, execution))
        if candidates:
            _, parent = min(candidates, key=lambda item: (item[0], -item[1].payload.sequence_number))
            confidence = max(0.5, 1.0 - (abs((parent.payload.outcome.row_count or 0) - child_count) / max(child_count, 1)))
            edges.append(
                _edge(
                    run_id=run_id,
                    from_node=execution_nodes[parent.artifact_id],
                    to_node=family_nodes[family.artifact_id],
                    kind=WorkloadEdgeKind.POSSIBLE_RESULT_DRIVES,
                    method=InferenceMethod.INFERRED,
                    confidence=confidence,
                    evidence_refs=(parent.reference(), family.reference()),
                    attributes={
                        "parent_row_count": parent.payload.outcome.row_count,
                        "child_execution_count": child_count,
                        "inference": "cardinality-and-temporal-alignment",
                    },
                )
            )

    for finding in findings:
        node_id = f"finding:{finding.artifact_id}"
        nodes.append(
            WorkloadNode(
                node_id=node_id,
                kind=WorkloadNodeKind.FINDING,
                label=finding.payload.title,
                artifact_ref=finding.reference(),
                attributes={
                    "severity": str(finding.payload.severity.level),
                    "confidence": str(finding.payload.confidence.level),
                    "mechanism_key": finding.payload.mechanism_key,
                },
            )
        )
        edges.append(_edge(run_id=run_id, from_node=operation_node, to_node=node_id, kind=WorkloadEdgeKind.CONTAINS))
        for subject in finding.payload.subject_refs:
            target = family_nodes.get(subject.artifact_id) or execution_nodes.get(subject.artifact_id)
            if target:
                edges.append(
                    _edge(
                        run_id=run_id,
                        from_node=node_id,
                        to_node=target,
                        kind=WorkloadEdgeKind.AFFECTS,
                        evidence_refs=finding.payload.evidence_refs,
                    )
                )

    graph_identity = {"run_id": run_id, "family_scheme_key": family_scheme_key, "nodes": [n.node_id for n in nodes], "edges": [e.edge_id for e in edges]}
    graph = WorkloadGraphArtifact(
        artifact_id=_stable_id("wkg", graph_identity, length=32),
        producer=producer,
        provenance=Provenance(
            input_refs=tuple(item.reference() for item in executions)
            + tuple(item.reference() for item in selected)
            + tuple(item.reference() for item in findings),
            derivation_key="workload-graph-build.v1",
        ),
        payload=WorkloadGraphPayload(
            run_id=run_id,
            family_scheme_key=family_scheme_key,
            nodes=tuple(nodes),
            edges=tuple(edges),
            capability_gaps=(),
        ),
    ).seal()

    motifs = builtin_motifs(producer)
    episodes = match_episodes(
        run_id=run_id,
        graph=graph,
        executions=executions,
        templates=templates_by_id,
        families=selected,
        motifs=motifs,
        producer=producer,
    )
    return WorkloadBuildResult(graph=graph, motifs=motifs, episodes=episodes)


def match_episodes(
    *,
    run_id: str,
    graph: WorkloadGraphArtifact,
    executions: tuple[QueryExecutionArtifact, ...],
    templates: dict[str, QueryTemplateArtifact],
    families: tuple[ObservedQueryFamilyArtifact, ...],
    motifs: tuple[WorkloadMotifArtifact, ...],
    producer: ProducerIdentity,
) -> tuple[WorkloadEpisodeArtifact, ...]:
    motif_by_key = {item.payload.motif_key: item for item in motifs}
    episodes: list[WorkloadEpisodeArtifact] = []

    def add(
        motif_key: str,
        title: str,
        bindings: dict[str, str],
        confidence: float,
        refs: tuple[ArtifactReference, ...],
        evaluations: tuple[ConstraintEvaluation, ...],
        *,
        edge_ids: tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
    ) -> None:
        identity = {"run_id": run_id, "motif": motif_key, "bindings": bindings, "edges": edge_ids}
        episodes.append(
            WorkloadEpisodeArtifact(
                artifact_id=_stable_id("wep", identity, length=32),
                producer=producer,
                provenance=Provenance(
                    input_refs=(graph.reference(), motif_by_key[motif_key].reference(), *refs),
                    derivation_key="workload-motif-match.v1",
                ),
                payload=WorkloadEpisodePayload(
                    run_id=run_id,
                    motif_key=motif_key,
                    title=title,
                    family_scheme_key=graph.payload.family_scheme_key,
                    node_bindings=bindings,
                    edge_ids=edge_ids,
                    constraint_evaluations=evaluations,
                    match_confidence=confidence,
                    subject_refs=refs,
                    metadata=metadata or {},
                ),
            ).seal()
        )

    for family in families:
        count = family.payload.aggregates.execution_count
        distinct = family.payload.aggregates.distinct_parameter_bindings
        node_id = f"family:{family.artifact_id}"
        if count > 1 and distinct <= 1:
            add(
                "exact-duplicate-cluster.v1",
                "Exact duplicate query cluster",
                {"family": node_id},
                1.0,
                (family.reference(),),
                (ConstraintEvaluation(constraint_key="repeated", status="satisfied", values={"execution_count": count}),),
            )
        if count > 1 and distinct > 1:
            add(
                "parameterized-repetition.v1",
                "Parameterized structural repetition",
                {"family": node_id},
                min(1.0, 0.55 + min(count, 20) / 50 + min(distinct, 20) / 50),
                (family.reference(),),
                (
                    ConstraintEvaluation(constraint_key="repeated", status="satisfied", values={"execution_count": count}),
                    ConstraintEvaluation(constraint_key="binding-diversity", status="satisfied", values={"distinct_parameter_bindings": distinct}),
                ),
            )
        template = templates.get(family.payload.query_template_ref.artifact_id)
        if template and template.payload.statement_kind in {"insert", "update", "delete"} and count >= 3:
            add(
                "per-item-write-loop.v1",
                "Per-item write loop",
                {"family": node_id},
                min(1.0, 0.6 + count / 25),
                (family.reference(), template.reference()),
                (
                    ConstraintEvaluation(constraint_key="write-statement", status="satisfied", values={"statement_kind": template.payload.statement_kind}),
                    ConstraintEvaluation(constraint_key="repeated", status="satisfied", values={"execution_count": count}),
                ),
            )

    for edge in graph.payload.edges:
        if edge.kind == WorkloadEdgeKind.POSSIBLE_RESULT_DRIVES:
            refs = edge.evidence_refs
            add(
                "parent-driven-repeated-lookup.v1",
                "Parent-driven repeated lookup",
                {"parent": edge.from_node, "child_family": edge.to_node},
                edge.confidence,
                refs,
                (ConstraintEvaluation(constraint_key="cardinality-alignment", status="satisfied", values=edge.attributes),),
                edge_ids=(edge.edge_id,),
                metadata={"inference_method": str(edge.inference_method)},
            )

    by_transaction: dict[str, list[QueryExecutionArtifact]] = defaultdict(list)
    for execution in executions:
        if execution.payload.transaction.transaction_id:
            by_transaction[execution.payload.transaction.transaction_id].append(execution)
    for transaction_id, members in sorted(by_transaction.items()):
        if len(members) >= 5:
            add(
                "long-transaction-accumulation.v1",
                "Long transaction query accumulation",
                {"transaction": f"transaction:{transaction_id}"},
                min(1.0, 0.5 + len(members) / 20),
                tuple(item.reference() for item in members),
                (ConstraintEvaluation(constraint_key="query-count", status="satisfied", values={"query_count": len(members)}),),
            )

    return tuple(sorted(episodes, key=lambda item: (item.payload.motif_key, item.artifact_id)))
