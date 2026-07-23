import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  createCounterexample,
  evaluateRunNovelty,
  listArtifacts,
  listCounterexamples,
  listRuns,
  minimizeCounterexample,
  promoteCounterexample,
  type ArtifactDocumentLike,
  type IndexedArtifactSummary,
  type RunListItem,
} from "../lib/api";

function text(value: unknown, fallback = "unknown"): string {
  return typeof value === "string" ? value : fallback;
}

function object(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? value as Record<string, unknown> : {};
}

export function DetectorLabPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [instances, setInstances] = useState<IndexedArtifactSummary[]>([]);
  const [candidates, setCandidates] = useState<IndexedArtifactSummary[]>([]);
  const [runId, setRunId] = useState("");
  const [instanceId, setInstanceId] = useState("");
  const [label, setLabel] = useState("false_positive");
  const [minimumParents, setMinimumParents] = useState(2);
  const [novelty, setNovelty] = useState<ArtifactDocumentLike | null>(null);
  const [selectedCandidate, setSelectedCandidate] = useState<string | null>(null);
  const [minimizationId, setMinimizationId] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refreshCandidates = () => listCounterexamples({ limit: 50 }).then((response) => setCandidates(response.items));

  useEffect(() => {
    listRuns({ limit: 100 }).then((response) => {
      setRuns(response.items);
      if (response.items[0]) setRunId(response.items[0].artifact_id);
    }).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
    listArtifacts({ kind: "scenario_instance", limit: 100 }).then((response) => {
      setInstances(response.items);
      if (response.items[0]) setInstanceId(response.items[0].artifact_id);
    }).catch(() => undefined);
    refreshCandidates().catch(() => undefined);
  }, []);

  const selectedRun = useMemo(() => runs.find((item) => item.artifact_id === runId), [runs, runId]);

  const analyzeNovelty = async () => {
    if (!runId) return;
    setBusy("novelty"); setError(null);
    try { setNovelty(await evaluateRunNovelty(runId)); }
    catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(null); }
  };

  const capture = async () => {
    if (!runId || !instanceId) return;
    setBusy("capture"); setError(null);
    try {
      const candidate = await createCounterexample({
        source_artifact_id: runId,
        scenario_instance_id: instanceId,
        novelty_signature_id: novelty?.artifact_id,
        label,
        preserved_predicate: {
          predicate_key: "minimum-parent-count.v1",
          kind: "custom",
          subject_ref: null,
          parameters: { minimum_parent_count: minimumParents },
          description: `The minimized scenario must retain at least ${minimumParents} parent rows.`,
        },
        notes: ["Captured from Detector Laboratory."],
        tags: ["detector-lab"],
      });
      setSelectedCandidate(candidate.artifact_id);
      await refreshCandidates();
    } catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(null); }
  };

  const minimize = async (candidateId: string) => {
    setBusy(candidateId); setError(null);
    try {
      const response = await minimizeCounterexample(candidateId);
      setSelectedCandidate(candidateId);
      setMinimizationId(response.minimization.artifact_id);
    } catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(null); }
  };

  const promote = async (candidateId: string) => {
    setBusy(`promote:${candidateId}`); setError(null);
    try {
      await promoteCounterexample(candidateId, { minimization_id: selectedCandidate === candidateId ? minimizationId ?? undefined : undefined, reviewer_notes: ["Promoted from Detector Laboratory."] });
      await refreshCandidates();
    } catch (reason: unknown) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(null); }
  };

  const noveltyPayload = object(novelty?.payload);

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Corpus evolution</p>
          <h1>Detector Laboratory</h1>
          <p>Classify behavioral novelty, capture labeled counterexamples, shrink scenario dimensions while preserving an explicit predicate, and promote reviewed cases into the corpus.</p>
        </div>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="detector-lab-layout">
        <div className="detector-lab-controls">
          <article className="panel">
            <h2>1. Behavioral novelty</h2>
            <label>Captured run<select value={runId} onChange={(event) => setRunId(event.target.value)}>{runs.map((run) => <option value={run.artifact_id} key={run.artifact_id}>{run.name} · {run.artifact_id}</option>)}</select></label>
            <button className="primary-button" type="button" disabled={!runId || Boolean(busy)} onClick={analyzeNovelty}>{busy === "novelty" ? "Classifying…" : "Evaluate novelty"}</button>
            {novelty && <div className="novelty-result">
              <span className={`badge novelty-${text(noveltyPayload.status)}`}>{text(noveltyPayload.status)}</span>
              <strong>{text(noveltyPayload.signature_hash)}</strong>
              <p>{Array.isArray(noveltyPayload.explanation) ? noveltyPayload.explanation.join(" ") : ""}</p>
              <Link to={`/artifacts/${novelty.artifact_id}`}>Inspect signature</Link>
            </div>}
          </article>

          <article className="panel">
            <h2>2. Capture counterexample</h2>
            <label>Scenario instance<select value={instanceId} onChange={(event) => setInstanceId(event.target.value)}>{instances.map((item) => <option value={item.artifact_id} key={item.artifact_id}>{item.artifact_id}</option>)}</select></label>
            <label>Label<select value={label} onChange={(event) => setLabel(event.target.value)}><option value="false_positive">False positive</option><option value="false_negative">False negative</option><option value="unexpected_regression">Unexpected regression</option><option value="unexpected_non_regression">Unexpected non-regression</option><option value="unclassified">Unclassified</option></select></label>
            <label>Minimum parent count<input type="number" min={0} value={minimumParents} onChange={(event) => setMinimumParents(Number(event.target.value))} /></label>
            <button className="primary-button" type="button" disabled={!runId || !instanceId || Boolean(busy)} onClick={capture}>{busy === "capture" ? "Capturing…" : "Capture candidate"}</button>
            <small>Source: {selectedRun?.name ?? "no run selected"}</small>
          </article>
        </div>

        <article className="panel">
          <h2>Counterexample corpus</h2>
          {!candidates.length && <p className="empty-state">No candidates have been captured.</p>}
          <div className="counterexample-list">
            {candidates.map((candidate) => <div className={selectedCandidate === candidate.artifact_id ? "selected" : ""} key={candidate.artifact_id}>
              <span><strong>{candidate.title ?? candidate.artifact_id}</strong><code>{candidate.artifact_id}</code><small>{candidate.status ?? "created"}</small></span>
              <div className="result-links">
                <Link to={`/artifacts/${candidate.artifact_id}`}>Inspect</Link>
                <button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => minimize(candidate.artifact_id)}>{busy === candidate.artifact_id ? "Shrinking…" : "Minimize"}</button>
                <button className="secondary-button" type="button" disabled={Boolean(busy)} onClick={() => promote(candidate.artifact_id)}>{busy === `promote:${candidate.artifact_id}` ? "Promoting…" : "Promote"}</button>
              </div>
              {selectedCandidate === candidate.artifact_id && minimizationId && <p>Minimization: <Link to={`/artifacts/${minimizationId}`}>{minimizationId}</Link></p>}
            </div>)}
          </div>
        </article>
      </div>
    </section>
  );
}
