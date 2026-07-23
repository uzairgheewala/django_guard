import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns, type RunListItem } from "../lib/api";

export function RunsPage() {
  const [runs, setRuns] = useState<RunListItem[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listRuns()
      .then((response) => setRuns(response.items))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Captured operations</p>
          <h1>Runs</h1>
          <p>Open one immutable run bundle and move from execution evidence to families, findings, detector receipts, and policy results.</p>
        </div>
      </header>
      {error && <div className="error-banner" role="alert">{error}</div>}
      <div className="table-wrap">
        <table>
          <thead><tr><th>Run</th><th>Status</th><th>Mode</th><th>Queries</th><th>Findings</th><th>Completed</th></tr></thead>
          <tbody>
            {runs.map((run) => (
              <tr key={run.artifact_id}>
                <td><Link to={`/runs/${run.artifact_id}`}>{run.name}</Link><br /><code>{run.artifact_id}</code></td>
                <td><span className={`badge status-${run.status}`}>{run.status}</span></td>
                <td>{run.mode}</td>
                <td>{run.inventory.by_kind.query_execution ?? 0}</td>
                <td>{run.inventory.by_kind.finding ?? 0}</td>
                <td>{run.completed_at ? new Date(run.completed_at).toLocaleString() : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {runs.length === 0 && <p className="empty-state">No captured Milestone B runs are indexed.</p>}
      </div>
    </section>
  );
}
