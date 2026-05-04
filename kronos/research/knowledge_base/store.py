"""SQLite + FTS research knowledge base."""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from kronos.research.experiments.schema import ExperimentRunRecord


@dataclass(frozen=True)
class KnowledgeEntry:
    """Structured research-memory entry."""

    entry_id: int
    entry_type: str
    title: str
    summary: str
    run_id: str | None
    factor_name: str | None
    tags: list[str]
    metadata_json: str


def knowledge_base_path(base_path: str | Path) -> Path:
    root = Path(base_path) / "knowledge_base"
    root.mkdir(parents=True, exist_ok=True)
    return root / "knowledge.db"


def init_knowledge_base(*, base_path: str | Path) -> Path:
    """Initialise the SQLite + FTS research knowledge base."""
    db_path = knowledge_base_path(base_path)
    connection = sqlite3.connect(db_path)
    try:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entry_type TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                run_id TEXT,
                factor_name TEXT,
                tags_json TEXT NOT NULL,
                metadata_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_entries_fts
            USING fts5(title, summary, tags, content='knowledge_entries', content_rowid='id')
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_entries_ai
            AFTER INSERT ON knowledge_entries
            BEGIN
              INSERT INTO knowledge_entries_fts(rowid, title, summary, tags)
              VALUES (new.id, new.title, new.summary, new.tags_json);
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_entries_ad
            AFTER DELETE ON knowledge_entries
            BEGIN
              INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rowid, title, summary, tags)
              VALUES ('delete', old.id, old.title, old.summary, old.tags_json);
            END
            """
        )
        connection.execute(
            """
            CREATE TRIGGER IF NOT EXISTS knowledge_entries_au
            AFTER UPDATE ON knowledge_entries
            BEGIN
              INSERT INTO knowledge_entries_fts(knowledge_entries_fts, rowid, title, summary, tags)
              VALUES ('delete', old.id, old.title, old.summary, old.tags_json);
              INSERT INTO knowledge_entries_fts(rowid, title, summary, tags)
              VALUES (new.id, new.title, new.summary, new.tags_json);
            END
            """
        )
    finally:
        connection.commit()
        connection.close()
    return db_path


def add_experiment_entry(record: ExperimentRunRecord, *, base_path: str | Path) -> int:
    """Add an experiment-memory entry based on an experiment run record."""
    summary = json.dumps(record.results, ensure_ascii=False)
    tags = [record.module, *record.factors]
    return _insert_entry(
        base_path=base_path,
        entry_type="experiment",
        title=f"{record.module}:{record.run_id}",
        summary=summary,
        run_id=record.run_id,
        factor_name=record.factors[0] if record.factors else None,
        tags=tags,
        metadata={
            "git_commit": record.git_commit,
            "data_snapshot_id": record.data_snapshot_id,
            "artifact_paths": record.artifact_paths,
            "results": record.results,
        },
    )


def add_failure_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add a failure-memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="failure_reason",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
    )


def add_candidate_disposition_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add a candidate-disposition memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="candidate_disposition",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
    )


def add_watchlist_review_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add a watchlist-review memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="watchlist_review",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
    )


def add_watchlist_evidence_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add a watchlist-evidence memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="watchlist_evidence",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id") or metadata.get("batch_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
    )


def add_agent_plan_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add an agent-generated research-plan memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="agent_research_plan",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
        replace_existing_run_entry=True,
    )


def add_agent_decision_entry(
    *,
    title: str,
    summary: str,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    base_path: str | Path,
) -> int:
    """Add an agent-generated research decision memory entry."""
    return _insert_entry(
        base_path=base_path,
        entry_type="agent_research_decision",
        title=title,
        summary=summary,
        run_id=metadata.get("run_id"),
        factor_name=factor_name,
        tags=tags,
        metadata=metadata,
        replace_existing_run_entry=True,
    )


def search_entries(
    query: str,
    *,
    base_path: str | Path,
    entry_type: str | None = None,
    limit: int = 20,
) -> list[KnowledgeEntry]:
    """Search research memory through SQLite FTS."""
    db_path = init_knowledge_base(base_path=base_path)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        sql = """
            SELECT
                e.id,
                e.entry_type,
                e.title,
                e.summary,
                e.run_id,
                e.factor_name,
                e.tags_json,
                e.metadata_json
            FROM knowledge_entries_fts f
            JOIN knowledge_entries e ON e.id = f.rowid
            WHERE knowledge_entries_fts MATCH ?
        """
        params: list[Any] = [query]
        if entry_type is not None:
            sql += " AND e.entry_type = ?"
            params.append(entry_type)
        sql += " ORDER BY e.id DESC LIMIT ?"
        params.append(limit)
        rows = connection.execute(sql, params).fetchall()
    finally:
        connection.close()

    return [
        KnowledgeEntry(
            entry_id=row["id"],
            entry_type=row["entry_type"],
            title=row["title"],
            summary=row["summary"],
            run_id=row["run_id"],
            factor_name=row["factor_name"],
            tags=json.loads(row["tags_json"]),
            metadata_json=row["metadata_json"],
        )
        for row in rows
    ]


def _insert_entry(
    *,
    base_path: str | Path,
    entry_type: str,
    title: str,
    summary: str,
    run_id: str | None,
    factor_name: str | None,
    tags: list[str],
    metadata: dict[str, Any],
    replace_existing_run_entry: bool = False,
) -> int:
    db_path = init_knowledge_base(base_path=base_path)
    connection = sqlite3.connect(db_path)
    try:
        if replace_existing_run_entry and run_id:
            connection.execute(
                """
                DELETE FROM knowledge_entries
                WHERE entry_type = ? AND run_id = ?
                """,
                (entry_type, run_id),
            )
        cursor = connection.execute(
            """
            INSERT INTO knowledge_entries (
                entry_type,
                title,
                summary,
                run_id,
                factor_name,
                tags_json,
                metadata_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry_type,
                title,
                summary,
                run_id,
                factor_name,
                json.dumps(tags, ensure_ascii=False),
                json.dumps(_json_safe(metadata), ensure_ascii=False, allow_nan=False),
            ),
        )
        entry_id = int(cursor.lastrowid or 0)
    finally:
        connection.commit()
        connection.close()
    return entry_id


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value
