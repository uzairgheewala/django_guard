from __future__ import annotations

import os

import pytest

pytest.importorskip("django")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "workbench_api.settings")

import django  # noqa: E402

django.setup()

from django.db import connection  # noqa: E402

from planguard.capture import AnalysisSession  # noqa: E402


def test_django_execute_wrapper_captures_cursor_queries(tmp_path) -> None:
    with AnalysisSession("django-capture", store=tmp_path) as session:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
    assert session.analysis.summary.payload.query_count == 1
    execution = session.analysis.executions[0]
    assert execution.payload.context["django"] is True
    assert execution.payload.connection.alias == "default"
