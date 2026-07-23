import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import type { MaterializedArtifact } from "../generated/artifact-types";
import { JsonTree } from "../components/JsonTree";
import { getArtifact, getRelatedArtifacts, verifyArtifact, type RelatedArtifactsResponse } from "../lib/api";

type Tab = "overview" | "provenance" | "extensions" | "raw";

export function ArtifactDetailPage() {
  const { artifactId = "" } = useParams();
  const [artifact, setArtifact] = useState<MaterializedArtifact | null>(null);
  const [verified, setVerified] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [related, setRelated] = useState<RelatedArtifactsResponse>({ inputs: [], derived: [] });
  const [tab, setTab] = useState<Tab>("overview");

  useEffect(() => {
    setError(null);
    Promise.all([getArtifact(artifactId), verifyArtifact(artifactId), getRelatedArtifacts(artifactId)])
      .then(([document, integrity, relationships]) => {
        setArtifact(document);
        setVerified(integrity.verified);
        setRelated(relationships);
      })
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, [artifactId]);

  const raw = useMemo(() => (artifact ? JSON.stringify(artifact, null, 2) : ""), [artifact]);

  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!artifact) return <p className="empty-state">Loading artifact…</p>;

  const provenance = artifact.provenance;
  const extensions = artifact.extensions;
  const inputRefs = provenance.input_refs ?? [];

  return (
    <section>
      <header className="page-header artifact-heading">
        <div>
          <p className="eyebrow">{artifact.artifact_kind}</p>
          <h1>{artifact.artifact_id}</h1>
          <p>{artifact.schema_version}</p>
        </div>
        <span className={`integrity ${verified ? "verified" : "failed"}`}>
          <span className={`status-dot ${verified ? "supported" : "unsupported"}`} />
          {verified ? "Integrity verified" : "Integrity failed"}
        </span>
      </header>

      <div className="metadata-strip">
        <div><span>Producer</span><strong>{artifact.producer.name} {artifact.producer.version}</strong></div>
        <div><span>Created</span><strong>{new Date(artifact.created_at).toLocaleString()}</strong></div>
        <div><span>Hash</span><code>{artifact.content_hash}</code></div>
      </div>

      <div className="tabs" role="tablist" aria-label="Artifact sections">
        {(["overview", "provenance", "extensions", "raw"] as Tab[]).map((candidate) => (
          <button
            key={candidate}
            type="button"
            className={tab === candidate ? "active" : ""}
            onClick={() => setTab(candidate)}
            role="tab"
            aria-selected={tab === candidate}
          >
            {candidate[0].toUpperCase() + candidate.slice(1)}
          </button>
        ))}
      </div>

      {tab === "overview" && (
        <article className="panel artifact-panel">
          <h2>Payload</h2>
          <JsonTree value={artifact.payload} />
        </article>
      )}

      {tab === "provenance" && (
        <article className="panel artifact-panel">
          <h2>Derivation</h2>
          <dl className="definition-list">
            <div><dt>Code revision</dt><dd>{provenance.code_revision ?? "Not declared"}</dd></div>
            <div><dt>Derivation key</dt><dd>{provenance.derivation_key ?? "Not declared"}</dd></div>
          </dl>
          <h3>Inputs</h3>
          {inputRefs.length === 0 ? (
            <p className="muted">No direct inputs declared.</p>
          ) : (
            <ul className="reference-list">
              {inputRefs.map((reference) => (
                <li key={reference.artifact_id}>
                  <Link to={`/artifacts/${reference.artifact_id}`}>{reference.artifact_id}</Link>
                  <span>{reference.artifact_kind}</span>
                  <code>{reference.content_hash?.slice(0, 20)}…</code>
                </li>
              ))}
            </ul>
          )}
          <h3>Derived artifacts</h3>
          {related.derived.length === 0 ? <p className="muted">No indexed artifact currently declares this document as an input.</p> : <ul className="reference-list">{related.derived.map((reference) => <li key={reference.artifact_id}><Link to={`/artifacts/${reference.artifact_id}`}>{reference.artifact_id}</Link><span>{reference.artifact_kind}</span><code>{reference.content_hash?.slice(0, 20)}…</code></li>)}</ul>}
          {provenance.configuration_ref && (
            <>
              <h3>Configuration</h3>
              <Link to={`/artifacts/${provenance.configuration_ref.artifact_id}`}>
                {provenance.configuration_ref.artifact_id}
              </Link>
            </>
          )}
        </article>
      )}

      {tab === "extensions" && (
        <article className="panel artifact-panel">
          <h2>Namespaced extensions</h2>
          {Object.keys(extensions).length === 0 ? (
            <p className="muted">This artifact has no extension payloads.</p>
          ) : (
            <JsonTree value={extensions} />
          )}
        </article>
      )}

      {tab === "raw" && (
        <article className="panel artifact-panel">
          <h2>Canonical document</h2>
          <pre className="raw-json">{raw}</pre>
        </article>
      )}
    </section>
  );
}
