"""Seed the Milestone C workload graph and registry demonstration run."""

from __future__ import annotations

from pathlib import Path

from planguard.artifacts.models import CapturePolicyPayload, OriginCaptureMode, ParameterCaptureMode, RawSqlMode
from planguard.capture.session import AnalysisSession
from planguard.store.index import ArtifactIndex
from planguard.store.filesystem import FilesystemArtifactStore

ROOT = Path(__file__).resolve().parents[1]
STORE_ROOT = ROOT / "examples" / "store"


def main() -> None:
    store = FilesystemArtifactStore(STORE_ROOT)
    policy = CapturePolicyPayload(
        policy_key="milestone-c-demo.v1",
        raw_sql_mode=RawSqlMode.PRESERVE,
        parameter_capture_mode=ParameterCaptureMode.SHAPE_AND_HASH,
        origin_capture_mode=OriginCaptureMode.FIRST_APPLICATION_FRAME,
        application_roots=(str(ROOT),),
        hmac_key_id="milestone-c-demo-key",
    )
    with AnalysisSession(
        "Student plan workload graph",
        store=store,
        mode="laboratory",
        tags=("milestone-c", "workload-graph", "academic-demo"),
        capture_policy=policy,
        hmac_key=b"planguard-milestone-c-demo-key-32b",
        attach_django=False,
        run_id="run_demo_c_001",
        code_revision="milestone-c-demo",
    ) as session:
        session.record_query(
            "SELECT id, course_id FROM plan_item WHERE student_id = %s ORDER BY position",
            [18291], duration_ms=6.4, row_count=8, transaction_depth=1, autocommit=False,
            context={"operation_segment": "load-plan-items"},
        )
        for course_id in range(7001, 7009):
            session.record_query(
                "SELECT id, subject, number, title FROM course WHERE id = %s",
                [course_id], duration_ms=1.1 + (course_id % 3) * 0.2, row_count=1,
                transaction_depth=1, autocommit=False,
                context={"operation_segment": "serialize-plan-item", "relation": "course"},
            )
        for item_id in range(9101, 9105):
            session.record_query(
                "UPDATE plan_item SET last_viewed_at = NOW() WHERE id = %s",
                [item_id], duration_ms=0.8, row_count=1,
                transaction_depth=1, autocommit=False,
                context={"operation_segment": "mark-visible"},
            )
        session.record_query(
            "SELECT COUNT(*) FROM advising_note WHERE student_id = %s",
            [18291], duration_ms=2.2, row_count=1,
            transaction_depth=1, autocommit=False,
            context={"operation_segment": "load-note-count"},
        )

    ArtifactIndex(STORE_ROOT / "registry.sqlite3").rebuild(store)
    print(session.manifest.artifact_id)


if __name__ == "__main__":
    main()
