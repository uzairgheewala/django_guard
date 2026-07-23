from __future__ import annotations

from planguard.analysis.normalize import normalize_sql, redact_sql
from planguard.capture import AnalysisSession


def test_normalization_preserves_structure_but_not_literals() -> None:
    first = normalize_sql("SELECT * FROM course WHERE id = 17")
    second = normalize_sql(" select *  from course where id=99; -- comment")
    other = normalize_sql("SELECT * FROM student WHERE id = 17")
    assert first.structural_shape_fingerprint == second.structural_shape_fingerprint
    assert first.structural_shape_fingerprint != other.structural_shape_fingerprint
    assert first.features.relations == ("course",)
    assert first.features.predicate_columns == ("id",)
    assert ":number" in redact_sql("SELECT * FROM t WHERE id=41 AND name='Uzair'")


def test_family_schemes_are_distinct_lenses(tmp_path) -> None:
    with AnalysisSession("families", store=tmp_path, attach_django=False, hmac_key=b"x") as session:
        for value in (1, 2, 3):
            session.record_query("SELECT * FROM course WHERE id = %s", [value], duration_ms=1)
    counts = session.analysis.summary.payload.family_count_by_scheme
    assert counts["structural-shape.v1"] == 1
    assert counts["shape-origin.v1"] == 1
    assert counts["shape-parameter-regime.v1"] == 1
    assert counts["exact-execution.v1"] == 3
