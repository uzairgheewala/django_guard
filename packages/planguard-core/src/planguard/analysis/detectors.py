"""Milestone B evidence-backed workload detectors."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from planguard.artifacts.models import (
    ArtifactReference,
    ConfidenceLevel,
    DetectorReceiptArtifact,
    DetectorReceiptPayload,
    DetectorStatus,
    EvidenceArtifact,
    EvidenceClaim,
    EvidencePayload,
    FindingArtifact,
    FindingExplanation,
    FindingPayload,
    ObservedQueryFamilyArtifact,
    ProducerIdentity,
    Provenance,
    RemediationGuidance,
    Score,
    SeverityLevel,
)
from planguard.time import utc_now


@dataclass(frozen=True, slots=True)
class DetectorContext:
    run_id: str
    families: tuple[ObservedQueryFamilyArtifact, ...]
    producer: ProducerIdentity
    total_query_count: int
    total_database_time_ms: float


@dataclass(frozen=True, slots=True)
class DetectorOutput:
    evidence: tuple[EvidenceArtifact, ...]
    findings: tuple[FindingArtifact, ...]
    receipt: DetectorReceiptArtifact


class Detector(Protocol):
    key: str
    version: str
    required_capabilities: tuple[str, ...]

    def analyze(self, context: DetectorContext) -> tuple[EvidenceArtifact, ...] | tuple[()]: ...


def _levels(severity: SeverityLevel, confidence: ConfidenceLevel, *, s: float, c: float) -> tuple[Score, Score]:
    return Score(level=severity, score=s), Score(level=confidence, score=c)


def _make_finding(
    *,
    context: DetectorContext,
    detector_key: str,
    mechanism: str,
    title: str,
    family: ObservedQueryFamilyArtifact,
    evidence: EvidenceArtifact,
    severity: SeverityLevel,
    confidence: ConfidenceLevel,
    severity_score: float,
    confidence_score: float,
    summary: str,
    guidance: tuple[str, ...],
    limitations: tuple[str, ...] = (),
) -> FindingArtifact:
    sev, conf = _levels(severity, confidence, s=severity_score, c=confidence_score)
    return FindingArtifact(
        producer=context.producer,
        provenance=Provenance(
            input_refs=(family.reference(), evidence.reference()),
            derivation_key=detector_key,
        ),
        payload=FindingPayload(
            run_id=context.run_id,
            detector_key=detector_key,
            mechanism_key=mechanism,
            title=title,
            severity=sev,
            confidence=conf,
            subject_refs=(family.reference(),),
            evidence_refs=(evidence.reference(),),
            claims=evidence.payload.claims,
            explanation=FindingExplanation(summary=summary),
            remediation=RemediationGuidance(
                category=mechanism,
                guidance=guidance,
            ),
            limitations=limitations,
        ),
    )


class BaseDetector:
    key = "detector.base.v1"
    version = "1"
    required_capabilities = ("query.family",)

    def run(self, context: DetectorContext) -> DetectorOutput:
        started = utc_now()
        evidence: tuple[EvidenceArtifact, ...] = ()
        findings: tuple[FindingArtifact, ...] = ()
        error: str | None = None
        status = DetectorStatus.EXECUTED
        try:
            evidence, findings = self._analyze(context)
        except Exception as exc:  # detector isolation is deliberate
            status = DetectorStatus.FAILED
            error = f"{type(exc).__name__}: {exc}"
        completed = utc_now()
        receipt = DetectorReceiptArtifact(
            producer=context.producer,
            provenance=Provenance(
                input_refs=tuple(item.reference() for item in context.families),
                derivation_key=self.key,
            ),
            payload=DetectorReceiptPayload(
                run_id=context.run_id,
                detector_key=self.key,
                detector_version=self.version,
                status=status,
                started_at=started,
                completed_at=completed,
                finding_refs=tuple(item.reference() for item in findings),
                required_capabilities=self.required_capabilities,
                error=error,
                statistics={
                    "family_count": len(context.families),
                    "evidence_count": len(evidence),
                    "finding_count": len(findings),
                },
            ),
        )
        return DetectorOutput(evidence=evidence, findings=findings, receipt=receipt)

    def _analyze(
        self, context: DetectorContext
    ) -> tuple[tuple[EvidenceArtifact, ...], tuple[FindingArtifact, ...]]:
        raise NotImplementedError


class ExactDuplicateDetector(BaseDetector):
    key = "exact-duplicate-execution.v1"

    def _analyze(self, context: DetectorContext):
        evidence_items: list[EvidenceArtifact] = []
        findings: list[FindingArtifact] = []
        for family in context.families:
            if family.payload.family_scheme_key != "exact-execution.v1":
                continue
            count = family.payload.aggregates.execution_count
            if count < 2:
                continue
            evidence = EvidenceArtifact(
                producer=context.producer,
                provenance=Provenance(input_refs=(family.reference(),), derivation_key=self.key),
                payload=EvidencePayload(
                    run_id=context.run_id,
                    claims=(
                        EvidenceClaim(
                            claim_key="identical_execution_repeated",
                            status="supported",
                            subject_refs=(family.reference(),),
                            values={"execution_count": count},
                            explanation="The same shape, parameter binding, and origin repeated.",
                        ),
                    ),
                ),
            ).seal()
            evidence_items.append(evidence)
            findings.append(
                _make_finding(
                    context=context,
                    detector_key=self.key,
                    mechanism="redundant_execution",
                    title="Exact database execution repeated",
                    family=family,
                    evidence=evidence,
                    severity=SeverityLevel.MEDIUM,
                    confidence=ConfidenceLevel.HIGH,
                    severity_score=min(0.9, 0.35 + count / 25),
                    confidence_score=0.99,
                    summary=f"One exact execution family ran {count} times from one origin.",
                    guidance=(
                        "Inspect repeated QuerySet evaluation or repeated serializer/property access.",
                        "Verify whether one evaluated result can be reused without changing semantics.",
                    ),
                )
            )
        return tuple(evidence_items), tuple(findings)


class StructuralRepetitionDetector(BaseDetector):
    key = "structural-repetition.v1"

    def _analyze(self, context: DetectorContext):
        evidence_items: list[EvidenceArtifact] = []
        findings: list[FindingArtifact] = []
        for family in context.families:
            if family.payload.family_scheme_key != "shape-origin.v1":
                continue
            aggregates = family.payload.aggregates
            if aggregates.execution_count < 4:
                continue
            evidence = EvidenceArtifact(
                producer=context.producer,
                provenance=Provenance(input_refs=(family.reference(),), derivation_key=self.key),
                payload=EvidencePayload(
                    run_id=context.run_id,
                    claims=(
                        EvidenceClaim(
                            claim_key="structural_family_repeated",
                            status="supported",
                            subject_refs=(family.reference(),),
                            values={
                                "execution_count": aggregates.execution_count,
                                "distinct_parameter_bindings": aggregates.distinct_parameter_bindings,
                                "total_duration_ms": aggregates.total_duration_ms,
                            },
                        ),
                    ),
                ),
            ).seal()
            evidence_items.append(evidence)
            findings.append(
                _make_finding(
                    context=context,
                    detector_key=self.key,
                    mechanism="round_trip_amplification",
                    title="Structurally identical query repeated",
                    family=family,
                    evidence=evidence,
                    severity=SeverityLevel.MEDIUM,
                    confidence=ConfidenceLevel.HIGH,
                    severity_score=min(0.9, aggregates.execution_count / 40),
                    confidence_score=0.97,
                    summary=(
                        f"One shape-and-origin family ran {aggregates.execution_count} times "
                        f"with {aggregates.distinct_parameter_bindings} parameter bindings."
                    ),
                    guidance=(
                        "Inspect whether the operation can batch or prefetch the repeated access.",
                        "Measure replacement result-set size before treating fewer queries as sufficient.",
                    ),
                    limitations=("Repetition alone does not prove the queries are avoidable.",),
                )
            )
        return tuple(evidence_items), tuple(findings)


class LikelyNPlusOneDetector(BaseDetector):
    key = "likely-n-plus-one.v1"

    def _analyze(self, context: DetectorContext):
        evidence_items: list[EvidenceArtifact] = []
        findings: list[FindingArtifact] = []
        for family in context.families:
            if family.payload.family_scheme_key != "shape-origin.v1":
                continue
            aggregates = family.payload.aggregates
            count = aggregates.execution_count
            distinct = aggregates.distinct_parameter_bindings
            diversity = distinct / count if count else 0.0
            if count < 5 or diversity < 0.75:
                continue
            confidence_score = min(0.92, 0.65 + diversity * 0.25)
            evidence = EvidenceArtifact(
                producer=context.producer,
                provenance=Provenance(input_refs=(family.reference(),), derivation_key=self.key),
                payload=EvidencePayload(
                    run_id=context.run_id,
                    claims=(
                        EvidenceClaim(
                            claim_key="parameter_varying_lookup_cluster",
                            status="supported",
                            subject_refs=(family.reference(),),
                            values={
                                "execution_count": count,
                                "distinct_parameter_bindings": distinct,
                                "parameter_diversity_ratio": diversity,
                            },
                            explanation=(
                                "A single application origin emitted many structurally identical "
                                "queries whose parameter bindings varied."
                            ),
                        ),
                    ),
                ),
            ).seal()
            evidence_items.append(evidence)
            findings.append(
                _make_finding(
                    context=context,
                    detector_key=self.key,
                    mechanism="round_trip_amplification",
                    title="Likely relation-driven N+1 workload",
                    family=family,
                    evidence=evidence,
                    severity=SeverityLevel.HIGH if count >= 20 else SeverityLevel.MEDIUM,
                    confidence=ConfidenceLevel.HIGH if confidence_score >= 0.85 else ConfidenceLevel.MEDIUM,
                    severity_score=min(0.95, 0.4 + count / 50),
                    confidence_score=confidence_score,
                    summary=(
                        f"{count} same-origin executions used {distinct} distinct parameter bindings, "
                        "which is consistent with per-parent relation loading."
                    ),
                    guidance=(
                        "Inspect lazy relation access inside iteration or serialization.",
                        "Consider select_related, prefetch_related, or an explicit batch query where semantics permit.",
                        "Verify that eager loading does not create excessive row amplification.",
                    ),
                    limitations=(
                        "Milestone B does not yet prove a parent-result dependency; workload graphs add that evidence later.",
                    ),
                )
            )
        return tuple(evidence_items), tuple(findings)


class SlowFamilyConcentrationDetector(BaseDetector):
    key = "slow-family-concentration.v1"

    def _analyze(self, context: DetectorContext):
        evidence_items: list[EvidenceArtifact] = []
        findings: list[FindingArtifact] = []
        if context.total_database_time_ms <= 0:
            return (), ()
        for family in context.families:
            if family.payload.family_scheme_key != "structural-shape.v1":
                continue
            share = family.payload.aggregates.total_duration_ms / context.total_database_time_ms
            if share < 0.50:
                continue
            evidence = EvidenceArtifact(
                producer=context.producer,
                provenance=Provenance(input_refs=(family.reference(),), derivation_key=self.key),
                payload=EvidencePayload(
                    run_id=context.run_id,
                    claims=(
                        EvidenceClaim(
                            claim_key="family_dominates_database_time",
                            status="supported",
                            subject_refs=(family.reference(),),
                            values={
                                "database_time_share": share,
                                "family_total_ms": family.payload.aggregates.total_duration_ms,
                                "run_total_ms": context.total_database_time_ms,
                            },
                        ),
                    ),
                ),
            ).seal()
            evidence_items.append(evidence)
            findings.append(
                _make_finding(
                    context=context,
                    detector_key=self.key,
                    mechanism="database_time_concentration",
                    title="One query family dominates database time",
                    family=family,
                    evidence=evidence,
                    severity=SeverityLevel.HIGH if share >= 0.8 else SeverityLevel.MEDIUM,
                    confidence=ConfidenceLevel.HIGH,
                    severity_score=share,
                    confidence_score=0.99,
                    summary=f"This structural family consumed {share:.1%} of captured database time.",
                    guidance=(
                        "Prioritize this family for plan collection and representative-parameter analysis.",
                        "Separate per-execution latency from repetition before selecting a remediation.",
                    ),
                )
            )
        return tuple(evidence_items), tuple(findings)


DEFAULT_DETECTORS: tuple[BaseDetector, ...] = (
    ExactDuplicateDetector(),
    StructuralRepetitionDetector(),
    LikelyNPlusOneDetector(),
    SlowFamilyConcentrationDetector(),
)
