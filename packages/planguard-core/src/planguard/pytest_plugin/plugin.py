"""Pytest integration for scoped capture and query budgets."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from planguard.artifacts.models import EvaluationStatus
from planguard.capture.session import AnalysisSession
from planguard.policy.engine import QueryPolicy
from planguard.reporting.render import render_terminal


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("planguard")
    group.addoption(
        "--planguard-store",
        action="store",
        default=".planguard",
        help="Artifact store used by PlanGuard captures.",
    )
    group.addoption(
        "--planguard-no-auto-capture",
        action="store_true",
        default=False,
        help="Disable automatic capture for @pytest.mark.planguard tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "planguard(max_queries=None, max_total_database_ms=None, "
        "max_family_executions=None, forbid_findings=()): capture and enforce query budgets",
    )


def _policy(kwargs: dict[str, Any]) -> QueryPolicy:
    return QueryPolicy(
        max_queries=kwargs.get("max_queries"),
        max_total_database_ms=kwargs.get("max_total_database_ms"),
        max_family_executions=kwargs.get("max_family_executions"),
        forbid_findings=frozenset(kwargs.get("forbid_findings", ())),
    )


class PlanGuardFixture:
    def __init__(self, config: pytest.Config, nodeid: str) -> None:
        self.store = Path(config.getoption("--planguard-store"))
        self.nodeid = nodeid

    def capture(self, *, name: str | None = None, policy: QueryPolicy | None = None, **kwargs: Any):
        return AnalysisSession(
            name or self.nodeid,
            store=self.store,
            mode="test",
            tags=("pytest",),
            budget_policy=policy,
            **kwargs,
        )


@pytest.fixture
def plan_guard(request: pytest.FixtureRequest) -> PlanGuardFixture:
    return PlanGuardFixture(request.config, request.node.nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item: pytest.Item):
    marker = item.get_closest_marker("planguard")
    if marker is None or item.config.getoption("--planguard-no-auto-capture"):
        yield
        return

    session = AnalysisSession(
        item.nodeid,
        store=Path(item.config.getoption("--planguard-store")),
        mode="test",
        tags=("pytest", "automatic"),
        budget_policy=_policy(dict(marker.kwargs)),
    )
    session.__enter__()
    outcome = yield
    excinfo = outcome.excinfo
    operation_error = excinfo[1] if excinfo else None
    session.__exit__(
        type(operation_error) if operation_error else None,
        operation_error,
        operation_error.__traceback__ if operation_error else None,
    )
    if excinfo is None and session.result is not None and session.result.analysis.budget_evaluations:
        evaluation = session.result.analysis.budget_evaluations[0]
        if evaluation.payload.status == EvaluationStatus.FAILED:
            report = render_terminal(session.result.analysis, evaluation=evaluation)
            outcome.force_exception(AssertionError(report))
