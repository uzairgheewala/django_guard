import { useEffect, useState } from "react";
import { getCapabilities, type CapabilitiesResponse } from "../lib/api";

export function CapabilitiesPage() {
  const [data, setData] = useState<CapabilitiesResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCapabilities()
      .then(setData)
      .catch((reason: unknown) => setError(reason instanceof Error ? reason.message : String(reason)));
  }, []);

  if (error) return <div className="error-banner" role="alert">{error}</div>;
  if (!data) return <p className="empty-state">Loading capabilities…</p>;

  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Contract boundary</p>
          <h1>Capabilities</h1>
          <p>Supported and deliberately deferred behavior in this repository milestone.</p>
        </div>
      </header>

      <div className="capability-list">
        {Object.entries(data.capabilities).map(([name, status]) => (
          <article key={name} className="capability-row">
            <div>
              <strong>{name}</strong>
              <small>{status === "unsupported" ? "Explicitly deferred" : "Available"}</small>
            </div>
            <span className={`capability-state ${status}`}>
              <span className={`status-dot ${status}`} />
              {status}
            </span>
          </article>
        ))}
      </div>

      <article className="panel">
        <h2>Registered artifact contracts</h2>
        <ul className="contract-list">
          {data.contracts.map((contract) => (
            <li key={`${contract.artifact_kind}/${contract.schema_version}`}>
              <span>{contract.artifact_kind}</span>
              <code>{contract.schema_version}</code>
            </li>
          ))}
        </ul>
      </article>
    </section>
  );
}
