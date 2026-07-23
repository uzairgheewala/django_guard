"""Terminal, JSON, and standalone HTML projections of canonical analysis artifacts."""

from __future__ import annotations

import html
import json
from pathlib import Path

from planguard.analysis.engine import AnalysisBundle
from planguard.artifacts.models import BudgetEvaluationArtifact
from planguard.canonical import canonical_data, canonical_json_text


def render_terminal(
    bundle: AnalysisBundle,
    *,
    evaluation: BudgetEvaluationArtifact | None = None,
) -> str:
    lines = [
        f"PlanGuard run {bundle.run_id}",
        "=" * 72,
        f"Queries: {bundle.summary.payload.query_count}",
        f"Templates: {bundle.summary.payload.query_template_count}",
        f"Database time: {bundle.summary.payload.total_database_time_ms:.3f} ms",
        "Families:",
    ]
    for scheme, count in sorted(bundle.summary.payload.family_count_by_scheme.items()):
        lines.append(f"  {scheme}: {count}")
    lines.append(f"Plans: {len(bundle.plan_observations)}")
    for plan in bundle.plan_observations:
        mode = "actual" if plan.payload.collection.analyzed else "estimated"
        lines.append(f"  {plan.payload.features.plan_shape_fingerprint}: {plan.payload.features.node_count} nodes ({mode})")
    lines.append(f"Workload graphs: {len(bundle.workload_graphs)}")
    lines.append(f"Workload episodes: {len(bundle.workload_episodes)}")
    for episode in bundle.workload_episodes:
        lines.append(f"  [{episode.payload.match_confidence:.2f}] {episode.payload.title} ({episode.payload.motif_key})")
    lines.append(f"Findings: {len(bundle.findings)}")
    for finding in sorted(
        bundle.findings,
        key=lambda item: item.payload.severity.score,
        reverse=True,
    ):
        family = finding.payload.subject_refs[0].artifact_id if finding.payload.subject_refs else "-"
        lines.extend(
            [
                f"  [{str(finding.payload.severity.level).upper()} / "
                f"{str(finding.payload.confidence.level).upper()} confidence] "
                f"{finding.payload.title}",
                f"    detector: {finding.payload.detector_key}",
                f"    subject: {family}",
                f"    {finding.payload.explanation.summary}",
            ]
        )
    if evaluation is not None:
        lines.extend(["", f"Policy: {evaluation.payload.status}"])
        for rule in evaluation.payload.rule_evaluations:
            lines.append(f"  {rule.status}: {rule.rule_key} — {rule.message}")
    return "\n".join(lines) + "\n"


def render_json(
    bundle: AnalysisBundle,
    *,
    evaluation: BudgetEvaluationArtifact | None = None,
) -> str:
    payload = {
        "summary": canonical_data(bundle.summary),
        "families": [canonical_data(item) for item in bundle.families],
        "findings": [canonical_data(item) for item in bundle.findings],
        "detector_receipts": [canonical_data(item) for item in bundle.detector_receipts],
        "workload_graphs": [canonical_data(item) for item in bundle.workload_graphs],
        "workload_motifs": [canonical_data(item) for item in bundle.workload_motifs],
        "workload_episodes": [canonical_data(item) for item in bundle.workload_episodes],
        "plan_observations": [canonical_data(item) for item in bundle.plan_observations],
        "plan_collection_receipts": [canonical_data(item) for item in bundle.plan_collection_receipts],
        "budget_evaluation": canonical_data(evaluation) if evaluation else None,
    }
    return json.dumps(payload, sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def render_html(
    bundle: AnalysisBundle,
    *,
    evaluation: BudgetEvaluationArtifact | None = None,
) -> str:
    findings = "".join(
        f"<article><h3>{html.escape(item.payload.title)}</h3>"
        f"<p><strong>{html.escape(str(item.payload.severity.level))}</strong> severity · "
        f"{html.escape(str(item.payload.confidence.level))} confidence</p>"
        f"<p>{html.escape(item.payload.explanation.summary)}</p>"
        f"<code>{html.escape(item.payload.detector_key)}</code></article>"
        for item in bundle.findings
    ) or "<p>No findings.</p>"
    policy = ""
    if evaluation is not None:
        rules = "".join(
            f"<li><strong>{html.escape(str(rule.status))}</strong> "
            f"{html.escape(rule.rule_key)} — {html.escape(rule.message)}</li>"
            for rule in evaluation.payload.rule_evaluations
        )
        policy = f"<section><h2>Policy: {html.escape(str(evaluation.payload.status))}</h2><ul>{rules}</ul></section>"
    embedded = html.escape(render_json(bundle, evaluation=evaluation))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PlanGuard {html.escape(bundle.run_id)}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px;color:#182033}}
header,section,article{{border:1px solid #d9e0ec;border-radius:12px;padding:18px;margin:14px 0}}
.metrics{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
.metrics div{{background:#f4f7fb;padding:14px;border-radius:10px}}code,pre{{font-family:ui-monospace,monospace}}
details pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#111827;color:#e5e7eb;padding:16px;border-radius:10px}}
</style></head><body>
<header><h1>PlanGuard analysis</h1><p>{html.escape(bundle.run_id)}</p></header>
<section class="metrics"><div><strong>{bundle.summary.payload.query_count}</strong><br>queries</div>
<div><strong>{bundle.summary.payload.query_template_count}</strong><br>templates</div>
<div><strong>{bundle.summary.payload.total_database_time_ms:.3f} ms</strong><br>database time</div>
<div><strong>{len(bundle.plan_observations)}</strong><br>plans</div>
<div><strong>{len(bundle.workload_episodes)}</strong><br>episodes</div>
<div><strong>{len(bundle.findings)}</strong><br>findings</div></section>
<section><h2>Findings</h2>{findings}</section>{policy}
<details><summary>Canonical report JSON</summary><pre>{embedded}</pre></details>
</body></html>"""


def write_report(
    path: Path,
    bundle: AnalysisBundle,
    *,
    format: str,
    evaluation: BudgetEvaluationArtifact | None = None,
) -> None:
    if format == "terminal":
        text = render_terminal(bundle, evaluation=evaluation)
    elif format == "json":
        text = render_json(bundle, evaluation=evaluation)
    elif format == "html":
        text = render_html(bundle, evaluation=evaluation)
    else:
        raise ValueError(f"Unsupported report format: {format}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
