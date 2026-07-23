import { Link } from "react-router-dom";

export function HomePage() {
  return (
    <section>
      <header className="page-header">
        <div>
          <p className="eyebrow">Milestone B</p>
          <h1>Developer performance MVP</h1>
          <p>
            Capture a Django operation, preserve every query execution, reinterpret it through explicit family lenses,
            inspect evidence-backed findings, and enforce query budgets from pytest or the workbench.
          </p>
        </div>
      </header>

      <div className="metric-grid four-up">
        <article className="metric-card"><span>Artifact contracts</span><strong>14</strong><small>Capture through policy evaluation</small></article>
        <article className="metric-card"><span>Family lenses</span><strong>4</strong><small>Explicit equivalence schemes</small></article>
        <article className="metric-card"><span>Detectors</span><strong>4</strong><small>Each emits evidence and receipts</small></article>
        <article className="metric-card"><span>Integration</span><strong>pytest</strong><small>Budgets can fail CI</small></article>
      </div>

      <div className="callout">
        <div>
          <h2>Explore the Milestone B sample</h2>
          <p>The sample contains a parameter-varying lookup cluster, multiple family projections, detector evidence, findings, and a failed budget evaluation.</p>
        </div>
        <Link className="primary-button" to="/runs/run_demo_b_001">Open sample run</Link>
      </div>

      <div className="section-grid">
        <article className="panel"><h2>Facts remain immutable</h2><p>Captured executions are never rewritten when normalization, grouping, detector logic, or policies evolve.</p></article>
        <article className="panel"><h2>Families are lenses</h2><p>Switch among exact, structural, origin-sensitive, and parameter-regime projections without recapturing the operation.</p></article>
        <article className="panel"><h2>Claims expose evidence</h2><p>Severity, confidence, limitations, detector receipts, and evidence references remain separate and inspectable.</p></article>
        <article className="panel"><h2>Budgets are artifacts</h2><p>Policy definitions and evaluations use the same canonical contract boundary as CLI, API, pytest, and UI workflows.</p></article>
      </div>
    </section>
  );
}
