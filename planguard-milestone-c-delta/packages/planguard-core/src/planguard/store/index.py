"""Rebuildable SQLite metadata index over immutable PlanGuard artifacts.

JSON artifacts remain canonical. This index may be deleted and reconstructed
from a FilesystemArtifactStore without losing evidence.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from planguard.artifacts.models import (
    FindingArtifact,
    ObservedQueryFamilyArtifact,
    QueryTemplateArtifact,
    RunManifestArtifact,
    WorkloadEpisodeArtifact,
    WorkloadGraphArtifact,
    WorkloadMotifArtifact,
)
from planguard.canonical import canonical_data
from planguard.store.filesystem import FilesystemArtifactStore


@dataclass(frozen=True, slots=True)
class SearchPage:
    items: tuple[dict[str, Any], ...]
    total: int
    limit: int
    offset: int


class ArtifactIndex:
    """Queryable metadata projection that is explicitly disposable."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def _initialize(self) -> None:
        with self._connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    artifact_kind TEXT NOT NULL,
                    schema_version TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    run_id TEXT,
                    name TEXT,
                    mode TEXT,
                    status TEXT,
                    title TEXT,
                    mechanism_key TEXT,
                    severity TEXT,
                    confidence TEXT,
                    family_scheme_key TEXT,
                    query_shape_fingerprint TEXT,
                    motif_key TEXT,
                    search_text TEXT NOT NULL,
                    metadata_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS artifacts_kind_idx ON artifacts(artifact_kind);
                CREATE INDEX IF NOT EXISTS artifacts_run_idx ON artifacts(run_id);
                CREATE INDEX IF NOT EXISTS artifacts_created_idx ON artifacts(created_at DESC);
                CREATE INDEX IF NOT EXISTS artifacts_mechanism_idx ON artifacts(mechanism_key);
                CREATE INDEX IF NOT EXISTS artifacts_motif_idx ON artifacts(motif_key);

                CREATE TABLE IF NOT EXISTS artifact_tags (
                    artifact_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    PRIMARY KEY (artifact_id, tag),
                    FOREIGN KEY (artifact_id) REFERENCES artifacts(artifact_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS artifact_tags_tag_idx ON artifact_tags(tag);

                CREATE TABLE IF NOT EXISTS provenance_edges (
                    source_artifact_id TEXT NOT NULL,
                    target_artifact_id TEXT NOT NULL,
                    relationship TEXT NOT NULL,
                    PRIMARY KEY (source_artifact_id, target_artifact_id, relationship)
                );
                CREATE INDEX IF NOT EXISTS provenance_target_idx ON provenance_edges(target_artifact_id);
                """
            )

    @staticmethod
    def _metadata(artifact: Any) -> dict[str, Any]:
        payload = artifact.payload
        run_id = getattr(payload, "run_id", None)
        name = mode = status = title = mechanism_key = severity = confidence = None
        family_scheme_key = query_shape_fingerprint = motif_key = None
        tags: tuple[str, ...] = ()

        if isinstance(artifact, RunManifestArtifact):
            run_id = artifact.artifact_id
            name = payload.run.name
            mode = payload.run.mode
            status = str(payload.run.status)
            tags = payload.run.tags
        if isinstance(artifact, FindingArtifact):
            title = payload.title
            mechanism_key = payload.mechanism_key
            severity = str(payload.severity.level)
            confidence = str(payload.confidence.level)
        if isinstance(artifact, ObservedQueryFamilyArtifact):
            family_scheme_key = payload.family_scheme_key
        if isinstance(artifact, QueryTemplateArtifact):
            query_shape_fingerprint = payload.structural_shape_fingerprint
            title = payload.canonical_sql[:240]
        if isinstance(artifact, WorkloadGraphArtifact):
            family_scheme_key = payload.family_scheme_key
            title = f"Workload graph for {payload.run_id}"
        if isinstance(artifact, WorkloadMotifArtifact):
            motif_key = payload.motif_key
            title = payload.title
        if isinstance(artifact, WorkloadEpisodeArtifact):
            motif_key = payload.motif_key
            title = payload.title
            family_scheme_key = payload.family_scheme_key

        material = canonical_data(payload)
        search_text = " ".join(
            value
            for value in (
                artifact.artifact_id,
                artifact.artifact_kind,
                artifact.schema_version,
                str(run_id or ""),
                str(name or ""),
                str(title or ""),
                str(mechanism_key or ""),
                str(motif_key or ""),
                json.dumps(material, sort_keys=True, default=str),
            )
            if value
        ).lower()
        return {
            "run_id": run_id,
            "name": name,
            "mode": mode,
            "status": status,
            "title": title,
            "mechanism_key": mechanism_key,
            "severity": severity,
            "confidence": confidence,
            "family_scheme_key": family_scheme_key,
            "query_shape_fingerprint": query_shape_fingerprint,
            "motif_key": motif_key,
            "search_text": search_text,
            "metadata_json": json.dumps(material, sort_keys=True, default=str),
            "tags": tags,
        }

    def upsert(self, artifact: Any) -> None:
        metadata = self._metadata(artifact)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO artifacts (
                    artifact_id, artifact_kind, schema_version, content_hash, created_at,
                    run_id, name, mode, status, title, mechanism_key, severity, confidence,
                    family_scheme_key, query_shape_fingerprint, motif_key, search_text, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(artifact_id) DO UPDATE SET
                    artifact_kind=excluded.artifact_kind,
                    schema_version=excluded.schema_version,
                    content_hash=excluded.content_hash,
                    created_at=excluded.created_at,
                    run_id=excluded.run_id,
                    name=excluded.name,
                    mode=excluded.mode,
                    status=excluded.status,
                    title=excluded.title,
                    mechanism_key=excluded.mechanism_key,
                    severity=excluded.severity,
                    confidence=excluded.confidence,
                    family_scheme_key=excluded.family_scheme_key,
                    query_shape_fingerprint=excluded.query_shape_fingerprint,
                    motif_key=excluded.motif_key,
                    search_text=excluded.search_text,
                    metadata_json=excluded.metadata_json
                """,
                (
                    artifact.artifact_id,
                    artifact.artifact_kind,
                    artifact.schema_version,
                    artifact.content_hash,
                    artifact.created_at.isoformat(),
                    metadata["run_id"],
                    metadata["name"],
                    metadata["mode"],
                    metadata["status"],
                    metadata["title"],
                    metadata["mechanism_key"],
                    metadata["severity"],
                    metadata["confidence"],
                    metadata["family_scheme_key"],
                    metadata["query_shape_fingerprint"],
                    metadata["motif_key"],
                    metadata["search_text"],
                    metadata["metadata_json"],
                ),
            )
            db.execute("DELETE FROM artifact_tags WHERE artifact_id = ?", (artifact.artifact_id,))
            db.executemany(
                "INSERT OR IGNORE INTO artifact_tags(artifact_id, tag) VALUES (?, ?)",
                ((artifact.artifact_id, tag) for tag in metadata["tags"]),
            )
            db.execute("DELETE FROM provenance_edges WHERE source_artifact_id = ?", (artifact.artifact_id,))
            edges = [
                (artifact.artifact_id, ref.artifact_id, "input")
                for ref in artifact.provenance.input_refs
            ]
            if artifact.provenance.configuration_ref is not None:
                edges.append(
                    (
                        artifact.artifact_id,
                        artifact.provenance.configuration_ref.artifact_id,
                        "configuration",
                    )
                )
            db.executemany(
                "INSERT OR IGNORE INTO provenance_edges(source_artifact_id, target_artifact_id, relationship) VALUES (?, ?, ?)",
                edges,
            )

    def rebuild(self, store: FilesystemArtifactStore) -> int:
        with self._connect() as db:
            db.execute("DELETE FROM provenance_edges")
            db.execute("DELETE FROM artifact_tags")
            db.execute("DELETE FROM artifacts")
        count = 0
        for record in store.list():
            self.upsert(store.load(record.artifact_id))
            count += 1
        return count

    def sync(self, store: FilesystemArtifactStore) -> int:
        records = store.list()
        known = {record.artifact_id for record in records}
        with self._connect() as db:
            existing = {row[0] for row in db.execute("SELECT artifact_id FROM artifacts")}
            stale = existing - known
            db.executemany("DELETE FROM artifacts WHERE artifact_id = ?", ((item,) for item in stale))
        for record in records:
            self.upsert(store.load(record.artifact_id))
        return len(records)

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        result["metadata"] = json.loads(result.pop("metadata_json"))
        return result

    def search(
        self,
        *,
        query: str | None = None,
        artifact_kind: str | None = None,
        run_id: str | None = None,
        tag: str | None = None,
        status: str | None = None,
        mode: str | None = None,
        mechanism_key: str | None = None,
        severity: str | None = None,
        motif_key: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> SearchPage:
        limit = max(1, min(limit, 500))
        offset = max(0, offset)
        where: list[str] = []
        params: list[Any] = []
        joins = ""
        if query:
            where.append("a.search_text LIKE ?")
            params.append(f"%{query.lower()}%")
        for column, value in (
            ("artifact_kind", artifact_kind),
            ("run_id", run_id),
            ("status", status),
            ("mode", mode),
            ("mechanism_key", mechanism_key),
            ("severity", severity),
            ("motif_key", motif_key),
        ):
            if value:
                where.append(f"a.{column} = ?")
                params.append(value)
        if tag:
            joins += " JOIN artifact_tags t ON t.artifact_id = a.artifact_id "
            where.append("t.tag = ?")
            params.append(tag)
        clause = " WHERE " + " AND ".join(where) if where else ""
        select = f"FROM artifacts a {joins}{clause}"
        with self._connect() as db:
            total = int(db.execute(f"SELECT COUNT(DISTINCT a.artifact_id) {select}", params).fetchone()[0])
            rows = db.execute(
                f"SELECT DISTINCT a.* {select} ORDER BY a.created_at DESC, a.artifact_id LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return SearchPage(items=tuple(self._row(row) for row in rows), total=total, limit=limit, offset=offset)

    def related(self, artifact_id: str) -> dict[str, tuple[dict[str, Any], ...]]:
        with self._connect() as db:
            outgoing = db.execute(
                """
                SELECT e.relationship, a.* FROM provenance_edges e
                LEFT JOIN artifacts a ON a.artifact_id = e.target_artifact_id
                WHERE e.source_artifact_id = ? ORDER BY e.relationship, e.target_artifact_id
                """,
                (artifact_id,),
            ).fetchall()
            incoming = db.execute(
                """
                SELECT e.relationship, a.* FROM provenance_edges e
                LEFT JOIN artifacts a ON a.artifact_id = e.source_artifact_id
                WHERE e.target_artifact_id = ? ORDER BY e.relationship, e.source_artifact_id
                """,
                (artifact_id,),
            ).fetchall()
        return {
            "inputs": tuple(self._row(row) for row in outgoing if row["artifact_id"] is not None),
            "derived": tuple(self._row(row) for row in incoming if row["artifact_id"] is not None),
        }

    def stats(self) -> dict[str, Any]:
        with self._connect() as db:
            total = int(db.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0])
            kinds = {row[0]: row[1] for row in db.execute("SELECT artifact_kind, COUNT(*) FROM artifacts GROUP BY artifact_kind ORDER BY artifact_kind")}
            runs = int(db.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_kind = 'run_manifest'").fetchone()[0])
            findings = int(db.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_kind = 'finding'").fetchone()[0])
            episodes = int(db.execute("SELECT COUNT(*) FROM artifacts WHERE artifact_kind = 'workload_episode'").fetchone()[0])
        return {"total_artifacts": total, "runs": runs, "findings": findings, "episodes": episodes, "by_kind": kinds}
