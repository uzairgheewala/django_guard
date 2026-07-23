"""Evidence-backed findings for canonical PostgreSQL plans."""

from __future__ import annotations

from planguard.artifacts.models import (
    EvidenceArtifact, EvidenceClaim, EvidencePayload, FindingArtifact, FindingExplanation,
    PlanObservationArtifact, ProducerIdentity, Provenance, RemediationGuidance, Score,
    SeverityLevel, ConfidenceLevel,
)


def analyze_plan(plan: PlanObservationArtifact, *, producer: ProducerIdentity, high_volume_relations: frozenset[str] = frozenset(), estimate_error_threshold: float = 10.0) -> tuple[tuple[EvidenceArtifact, ...], tuple[FindingArtifact, ...]]:
    evidence: list[EvidenceArtifact] = []
    findings: list[FindingArtifact] = []

    def emit(claim_key: str, mechanism: str, title: str, values: dict, severity: SeverityLevel, confidence: float, summary: str, guidance: tuple[str, ...]):
        ev = EvidenceArtifact(
            producer=producer,
            provenance=Provenance(input_refs=(plan.reference(),), derivation_key=f"plan-evidence:{claim_key}.v1"),
            payload=EvidencePayload(run_id=plan.payload.run_id, claims=(EvidenceClaim(claim_key=claim_key, status="supported", subject_refs=(plan.reference(),), values=values, explanation=summary),)),
        ).seal()
        f = FindingArtifact(
            producer=producer,
            provenance=Provenance(input_refs=(plan.reference(), ev.reference()), derivation_key=f"plan-finding:{claim_key}.v1"),
            payload={
                "run_id": plan.payload.run_id,
                "detector_key": f"postgres-plan-{claim_key}.v1",
                "mechanism_key": mechanism,
                "title": title,
                "severity": Score(level=severity, score={SeverityLevel.INFO:.1, SeverityLevel.LOW:.25, SeverityLevel.MEDIUM:.5, SeverityLevel.HIGH:.8, SeverityLevel.CRITICAL:1.0}[severity]),
                "confidence": Score(level=ConfidenceLevel.HIGH if confidence >= .8 else ConfidenceLevel.MEDIUM, score=confidence),
                "subject_refs": (plan.reference(),),
                "evidence_refs": (ev.reference(),),
                "claims": ev.payload.claims,
                "explanation": FindingExplanation(summary=summary),
                "remediation": RemediationGuidance(category=mechanism, guidance=guidance),
                "limitations": ("Plan operators are contextual; inspect relation size, selectivity, and workload before changing indexes or SQL.",),
                "metadata": {},
            },
        ).seal()
        evidence.append(ev); findings.append(f)

    for node in plan.payload.nodes:
        if node.node_type == "Seq Scan" and node.relation in high_volume_relations:
            emit("large-sequential-scan", "nonselective-access", f"Sequential scan on high-volume relation {node.relation}", {"relation": node.relation, "rows": node.actual_rows or node.estimated_rows}, SeverityLevel.HIGH, .95, f"The plan scans configured high-volume relation {node.relation} sequentially.", ("Verify predicate selectivity and available indexes.", "Confirm that the sequential scan is not cheaper for this parameter regime."))
    error = plan.payload.features.maximum_estimate_error_ratio
    if error is not None and error >= estimate_error_threshold:
        emit("cardinality-misestimation", "cardinality-misestimation", "Severe cardinality estimate error", {"maximum_ratio": error, "threshold": estimate_error_threshold}, SeverityLevel.MEDIUM, .9, f"At least one plan node differs from its row estimate by {error:.1f}×.", ("Inspect statistics freshness and cross-column correlation.", "Reproduce across representative parameter regimes before changing planner settings."))
    if plan.payload.features.has_disk_spill:
        emit("temporary-io-spill", "temporary-io", "Sort or hash operation spilled to temporary storage", {"temporary_io_blocks": plan.payload.features.temporary_io_blocks}, SeverityLevel.HIGH, .98, "The analyzed plan reports disk-backed sort/hash behavior or temporary I/O.", ("Inspect the dominant sort/hash node and input cardinality.", "Consider query shape, indexes, or memory only after confirming workload-wide impact."))
    if plan.payload.features.nested_loop_effective_rows and plan.payload.features.nested_loop_effective_rows > 100_000:
        emit("nested-loop-multiplication", "join-multiplication", "Nested-loop multiplication is large", {"effective_rows": plan.payload.features.nested_loop_effective_rows}, SeverityLevel.MEDIUM, .82, "Nested-loop rows multiplied by loop count exceed the configured evidence threshold.", ("Inspect inner-side selectivity and index support.", "Compare against alternate parameter regimes and join plans."))
    return tuple(evidence), tuple(findings)
