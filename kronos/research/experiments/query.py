"""DuckDB-backed experiment comparison queries."""

from __future__ import annotations

from typing import TYPE_CHECKING

import duckdb

from kronos.research.experiments.ledger import ledger_duckdb_path, rebuild_ledger_index
from kronos.research.experiments.schema import _stable_json

if TYPE_CHECKING:
    from pathlib import Path

    import pandas as pd


def query_runs(
    *,
    base_path: str | Path,
    factors: list[str] | None = None,
    universe: list[str] | None = None,
    split_dates: dict[str, object] | None = None,
    git_commit: str | None = None,
    data_snapshot_id: str | None = None,
    config_hash: str | None = None,
    result_metric: str | None = None,
    descending: bool = True,
) -> pd.DataFrame:
    """Query experiment runs through the DuckDB index."""
    rebuild_ledger_index(base_path=base_path)
    db_path = ledger_duckdb_path(base_path)
    connection = duckdb.connect(str(db_path), read_only=True)
    try:
        sql = """
            SELECT
                run_id,
                module,
                git_commit,
                data_snapshot_id,
                config_hash,
                factors,
                universe,
                split_dates,
                results,
                artifact_paths,
                numeric_results_json
            FROM runs
            WHERE 1=1
        """
        params: list[object] = []
        if factors is not None:
            sql += " AND factors_key = ?"
            params.append(_stable_json(sorted(factors)))
        if universe is not None:
            sql += " AND universe_key = ?"
            params.append(_stable_json(sorted(universe)))
        if split_dates is not None:
            sql += " AND split_dates_key = ?"
            params.append(_stable_json(split_dates))
        if git_commit is not None:
            sql += " AND git_commit = ?"
            params.append(git_commit)
        if data_snapshot_id is not None:
            sql += " AND data_snapshot_id = ?"
            params.append(data_snapshot_id)
        if config_hash is not None:
            sql += " AND config_hash = ?"
            params.append(config_hash)
        if result_metric is not None:
            order = "DESC" if descending else "ASC"
            sql += f" ORDER BY TRY_CAST(json_extract_string(numeric_results_json, '$.{result_metric}') AS DOUBLE) {order}"

        return connection.execute(sql, params).fetchdf()
    finally:
        connection.close()


def compare_runs(
    *,
    base_path: str | Path,
    factors: list[str] | None = None,
    universe: list[str] | None = None,
    split_dates: dict[str, object] | None = None,
) -> pd.DataFrame:
    """Return a comparison-friendly projection of experiment runs."""
    frame = query_runs(
        base_path=base_path,
        factors=factors,
        universe=universe,
        split_dates=split_dates,
    )
    if frame.empty:
        return frame
    return frame[
        ["run_id", "git_commit", "data_snapshot_id", "config_hash", "results", "artifact_paths"]
    ].copy()
