import { useState } from "react";
import { Link } from "react-router-dom";
import { runSecurityAudit, sanitizeArtifact, verifyTrust, type ArtifactDocumentLike } from "../lib/api";

export function SecurityCenterPage() {
  const [artifactId, setArtifactId] = useState("");
  const [result, setResult] = useState<ArtifactDocumentLike | null>(null);
  const [sanitized, setSanitized] = useState<{ sanitized: ArtifactDocumentLike; receipt: ArtifactDocumentLike } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const perform = async (action: "audit" | "trust" | "sanitize", all = false) => {
    setBusy(true); setError(null);
    try {
      if (action === "audit") setResult(await runSecurityAudit(all ? { all: true } : { artifact_ids: [artifactId] }));
      if (action === "trust") setResult(await verifyTrust(all ? { all: true } : { artifact_ids: [artifactId] }));
      if (action === "sanitize") setSanitized(await sanitizeArtifact(artifactId));
    } catch (reason) { setError(reason instanceof Error ? reason.message : String(reason)); }
    finally { setBusy(false); }
  };
  const payload: any = result?.payload;
  return <section>
    <header className="page-header"><div><p className="eyebrow">Safety boundary</p><h1>Security, redaction, and artifact trust</h1><p>Audit captured evidence, create schema-preserving sanitized derivatives, verify content-addressed integrity, and quarantine invalid imports instead of silently accepting them.</p></div></header>
    {error && <div className="error-banner" role="alert">{error}</div>}
    <article className="panel security-controls">
      <label>Artifact ID<input value={artifactId} onChange={(event) => setArtifactId(event.target.value)} placeholder="run_… or qexec_…" /></label>
      <div className="button-row"><button type="button" disabled={busy || !artifactId} onClick={() => perform("audit")}>Audit artifact</button><button type="button" disabled={busy || !artifactId} onClick={() => perform("trust")}>Verify trust</button><button type="button" disabled={busy || !artifactId} onClick={() => perform("sanitize")}>Create sanitized derivative</button><button className="primary-button" type="button" disabled={busy} onClick={() => perform("audit", true)}>Audit full store</button></div>
    </article>
    {result && <>
      <div className="metric-grid four-up"><article className="metric-card"><span>Artifact kind</span><strong>{result.artifact_kind}</strong></article><article className="metric-card"><span>Trust</span><strong>{String(payload.trust_state)}</strong></article><article className="metric-card"><span>Findings</span><strong>{String(payload.findings?.length ?? payload.failed_refs?.length ?? 0)}</strong></article><article className="metric-card"><span>Verified</span><strong>{String(payload.integrity_verified ?? payload.verified_refs?.length ?? 0)}</strong></article></div>
      <article className="panel"><div className="section-heading"><h2>Evidence</h2><Link to={`/artifacts/${result.artifact_id}`}>Open audit artifact</Link></div><div className="compact-list">{(payload.findings ?? []).map((item: any) => <div className="plain-row static" key={item.finding_key}><span><strong>{item.category}</strong><small>{item.json_path ?? item.artifact_ref?.artifact_id}</small></span><span className={`severity ${item.risk_level}`}>{item.risk_level}</span></div>)}{!(payload.findings?.length) && <p className="muted">No scanner findings in this report. This does not prove the absence of sensitive information.</p>}</div></article>
    </>}
    {sanitized && <article className="callout"><div><h2>Sanitized derivative created</h2><p>{(sanitized.receipt.payload as any).redacted_paths?.length ?? 0} paths were changed while retaining the original artifact schema.</p></div><Link className="primary-button" to={`/artifacts/${sanitized.sanitized.artifact_id}`}>Inspect derivative</Link></article>}
  </section>;
}
