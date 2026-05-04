"""JSONL ledger storage and DuckDB index management."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import duckdb

if TYPE_CHECKING:
    from kronos.research.experiments.schema import ExperimentRunRecord


def experiment_root(base_path: str | Path, run_id: str) -> Path:
    return Path(base_path) / "experiments" / run_id


def ledger_jsonl_path(base_path: str | Path) -> Path:
    root = Path(base_path) / "experiments"
    root.mkdir(parents=True, exist_ok=True)
    return root / "ledger.jsonl"


def ledger_duckdb_path(base_path: str | Path) -> Path:
    root = Path(base_path) / "experiments"
    root.mkdir(parents=True, exist_ok=True)
    return root / "ledger.duckdb"


def append_run_record(record: ExperimentRunRecord, *, base_path: str | Path) -> Path:
    """Append a validated record to the JSONL ledger."""
    ledger_path = ledger_jsonl_path(base_path)
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(record.model_dump_json())
        handle.write("\n")
    return ledger_path


def rebuild_ledger_index(*, base_path: str | Path) -> Path:
    """Rebuild the DuckDB index from the JSONL ledger."""
    ledger_path = ledger_jsonl_path(base_path)
    duckdb_path = ledger_duckdb_path(base_path)
    connection = duckdb.connect(str(duckdb_path))
    try:
        if ledger_path.exists() and ledger_path.read_text(encoding="utf-8").strip():
            connection.execute(
                f"""
                CREATE OR REPLACE TABLE runs AS
                SELECT *
                FROM read_json_auto('{ledger_path}', format='newline_delimited')
                """
            )
        else:
            connection.execute(
                """
                CREATE OR REPLACE TABLE runs (
                    run_id VARCHAR,
                    git_commit VARCHAR,
                    data_snapshot_id VARCHAR,
                    config_hash VARCHAR,
                    factors VARCHAR[],
                    universe VARCHAR[],
                    split_dates JSON,
                    results JSON,
                    artifact_paths JSON,
                    module VARCHAR,
                    created_at VARCHAR,
                    factors_key VARCHAR,
                    universe_key VARCHAR,
                    split_dates_key VARCHAR,
                    numeric_results_json VARCHAR
                )
                """
            )
    finally:
        connection.close()
    return duckdb_path
