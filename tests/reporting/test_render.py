from __future__ import annotations

from planguard.capture import AnalysisSession
from planguard.reporting import render_html, render_json, render_terminal


def test_reports_render_from_one_analysis_bundle(tmp_path) -> None:
    with AnalysisSession("report", store=tmp_path, attach_django=False) as session:
        session.record_query("SELECT * FROM course WHERE id = %s", [1], duration_ms=1.5)
    terminal = render_terminal(session.analysis)
    json_report = render_json(session.analysis)
    html_report = render_html(session.analysis)
    assert "Queries: 1" in terminal
    assert '"query_count": 1' in json_report
    assert "PlanGuard analysis" in html_report
