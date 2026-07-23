import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getComparison, type ArtifactDocumentLike } from "../lib/api";

interface Delta { metric_key: string; baseline?: number | null; candidate?: number | null; absolute_delta?: number | null; relative_delta?: number | null; unit?: string | null; direction: string; validity: string; }
interface Dimension { dimension_key: string; state: string; explanation: string; }
interface FamilyChange { change_kind: string; structural_shape_fingerprint?: string; explanation: string; }
interface PlanChange { change_kind: string; transitions: string[]; explanation: string; severity: string; baseline_plan_ref?: {artifact_id: string} | null; candidate_plan_ref?: {artifact_id: string} | null; }

export function ComparisonDetailPage() {
  const { comparisonId = "" } = useParams();
  const [report, setReport] = useState<ArtifactDocumentLike | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => { getComparison(comparisonId).then(setReport).catch((reason) => setError(reason instanceof Error ? reason.message : String(reason))); }, [comparisonId]);
  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!report) return <p className="empty-state">Loading comparison…</p>;
  const payload = report.payload;
  const base = payload.baseline_run_ref as {artifact_id: string}; const candidate = payload.candidate_run_ref as {artifact_id: string};
  const metrics = payload.metric_deltas as Delta[]; const dimensions = payload.dimensions as Dimension[]; const families = payload.family_changes as FamilyChange[]; const plans = payload.plan_changes as PlanChange[];
  return <section>
    <header className="page-header artifact-heading"><div><p className="eyebrow">{String(payload.status)}</p><h1>Optimization comparison</h1><p><Link to={`/runs/${base.artifact_id}`}>{base.artifact_id}</Link> → <Link to={`/runs/${candidate.artifact_id}`}>{candidate.artifact_id}</Link></p></div><Link className="integrity" to={`/artifacts/${report.artifact_id}`}>Open report artifact</Link></header>
    <div className="comparison-status-callout"><strong>Comparability</strong><span>{String(payload.status)}</span><p>{(payload.narrative as string[]).join(" ")}</p></div>
    <div className="metric-grid">{metrics.map((delta) => <article className={`metric-card delta-${delta.direction}`} key={delta.metric_key}><span>{delta.metric_key}</span><strong>{delta.baseline ?? "—"} → {delta.candidate ?? "—"}</strong><small>{delta.absolute_delta == null ? "unavailable" : `${delta.absolute_delta > 0 ? "+" : ""}${delta.absolute_delta} ${delta.unit ?? ""}`} · {delta.validity}</small></article>)}</div>
    <div className="comparison-detail-grid">
      <article className="panel"><h2>Comparability dimensions</h2><div className="dimension-list">{dimensions.map((item) => <div key={item.dimension_key}><span className={`badge comparison-${item.state}`}>{item.state}</span><strong>{item.dimension_key}</strong><p>{item.explanation}</p></div>)}</div></article>
      <article className="panel"><h2>Query-family changes</h2><div className="dimension-list">{families.filter((item) => item.change_kind !== "unchanged").map((item, index) => <div key={`${item.structural_shape_fingerprint}-${index}`}><span className="badge">{item.change_kind}</span><code>{item.structural_shape_fingerprint ?? "unmatched"}</code><p>{item.explanation}</p></div>)}</div></article>
    </div>
    <article className="panel"><h2>Plan changes</h2><div className="plan-change-list">{plans.map((item, index) => <div key={index}><span className={`badge severity-${item.severity}`}>{item.change_kind}</span><p>{item.explanation}</p>{item.transitions.map((transition) => <code key={transition}>{transition}</code>)}<div className="chip-row">{item.baseline_plan_ref && <Link to={`/plans/${item.baseline_plan_ref.artifact_id}`}>Baseline plan</Link>}{item.candidate_plan_ref && <Link to={`/plans/${item.candidate_plan_ref.artifact_id}`}>Candidate plan</Link>}</div></div>)}</div></article>
  </section>;
}
