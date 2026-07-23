import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns, type RunListItem } from "../lib/api";

export function RunsPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [hasFinding, setHasFinding] = useState("");

  useEffect(() => {
    const handle = window.setTimeout(() => {
      listRuns({ q: query, status, hasFinding, limit: 100 })
        .then((response) => { setRuns(response.items); setTotal(response.total); })
        .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
    }, 150);
    return () => window.clearTimeout(handle);
  }, [hasFinding, query, status]);

  return (
    <section>
      <header className="page-header"><div><p className="eyebrow">Captured operations</p><h1>Runs</h1><p>Search the rebuildable registry, then move from operation evidence to families, graphs, motifs, episodes, findings, and policies.</p></div></header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="filter-bar">
        <label>Search<input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Name, ID, tag, or artifact content" /></label>
        <label>Status<select value={status} onChange={(event) => setStatus(event.target.value)}><option value="">Any status</option><option value="completed">Completed</option><option value="failed">Failed</option><option value="incomplete">Incomplete</option></select></label>
        <label>Finding<select value={hasFinding} onChange={(event) => setHasFinding(event.target.value)}><option value="">Any</option><option value="true">Has a finding</option><option value="round-trip-amplification">Round-trip amplification</option><option value="redundant-execution">Redundant execution</option></select></label>
        <span className="filter-count">{runs.length} of {total}</span>
      </div>
      <div className="table-wrap">
        <table><thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Queries</th><th>Episodes</th><th>Findings</th><th>Completed</th></tr></thead><tbody>
          {runs.map((run) => <tr key={run.artifact_id}><td><Link to={`/runs/${run.artifact_id}`}>{run.name}</Link><br /><code>{run.artifact_id}</code></td><td><span className={`badge status-${run.status}`}>{run.status}</span></td><td>{run.mode}</td><td>{run.inventory.by_kind.query_execution ?? 0}</td><td>{run.inventory.by_kind.workload_episode ?? 0}</td><td>{run.inventory.by_kind.finding ?? 0}</td><td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}</td></tr>)}
        </tbody></table>
        {runs.length === 0 && <p className="empty-state">No runs match the active registry filters.</p>}
      </div>
    </section>
  );
}
