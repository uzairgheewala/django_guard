from __future__ import annotations

from planguard.artifacts.models import (
    ProducerIdentity,
    Provenance,
    RunManifestArtifact,
    RunManifestPayload,
    RunStatus,
    RunSummary,
    ArtifactInventory,
    QueryTemplateArtifact,
    QueryTemplatePayload,
    QueryFeatures,
    ParseQuality,
)
from planguard.store.filesystem import FilesystemArtifactStore
from planguard.store.index import ArtifactIndex


def test_index_rebuild_search_and_bidirectional_provenance(tmp_path) -> None:
    store = FilesystemArtifactStore(tmp_path / "store")
    producer = ProducerIdentity(name="test", version="1")
    run = RunManifestArtifact(
        artifact_id="run_index_test",
        producer=producer,
        payload=RunManifestPayload(
            run=RunSummary(name="Indexed academic dashboard", mode="test", status=RunStatus.COMPLETED, tags=("academic", "fast")),
            artifact_inventory=ArtifactInventory(by_kind={}, total_count=0),
        ),
    ).seal()
    store.save(run)
    template = QueryTemplateArtifact(
        producer=producer,
        provenance=Provenance(input_refs=(run.reference(),), derivation_key="test"),
        payload=QueryTemplatePayload(
            dialect="postgresql",
            canonical_sql="select * from course where id = :parameter",
            lexical_fingerprint="qlx_test",
            structural_shape_fingerprint="qsh_test",
            statement_kind="select",
            features=QueryFeatures(statement_kind="select", relations=("course",)),
            parse_quality=ParseQuality.PARTIAL,
        ),
    ).seal()
    store.save(template)

    index = ArtifactIndex(tmp_path / "registry.sqlite3")
    assert index.rebuild(store) == 2
    page = index.search(query="academic dashboard", artifact_kind="run_manifest")
    assert page.total == 1
    assert page.items[0]["artifact_id"] == run.artifact_id
    tagged = index.search(tag="academic")
    assert tagged.total == 1
    related = index.related(template.artifact_id)
    assert [item["artifact_id"] for item in related["inputs"]] == [run.artifact_id]
    reverse = index.related(run.artifact_id)
    assert [item["artifact_id"] for item in reverse["derived"]] == [template.artifact_id]
    assert index.stats()["total_artifacts"] == 2
