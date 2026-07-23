#!/usr/bin/env python
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "planguard-core" / "src"))

from planguard.capture import AnalysisSession  # noqa: E402
from planguard.policy import QueryPolicy  # noqa: E402


def seed(store: Path) -> str:
    session = AnalysisSession(
        "Milestone B query-family and policy demonstration",
        store=store,
        mode="sample",
        tags=("sample", "milestone-b", "developer-mvp"),
        attach_django=False,
        hmac_key=b"planguard-milestone-b-deterministic-demo-key",
        budget_policy=QueryPolicy(
            max_queries=12,
            max_family_executions=4,
            forbid_findings=frozenset({"likely-n-plus-one.v1"}),
        ),
        code_revision="git:milestone-b",
    )
    session.run_id = "run_demo_b_001"
    with session:
        session.record_query(
            "SELECT id, student_id FROM plan_item WHERE student_id = %s ORDER BY position",
            [4819],
            duration_ms=4.8,
            row_count=7,
        )
        for course_id, duration in zip(range(101, 108), (1.2, 1.1, 1.3, 1.0, 1.2, 1.4, 1.1), strict=True):
            session.record_query(
                "SELECT id, code, title FROM course WHERE id = %s",
                [course_id],
                duration_ms=duration,
                row_count=1,
            )
        session.record_query(
            "SELECT COUNT(*) FROM enrollment WHERE student_id = %s AND status = %s",
            [4819, "active"],
            duration_ms=5.7,
            row_count=1,
        )
        session.record_query(
            "SELECT COUNT(*) FROM enrollment WHERE student_id = %s AND status = %s",
            [4819, "active"],
            duration_ms=5.5,
            row_count=1,
        )
    return session.manifest.artifact_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--store", type=Path, default=ROOT / "examples" / "store")
    args = parser.parse_args()
    print(seed(args.store))


if __name__ == "__main__":
    main()
