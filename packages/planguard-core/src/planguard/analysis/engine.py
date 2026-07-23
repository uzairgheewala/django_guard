"""Artifact-producing analysis orchestration."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable

from planguard.analysis.detectors import DEFAULT_DETECTORS, BaseDetector, DetectorContext
from planguard.analysis.families import builtin_scheme_artifacts, derive_templates, project_families
from planguard.analysis.workload import build_workload
from planguard.artifacts.models import (
    AnalysisSummaryArtifact,
    AnalysisSummaryPayload,
    BudgetEvaluationArtifact,
    DetectorReceiptArtifact,
    EvidenceArtifact,
    FamilySchemeArtifact,
    FindingArtifact,
    ObservedQueryFamilyArtifact,
    ProducerIdentity,
    Provenance,
    QueryExecutionArtifact,
    QueryTemplateArtifact,
    WorkloadEpisodeArtifact,
    WorkloadGraphArtifact,
    WorkloadMotifArtifact,
    PlanObservationArtifact,
    PlanCollectionReceiptArtifact,
)


@dataclass(frozen=True, slots=True)
class AnalysisBundle:
    run_id: str
    executions: tuple[QueryExecutionArtifact, ...]
    templates: tuple[QueryTemplateArtifact, ...]
    schemes: tuple[FamilySchemeArtifact, ...]
    families: tuple[ObservedQueryFamilyArtifact, ...]
    evidence: tuple[EvidenceArtifact, ...]
    findings: tuple[FindingArtifact, ...]
    detector_receipts: tuple[DetectorReceiptArtifact, ...]
    budget_evaluations: tuple[BudgetEvaluationArtifact, ...]
    workload_graphs: tuple[WorkloadGraphArtifact, ...]
    workload_motifs: tuple[WorkloadMotifArtifact, ...]
    workload_episodes: tuple[WorkloadEpisodeArtifact, ...]
    plan_observations: tuple[PlanObservationArtifact, ...]
    plan_collection_receipts: tuple[PlanCollectionReceiptArtifact, ...]
    summary: AnalysisSummaryArtifact

    def all_derived_artifacts(self):
        return (
            *self.templates,
            *self.schemes,
            *self.families,
            *self.evidence,
            *self.findings,
            *self.detector_receipts,
            *self.budget_evaluations,
            *self.workload_graphs,
            *self.workload_motifs,
            *self.workload_episodes,
            *self.plan_observations,
            *self.plan_collection_receipts,
            self.summary,
        )


class AnalysisEngine:
    def __init__(
        self,
        *,
        producer: ProducerIdentity,
        detectors: Iterable[BaseDetector] = DEFAULT_DETECTORS,
    ) -> None:
        self.producer = producer
        self.detectors = tuple(detectors)

    def analyze(self, executions: Iterable[QueryExecutionArtifact], *, run_id: str) -> AnalysisBundle:
        execution_tuple = tuple(sorted(executions, key=lambda item: item.payload.sequence_number))
        templates_by_execution, templates_by_shape = derive_templates(
            execution_tuple,
            producer=self.producer,
        )
        schemes = tuple(item.seal() for item in builtin_scheme_artifacts(self.producer))
        families = tuple(
            item.seal()
            for item in project_families(
                execution_tuple,
                templates_by_execution,
                schemes=schemes,
                producer=self.producer,
            )
        )
        templates = tuple(item.seal() for item in templates_by_shape.values())
        total_ms = sum(item.payload.timing.duration_ms for item in execution_tuple)
        detector_context = DetectorContext(
            run_id=run_id,
            families=families,
            producer=self.producer,
            total_query_count=len(execution_tuple),
            total_database_time_ms=total_ms,
        )
        evidence: list[EvidenceArtifact] = []
        findings: list[FindingArtifact] = []
        receipts: list[DetectorReceiptArtifact] = []
        for detector in self.detectors:
            output = detector.run(detector_context)
            evidence.extend(item.seal() for item in output.evidence)
            findings.extend(item.seal() for item in output.findings)
            receipts.append(output.receipt.seal())

        workload = build_workload(
            run_id=run_id,
            executions=execution_tuple,
            templates=templates,
            families=families,
            findings=findings,
            producer=self.producer,
        )

        severity_counts = Counter(str(item.payload.severity.level) for item in findings)
        family_counts = Counter(item.payload.family_scheme_key for item in families)
        summary = AnalysisSummaryArtifact(
            producer=self.producer,
            provenance=Provenance(
                input_refs=tuple(item.reference() for item in execution_tuple)
                + tuple(item.reference() for item in families)
                + tuple(item.reference() for item in findings),
                derivation_key="analysis-summary.v1",
            ),
            payload=AnalysisSummaryPayload(
                run_id=run_id,
                query_count=len(execution_tuple),
                query_template_count=len(templates),
                family_count_by_scheme=dict(sorted(family_counts.items())),
                total_database_time_ms=total_ms,
                finding_count_by_severity=dict(sorted(severity_counts.items())),
                query_execution_refs=tuple(item.reference() for item in execution_tuple),
                query_template_refs=tuple(item.reference() for item in templates),
                family_refs=tuple(item.reference() for item in families),
                evidence_refs=tuple(item.reference() for item in evidence),
                finding_refs=tuple(item.reference() for item in findings),
                detector_receipt_refs=tuple(item.reference() for item in receipts),
            ),
        ).seal()
        return AnalysisBundle(
            run_id=run_id,
            executions=execution_tuple,
            templates=templates,
            schemes=schemes,
            families=families,
            evidence=tuple(evidence),
            findings=tuple(findings),
            detector_receipts=tuple(receipts),
            budget_evaluations=(),
            workload_graphs=(workload.graph,),
            workload_motifs=workload.motifs,
            workload_episodes=workload.episodes,
            plan_observations=(),
            plan_collection_receipts=(),
            summary=summary,
        )
