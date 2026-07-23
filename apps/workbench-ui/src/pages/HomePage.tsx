import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getRegistryStats, listRuns, type RegistryStats, type RunListItem } from "../lib/api";

export function HomePage() {
  const [stats, setStats] = useState<RegistryStats | null>(null);
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getRegistryStats(), listRuns({ limit: 4 })])
      .then(([registry, recent]) => { setStats(registry); setRuns(recent.items); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Milestone E</p>
          <h1>Plan intelligence and optimization evidence</h1>
          <p>Move from captured workload families into contextual PostgreSQL plans, then compare baseline and candidate runs only after their scenario and environment dimensions have been qualified.</p>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="metric-grid four-up">
        <article className="metric-card"><span>Artifacts</span><strong>{stats?.total_artifacts ?? "—"}</strong><small>Canonical source documents</small></article>
        <article className="metric-card"><span>Runs</span><strong>{stats?.runs ?? "—"}</strong><small>Captured operations</small></article>
        <article className="metric-card"><span>Findings</span><strong>{stats?.findings ?? "—"}</strong><small>Evidence-backed interpretations</small></article>
        <article className="metric-card"><span>Plans</span><strong>{stats?.plans ?? "—"}</strong><small>Canonical PostgreSQL observations</small></article>
      </div>

      <div className="callout">
        <div><h2>Validate an optimization</h2><p>Select baseline and candidate runs, inspect controlled and confounding dimensions, and compare workload families, plans, findings, and resource evidence.</p></div>
        <Link className="primary-button" to="/comparisons">Open Comparison Workbench</Link>
      </div>

      <div className="section-grid">
        <article className="panel"><h2>Plans are contextual</h2><p>Scan and join operators are interpreted with relation, parameter-regime, actual-row, buffer, and collection-policy evidence.</p></article>
        <article className="panel"><h2>Comparability first</h2><p>Scenario, seed, environment, capture policy, and intended implementation changes are qualified before timing deltas are treated as meaningful.</p></article>
        <article className="panel"><h2>Semantic plan diffs</h2><p>Plan comparisons emphasize operator, relation, index, cardinality, loop, buffer, and spill transitions rather than unstable raw JSON.</p></article>
        <article className="panel"><h2>Relative guards</h2><p>Versioned policies can require reductions or cap regressions against a qualified baseline.</p></article>
      </div>

      <article className="panel recent-runs-panel">
        <div className="section-heading"><div><h2>Recent runs</h2><p>Open any indexed operation.</p></div><Link to="/runs">View all</Link></div>
        <div className="recent-run-list">
          {runs.map((run) => <Link key={run.artifact_id} className="recent-run-row" to={`/runs/${run.artifact_id}`}><span><strong>{run.name}</strong><code>{run.artifact_id}</code></span><span>{run.inventory.by_kind.query_execution ?? 0} queries</span><span>{run.inventory.by_kind.workload_episode ?? 0} episodes</span></Link>)}
          {runs.length === 0 && <p className="muted">No indexed runs yet.</p>}
        </div>
      </article>
    </section>
  );
}
