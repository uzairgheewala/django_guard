import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JsonTree } from "../components/JsonTree";
import { getRun, type ArtifactDocumentLike, type RunDetailResponse } from "../lib/api";

type Tab = "timeline" | "families" | "findings" | "detectors" | "policies" | "manifest";

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
  const [error, setError] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("timeline");
  const [scheme, setScheme] = useState("shape-origin.v1");

  useEffect(() => {
    getRun(runId).then(setData).catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [runId]);

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
        <Link className="integrity" to={`/artifacts/${runId}`}>Open manifest artifact</Link>
      </header>

      <div className="metric-grid four-up">
        <article className="metric-card"><span>Queries</span><strong>{numberValue(summary.query_count)}</strong><small>Immutable executions</small></article>
        <article className="metric-card"><span>Templates</span><strong>{numberValue(summary.query_template_count)}</strong><small>Conservative structures</small></article>
        <article className="metric-card"><span>Database time</span><strong>{numberValue(summary.total_database_time_ms).toFixed(2)} ms</strong><small>Captured aggregate</small></article>
        <article className="metric-card"><span>Findings</span><strong>{data.findings.length}</strong><small>Evidence-backed claims</small></article>
      </div>

      <div className="tabs" role="tablist" aria-label="Run analysis views">
        {(["timeline", "families", "findings", "detectors", "policies", "manifest"] as Tab[]).map((candidate) => (
          <button key={candidate} type="button" className={tab === candidate ? "active" : ""} onClick={() => setTab(candidate)} role="tab" aria-selected={tab === candidate}>
            {candidate[0].toUpperCase() + candidate.slice(1)}
          </button>
        ))}
      </div>

      {tab === "timeline" && (
        <article className="panel artifact-panel">
          <h2>Query execution timeline</h2>
          <div className="timeline-list">
            {sortedExecutions.map((execution) => {
              const timing = execution.payload.timing as Record<string, unknown>;
              const origin = execution.payload.origin as Record<string, unknown>;
              const frame = (origin.application_frame ?? {}) as Record<string, unknown>;
              return (
                <div className="timeline-row" key={execution.artifact_id}>
                  <span className="sequence">#{numberValue(execution.payload.sequence_number)}</span>
                  <div>
                    <code>{stringValue(execution.payload.sql)}</code>
                    <small>{stringValue(frame.module)}:{stringValue(frame.line)} · {stringValue((execution.payload.connection as Record<string, unknown>).alias)}</small>
                  </div>
                  <strong>{numberValue(timing.duration_ms).toFixed(2)} ms</strong>
                  <Link to={`/artifacts/${execution.artifact_id}`}>Artifact</Link>
                </div>
              );
            })}
          </div>
        </article>
      )}

      {tab === "families" && (
        <article className="panel artifact-panel">
          <div className="section-heading">
            <div><h2>Query families</h2><p>Change the equivalence relation without changing captured observations.</p></div>
            <label>Family lens<select value={scheme} onChange={(event) => setScheme(event.target.value)}>
              <option value="exact-execution.v1">Exact execution</option>
              <option value="structural-shape.v1">Structural shape</option>
              <option value="shape-origin.v1">Shape + origin</option>
              <option value="shape-parameter-regime.v1">Shape + parameter regime</option>
            </select></label>
          </div>
          <div className="family-list">
            {families.map((family) => {
              const aggregate = family.payload.aggregates as Record<string, unknown>;
              return <div className="family-row" key={family.artifact_id}>
                <div><Link to={`/artifacts/${family.artifact_id}`}>{family.artifact_id}</Link><small>{Object.entries(family.payload.dimension_values as Record<string, unknown>).map(([key, value]) => `${key}=${value}`).join(" · ")}</small></div>
                <span><strong>{numberValue(aggregate.execution_count)}</strong> executions</span>
                <span><strong>{numberValue(aggregate.distinct_parameter_bindings)}</strong> bindings</span>
                <span><strong>{numberValue(aggregate.total_duration_ms).toFixed(2)}</strong> ms</span>
              </div>;
            })}
          </div>
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
