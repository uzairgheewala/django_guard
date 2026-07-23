import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JsonTree } from "../components/JsonTree";
import { WorkloadGraphExplorer } from "../components/WorkloadGraphExplorer";
import {
  getRun,
  getRunGraph,
  runExportUrl,
  type ArtifactDocumentLike,
  type RunDetailResponse,
  type RunGraphResponse,
} from "../lib/api";

type Tab = "timeline" | "workload" | "families" | "plans" | "findings" | "detectors" | "policies" | "manifest";

function numberValue(value: unknown): number {
  return typeof value === "number" ? value : 0;
}

function stringValue(value: unknown): string {
  return typeof value === "string" ? value : "unknown";
}

function findingScore(finding: ArtifactDocumentLike, key: "severity" | "confidence") {
  const score = finding.payload[key];
  if (!score || typeof score !== "object") return { level: "unknown", score: 0 };
  const record = score as Record<string, unknown>;
  return { level: stringValue(record.level), score: numberValue(record.score) };
}

export function RunDetailPage() {
  const { runId = "" } = useParams();
  const [data, setData] = useState<RunDetailResponse | null>(null);
  const [graphData, setGraphData] = useState<RunGraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [graphError, setGraphError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("workload");
  const [scheme, setScheme] = useState("shape-origin.v1");
  const [selectedArtifactId, setSelectedArtifactId] = useState<string | null>(null);

  useEffect(() => {
    getRun(runId)
      .then((response) => {
        setData(response);
        const graph = response.workload_graphs.find((item) => item.payload.family_scheme_key === "shape-origin.v1");
        if (graph) setGraphData({
          graph,
          episodes: response.workload_episodes.filter((item) => item.payload.family_scheme_key === "shape-origin.v1"),
        });
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [runId]);

  useEffect(() => {
    if (!data) return;
    const existing = data.workload_graphs.find((item) => item.payload.family_scheme_key === scheme);
    if (existing) {
      setGraphData({ graph: existing, episodes: data.workload_episodes.filter((item) => item.payload.family_scheme_key === scheme) });
      return;
    }
    setGraphError(null);
    getRunGraph(runId, scheme)
      .then(setGraphData)
      .catch((reason: unknown) => setGraphError(reason instanceof Error ? reason.message : String(reason)));
  }, [data, runId, scheme]);

  const families = useMemo(
    () => data?.families.filter((item) => item.payload.family_scheme_key === scheme) ?? [],
    [data, scheme],
  );

  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!data) return <p className="empty-state">Loading run…</p>;

  const run = data.manifest.payload.run as Record<string, unknown>;
  const summary = data.summary.payload;
  const sortedExecutions = [...data.executions].sort(
    (left, right) => numberValue(left.payload.sequence_number) - numberValue(right.payload.sequence_number),
  );

  return (
    <section>
      <header className="page-header artifact-heading">
        <div>
          <p className="eyebrow">{stringValue(run.mode)} · {stringValue(run.status)}</p>
          <h1>{stringValue(run.name)}</h1>
          <p><code>{runId}</code></p>
        </div>
        <div className="header-actions">
          <a className="secondary-button" href={runExportUrl(runId)}>Export bundle</a>
          <Link className="integrity" to={`/artifacts/${runId}`}>Open manifest artifact</Link>
        </div>
      </header>

      <div className="metric-grid four-up">
        <article className="metric-card"><span>Queries</span><strong>{numberValue(summary.query_count)}</strong><small>Immutable executions</small></article>
        <article className="metric-card"><span>Families</span><strong>{families.length}</strong><small>{scheme}</small></article>
        <article className="metric-card"><span>Episodes</span><strong>{graphData?.episodes.length ?? 0}</strong><small>Reusable motif matches</small></article>
        <article className="metric-card"><span>Plans</span><strong>{data.plan_observations.length}</strong><small>PostgreSQL semantic plans</small></article>
      </div>

      <div className="run-lens-bar">
        <label>Family lens
          <select value={scheme} onChange={(event) => setScheme(event.target.value)}>
            <option value="exact-execution.v1">Exact execution</option>
            <option value="structural-shape.v1">Structural shape</option>
            <option value="shape-origin.v1">Shape + origin</option>
            <option value="shape-parameter-regime.v1">Shape + parameter regime</option>
          </select>
        </label>
        <p>Timeline, families, graph, and episodes remain synchronized against the same immutable executions.</p>
      </div>

      <div className="tabs" role="tablist" aria-label="Run analysis views">
        {(["workload", "timeline", "families", "plans", "findings", "detectors", "policies", "manifest"] as Tab[]).map((candidate) => (
          <button key={candidate} type="button" className={tab === candidate ? "active" : ""} onClick={() => setTab(candidate)} role="tab" aria-selected={tab === candidate}>
            {candidate[0].toUpperCase() + candidate.slice(1)}
          </button>
        ))}
      </div>

      {tab === "workload" && (
        <article className="panel artifact-panel graph-panel">
          <div className="section-heading">
            <div><h2>Workload graph</h2><p>Observed facts, deterministic derivations, and uncertain causal edges remain visibly distinct.</p></div>
            {graphData && <Link to={`/artifacts/${graphData.graph.artifact_id}`}>Open graph artifact</Link>}
          </div>
          {graphError && <div className="error-banner" role="alert">{graphError}</div>}
          {graphData
            ? <WorkloadGraphExplorer graphArtifact={graphData.graph} episodes={graphData.episodes} selectedArtifactId={selectedArtifactId} onSelectArtifact={setSelectedArtifactId} />
            : <p className="empty-state">Building the selected graph projection…</p>}
        </article>
      )}

      {tab === "timeline" && (
        <article className="panel artifact-panel">
          <h2>Query execution timeline</h2>
          <div className="timeline-list">
            {sortedExecutions.map((execution) => {
              const timing = execution.payload.timing as Record<string, unknown>;
              const origin = execution.payload.origin as Record<string, unknown>;
              const frame = (origin.application_frame ?? {}) as Record<string, unknown>;
              const selected = selectedArtifactId === execution.artifact_id;
              return (
                <div className={`timeline-entry ${selected ? "selected" : ""}`} key={execution.artifact_id}>
                  <button type="button" className="timeline-row timeline-button" onClick={() => setSelectedArtifactId(execution.artifact_id)}>
                    <span className="sequence">#{numberValue(execution.payload.sequence_number)}</span>
                    <span className="timeline-query">
                      <code>{stringValue(execution.payload.sql)}</code>
                      <small>{stringValue(frame.module)}:{stringValue(frame.line)} · {stringValue((execution.payload.connection as Record<string, unknown>).alias)}</small>
                    </span>
                    <strong>{numberValue(timing.duration_ms).toFixed(2)} ms</strong>
                  </button>
                  <Link className="row-artifact-link" to={`/artifacts/${execution.artifact_id}`}>Artifact</Link>
                </div>
              );
            })}
          </div>
        </article>
      )}

      {tab === "families" && (
        <article className="panel artifact-panel">
          <div className="section-heading">
            <div><h2>Query families</h2><p>Each row is an explicit projection under {scheme}.</p></div>
          </div>
          <div className="family-list">
            {families.map((family) => {
              const aggregate = family.payload.aggregates as Record<string, unknown>;
              const selected = selectedArtifactId === family.artifact_id;
              return <div className={`family-entry ${selected ? "selected" : ""}`} key={family.artifact_id}>
                <button type="button" className="family-row family-button" onClick={() => setSelectedArtifactId(family.artifact_id)}>
                  <span className="family-identity"><code>{family.artifact_id}</code><small>{Object.entries(family.payload.dimension_values as Record<string, unknown>).map(([key, value]) => `${key}=${value}`).join(" · ")}</small></span>
                  <span><strong>{numberValue(aggregate.execution_count)}</strong> executions</span>
                  <span><strong>{numberValue(aggregate.distinct_parameter_bindings)}</strong> bindings</span>
                  <span><strong>{numberValue(aggregate.total_duration_ms).toFixed(2)}</strong> ms</span>
                </button>
                <Link className="row-artifact-link" to={`/artifacts/${family.artifact_id}`}>Artifact</Link>
              </div>;
            })}
          </div>
        </article>
      )}

      {tab === "plans" && (
        <article className="panel artifact-panel">
          <div className="section-heading"><div><h2>PostgreSQL plans</h2><p>Estimated and actual plans are labeled separately; each plan preserves collection safety context and representative-family provenance.</p></div></div>
          {data.plan_observations.length === 0 ? <p className="empty-state">No plans have been imported or safely collected for this run.</p> : <div className="plan-list">{data.plan_observations.map((plan) => {
            const features = plan.payload.features as Record<string, unknown>;
            const collection = plan.payload.collection as Record<string, unknown>;
            return <Link className="plan-list-row" to={`/plans/${plan.artifact_id}`} key={plan.artifact_id}><span><strong>{String(features.plan_shape_fingerprint)}</strong><small>{String(collection.mode)} · {collection.analyzed ? "actual" : "estimated"}</small></span><span>{String(features.node_count)} nodes</span><span>{String(features.execution_time_ms ?? "—")} ms</span></Link>;
          })}</div>}
        </article>
      )}

      {tab === "findings" && (
        <div className="finding-list">
          {data.findings.map((finding) => {
            const severity = findingScore(finding, "severity");
            const confidence = findingScore(finding, "confidence");
            const explanation = finding.payload.explanation as Record<string, unknown>;
            return <article className="panel finding-card" key={finding.artifact_id}>
              <div className="finding-heading"><span className={`badge severity-${severity.level}`}>{severity.level} severity</span><span className="badge">{confidence.level} confidence</span></div>
              <h2>{stringValue(finding.payload.title)}</h2>
              <p>{stringValue(explanation.summary)}</p>
              <div className="finding-meta"><code>{stringValue(finding.payload.detector_key)}</code><Link to={`/artifacts/${finding.artifact_id}`}>Inspect evidence</Link></div>
            </article>;
          })}
          {data.findings.length === 0 && <p className="empty-state">No findings were emitted.</p>}
        </div>
      )}

      {tab === "detectors" && <article className="panel artifact-panel"><h2>Detector receipts</h2><JsonTree value={data.detector_receipts} /></article>}
      {tab === "policies" && <article className="panel artifact-panel"><h2>Persisted policy evaluations</h2><JsonTree value={data.budget_evaluations} /></article>}
      {tab === "manifest" && <article className="panel artifact-panel"><h2>Run manifest</h2><JsonTree value={data.manifest} /></article>}
    </section>
  );
}
