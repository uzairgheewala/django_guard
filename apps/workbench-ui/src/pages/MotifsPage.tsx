import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listArtifacts, type IndexedArtifactSummary } from "../lib/api";

export function MotifsPage() {
  const [motifs, setMotifs] = useState<IndexedArtifactSummary[]>([]);
  const [episodes, setEpisodes] = useState<IndexedArtifactSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    Promise.all([listArtifacts({ kind: "workload_motif", limit: 100 }), listArtifacts({ kind: "workload_episode", limit: 100 })])
      .then(([motifResponse, episodeResponse]) => { setMotifs(motifResponse.items); setEpisodes(episodeResponse.items); })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);
  const countByMotif = episodes.reduce<Record<string, number>>((result, item) => {
    if (item.motif_key) result[item.motif_key] = (result[item.motif_key] ?? 0) + 1;
    return result;
  }, {});
  return <section>
    <header className="page-header"><div><p className="eyebrow">Reusable graph patterns</p><h1>Workload motifs</h1><p>Motifs describe structural workload patterns. Episode artifacts record matches; findings remain separate interpretations.</p></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <div className="motif-grid">{motifs.map((motif) => <article className="panel motif-card" key={motif.artifact_id}><span className="badge">{motif.motif_key ?? "motif"}</span><h2>{motif.title ?? motif.artifact_id}</h2><p>{String(motif.metadata?.description ?? "Open the canonical motif artifact to inspect roles, edge patterns, and constraints.")}</p><div className="motif-footer"><strong>{countByMotif[motif.motif_key ?? ""] ?? 0} episodes</strong><Link to={`/artifacts/${motif.artifact_id}`}>Inspect definition</Link></div></article>)}</div>
    {motifs.length === 0 && <p className="empty-state">No motif definitions are indexed.</p>}
  </section>;
}
