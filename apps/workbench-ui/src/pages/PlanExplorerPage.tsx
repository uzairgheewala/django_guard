import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { JsonTree } from "../components/JsonTree";
import { PlanTree } from "../components/PlanTree";
import { getPlan, type ArtifactDocumentLike } from "../lib/api";

function value(record: Record<string, unknown>, key: string): string | number {
  const item = record[key];
  return typeof item === "number" || typeof item === "string" ? item : "—";
}

export function PlanExplorerPage() {
  const { planId = "" } = useParams();
  const [plan, setPlan] = useState<ArtifactDocumentLike | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [raw, setRaw] = useState(false);
  useEffect(() => { getPlan(planId).then(setPlan).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason))); }, [planId]);
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!plan) return <p className="empty-state">Loading plan…</p>;
  const features = plan.payload.features as Record<string, unknown>;
  const collection = plan.payload.collection as Record<string, unknown>;
  return <section>
    <header className="page-header artifact-heading"><div><p className="eyebrow">PostgreSQL · {String(collection.analyzed ? "actual" : "estimated")}</p><h1>Plan Explorer</h1><p><code>{plan.artifact_id}</code></p></div><Link className="integrity" to={`/artifacts/${plan.artifact_id}`}>Open artifact</Link></header>
    <div className="metric-grid four-up">
      <article className="metric-card"><span>Nodes</span><strong>{value(features, "node_count")}</strong><small>Canonical operators</small></article>
      <article className="metric-card"><span>Execution</span><strong>{value(features, "execution_time_ms")}</strong><small>milliseconds</small></article>
      <article className="metric-card"><span>Estimate error</span><strong>{value(features, "maximum_estimate_error_ratio")}</strong><small>maximum ratio</small></article>
      <article className="metric-card"><span>Shared reads</span><strong>{value(features, "shared_read_blocks")}</strong><small>blocks</small></article>
    </div>
    <article className="panel artifact-panel">
      <div className="section-heading"><div><h2>Canonical plan tree</h2><p>Unknown PostgreSQL node attributes remain preserved in the artifact while common resource semantics are normalized.</p></div><button className="secondary-button" type="button" onClick={() => setRaw((item) => !item)}>{raw ? "Tree view" : "Raw JSON"}</button></div>
      {raw ? <JsonTree value={plan.payload.raw_plan} /> : <PlanTree plan={plan} />}
    </article>
  </section>;
}
