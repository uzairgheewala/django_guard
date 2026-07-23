"""Load a persisted run and its derived analysis artifacts from a store."""

from __future__ import annotations

from typing import TYPE_CHECKING

from planguard.analysis.engine import AnalysisBundle, AnalysisEngine
from planguard.artifacts.models import (
    AnalysisSummaryArtifact,
    BudgetEvaluationArtifact,
    DetectorReceiptArtifact,
    EvidenceArtifact,
    FamilySchemeArtifact,
    FindingArtifact,
    ObservedQueryFamilyArtifact,
    ProducerIdentity,
    QueryExecutionArtifact,
    QueryTemplateArtifact,
    RunManifestArtifact,
    WorkloadEpisodeArtifact,
    WorkloadGraphArtifact,
    WorkloadMotifArtifact,
)
from planguard.store.filesystem import FilesystemArtifactStore

if TYPE_CHECKING:
    from planguard.store.index import ArtifactIndex


def _belongs_to_run(artifact, run_id: str) -> bool:
    payload = getattr(artifact, "payload", None)
    return getattr(payload, "run_id", None) == run_id


def load_analysis_bundle(
    store: FilesystemArtifactStore,
    run_id: str,
    *,
    reanalyze_if_missing: bool = True,
    index: "ArtifactIndex | None" = None,
) -> tuple[RunManifestArtifact, AnalysisBundle]:
    manifest = store.load(run_id)
    if not isinstance(manifest, RunManifestArtifact):
        raise TypeError(f"{run_id} is not a run manifest")
    executions: list[QueryExecutionArtifact] = []
    templates: list[QueryTemplateArtifact] = []
    schemes: list[FamilySchemeArtifact] = []
    families: list[ObservedQueryFamilyArtifact] = []
    evidence: list[EvidenceArtifact] = []
    findings: list[FindingArtifact] = []
    receipts: list[DetectorReceiptArtifact] = []
    evaluations: list[BudgetEvaluationArtifact] = []
    summaries: list[AnalysisSummaryArtifact] = []
    workload_graphs: list[WorkloadGraphArtifact] = []
    workload_motifs: list[WorkloadMotifArtifact] = []
    workload_episodes: list[WorkloadEpisodeArtifact] = []

    input_ids = {reference.artifact_id for reference in manifest.provenance.input_refs}
    candidate_ids = set(input_ids)
    if index is not None:
        offset = 0
        while True:
            page = index.search(run_id=run_id, limit=500, offset=offset)
            candidate_ids.update(item["artifact_id"] for item in page.items)
            offset += len(page.items)
            if offset >= page.total or not page.items:
                break
        # A run manifest directly references global artifacts such as built-in motifs.
    else:
        for record in store.list():
            if record.artifact_id == run_id:
                continue
            try:
                artifact = store.load(record.artifact_id)
            except Exception:
                continue
            if _belongs_to_run(artifact, run_id):
                candidate_ids.add(record.artifact_id)

    for artifact_id in sorted(candidate_ids):
        if artifact_id == run_id:
            continue
        try:
            artifact = store.load(artifact_id)
        except Exception:
            continue
        if artifact.artifact_id not in input_ids and not _belongs_to_run(artifact, run_id):
            continue
        if isinstance(artifact, QueryExecutionArtifact):
            executions.append(artifact)
        elif isinstance(artifact, QueryTemplateArtifact):
            templates.append(artifact)
        elif isinstance(artifact, FamilySchemeArtifact):
            schemes.append(artifact)
        elif isinstance(artifact, ObservedQueryFamilyArtifact):
            families.append(artifact)
        elif isinstance(artifact, EvidenceArtifact):
            evidence.append(artifact)
        elif isinstance(artifact, FindingArtifact):
            findings.append(artifact)
        elif isinstance(artifact, DetectorReceiptArtifact):
            receipts.append(artifact)
        elif isinstance(artifact, BudgetEvaluationArtifact):
            evaluations.append(artifact)
        elif isinstance(artifact, AnalysisSummaryArtifact):
            summaries.append(artifact)
        elif isinstance(artifact, WorkloadGraphArtifact):
            workload_graphs.append(artifact)
        elif isinstance(artifact, WorkloadMotifArtifact):
            workload_motifs.append(artifact)
        elif isinstance(artifact, WorkloadEpisodeArtifact):
            workload_episodes.append(artifact)

    if not summaries and reanalyze_if_missing:
        producer = ProducerIdentity(name="planguard", version="0.2.0", build="reanalyze")
        return manifest, AnalysisEngine(producer=producer).analyze(executions, run_id=run_id)
    if not summaries:
        raise ValueError(f"No analysis summary exists for run {run_id}")
    summary = max(summaries, key=lambda item: item.created_at)
    return manifest, AnalysisBundle(
        run_id=run_id,
        executions=tuple(sorted(executions, key=lambda item: item.payload.sequence_number)),
        templates=tuple(templates),
        schemes=tuple(schemes),
        families=tuple(families),
        evidence=tuple(evidence),
        findings=tuple(findings),
        detector_receipts=tuple(receipts),
        budget_evaluations=tuple(evaluations),
        workload_graphs=tuple(workload_graphs),
        workload_motifs=tuple(workload_motifs),
        workload_episodes=tuple(workload_episodes),
        summary=summary,
    )
