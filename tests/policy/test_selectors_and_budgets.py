from __future__ import annotations

from planguard.artifacts.models import SelectorExpression, SelectorOperator
from planguard.capture import AnalysisSession
from planguard.policy import QueryPolicy
from planguard.policy.selectors import matches


def test_generic_selector_handles_nested_fields() -> None:
    subject = {"payload": {"aggregates": {"execution_count": 7}}}
    selector = SelectorExpression(
        operator=SelectorOperator.GREATER_THAN,
        field="payload.aggregates.execution_count",
        value=5,
    )
    assert matches(selector, subject)


def test_absolute_budget_passes_and_fails(tmp_path) -> None:
    with AnalysisSession(
        "budget",
        store=tmp_path,
        attach_django=False,
        budget_policy=QueryPolicy(max_queries=1),
    ) as session:
        session.record_query("SELECT 1")
        session.record_query("SELECT 2")
    evaluation = session.analysis.budget_evaluations[0]
    assert evaluation.payload.status == "failed"
    assert evaluation.payload.rule_evaluations[0].measured_value == 2
