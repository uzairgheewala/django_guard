import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { ArtifactSummary } from "../generated/artifact-types";
import { importArtifact, listArtifacts } from "../lib/api";

export function ArtifactsPage() {
  const [items, setItems] = useState<ArtifactSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [importing, setImporting] = useState(false);

  const refresh = () => {
    listArtifacts()
      .then((response) => setItems(response.items))
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  };

  useEffect(refresh, []);

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    try {
      await importArtifact(draft);
      setDraft("");
      refresh();
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason));
    } finally {
      setImporting(false);
    }
  };

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Registry</p>
          <h1>Artifacts</h1>
          <p>Immutable canonical documents currently indexed by the local workbench.</p>
        </div>
      </header>

      {error && <div className="error-banner" role="alert">{error}</div>}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Artifact</th>
              <th>Kind</th>
              <th>Schema</th>
              <th>Created</th>
              <th>Integrity hash</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.artifact_id}>
                <td><Link to={`/artifacts/${item.artifact_id}`}>{item.artifact_id}</Link></td>
                <td><span className="badge">{item.artifact_kind}</span></td>
                <td>{item.schema_version}</td>
                <td>{new Date(item.created_at).toLocaleString()}</td>
                <td><code>{item.content_hash?.slice(0, 22)}…</code></td>
              </tr>
            ))}
          </tbody>
        </table>
        {items.length === 0 && <p className="empty-state">No valid artifacts are indexed.</p>}
      </div>

      <article className="panel import-panel">
        <h2>Import one sealed artifact</h2>
        <p>Paste a complete canonical artifact document. Validation and integrity verification run before persistence.</p>
        <textarea
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="{ &quot;schema_version&quot;: &quot;...&quot;, ... }"
          rows={8}
        />
        <button type="button" className="primary-button" onClick={handleImport} disabled={!draft || importing}>
          {importing ? "Importing…" : "Validate and import"}
        </button>
      </article>
    </section>
  );
}
