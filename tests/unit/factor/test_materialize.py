"""Unit tests for factor materialization and cache identity."""

from __future__ import annotations

import json
from typing import Any

import pandas as pd

from kronos.factor.materialize import (
    feature_partition_path,
    is_cache_valid,
    meta_path,
    read_factor_all,
    read_factor_partition,
    write_factor_partition,
)
from kronos.factor.registry import compute_params_hash

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_factor_df(n: int = 20) -> pd.DataFrame:
    base_ts = 1_709_251_200_000  # 2024-03-01 UTC
    return pd.DataFrame({
        "event_time": [base_ts + i * 3_600_000 for i in range(n)],
        "available_at": [base_ts + (i + 1) * 3_600_000 for i in range(n)],
        "symbol": ["BTCUSDT"] * n,
        "value": [float(i) for i in range(n)],
    })


FACTOR_META: dict[str, Any] = {"lookback": 20}
SOURCE_INGESTED = 1_700_000_000_000


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

class TestPartitionPath:
    def test_path_includes_symbol(self, tmp_path) -> None:
        p = feature_partition_path(tmp_path, "asi_spread", "1.0.0", "1h", "BTCUSDT", 2024, 3)
        assert "BTCUSDT" in str(p)

    def test_path_structure(self, tmp_path) -> None:
        p = feature_partition_path(tmp_path, "asi_spread", "1.0.0", "1h", "BTCUSDT", 2024, 3)
        assert str(p).endswith("features/asi_spread/1.0.0/1h/BTCUSDT/2024/03.parquet")

    def test_month_zero_padded(self, tmp_path) -> None:
        p = feature_partition_path(tmp_path, "f", "1.0.0", "1h", "BTC", 2024, 1)
        assert "01.parquet" in str(p)

    def test_meta_path_sibling(self, tmp_path) -> None:
        p = feature_partition_path(tmp_path, "f", "1.0.0", "1h", "BTC", 2024, 3)
        mp = meta_path(p)
        assert mp.parent == p.parent
        assert mp.name == "03_meta.json"


# ---------------------------------------------------------------------------
# Write + Read
# ---------------------------------------------------------------------------

class TestWriteRead:
    def test_write_creates_parquet(self, tmp_path) -> None:
        df = _make_factor_df(5)
        paths = write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        assert len(paths) > 0
        assert paths[0].exists()

    def test_write_creates_meta_json(self, tmp_path) -> None:
        df = _make_factor_df(5)
        paths = write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        mp = meta_path(paths[0])
        assert mp.exists()
        manifest = json.loads(mp.read_text())
        assert manifest["factor_name"] == "cmo"
        assert manifest["factor_version"] == "1.0.0"
        assert manifest["symbol"] == "BTCUSDT"
        assert "params_hash" in manifest
        assert "source_max_ingested_at" in manifest

    def test_read_returns_data(self, tmp_path) -> None:
        df = _make_factor_df(5)
        write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        result = read_factor_partition(tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3)
        assert result is not None
        assert len(result) == 5

    def test_read_missing_returns_none(self, tmp_path) -> None:
        result = read_factor_partition(tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3)
        assert result is None

    def test_read_all_combines_months(self, tmp_path) -> None:
        # 24 hours = spans two months (March 31 + April 1)
        # Use data that spans March and April 2024
        mar_ts = 1_711_843_200_000  # 2024-03-31 00:00 UTC
        apr_ts = 1_711_929_600_000  # 2024-04-01 00:00 UTC
        df = pd.DataFrame({
            "event_time": [mar_ts, apr_ts],
            "available_at": [mar_ts + 3_600_000, apr_ts + 3_600_000],
            "symbol": ["BTCUSDT", "BTCUSDT"],
            "value": [1.0, 2.0],
        })
        write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        result = read_factor_all(tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT")
        assert result is not None
        assert len(result) == 2

    def test_write_empty_returns_no_paths(self, tmp_path) -> None:
        df = pd.DataFrame(columns=["event_time", "available_at", "symbol", "value"])
        paths = write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        assert paths == []


# ---------------------------------------------------------------------------
# params_hash
# ---------------------------------------------------------------------------

class TestParamsHash:
    def test_hash_is_12_chars(self) -> None:
        h = compute_params_hash({"lookback": 20})
        assert len(h) == 12

    def test_same_params_same_hash(self) -> None:
        h1 = compute_params_hash({"lookback": 20, "window": 5})
        h2 = compute_params_hash({"window": 5, "lookback": 20})
        assert h1 == h2  # key order doesn't matter

    def test_different_params_different_hash(self) -> None:
        h1 = compute_params_hash({"lookback": 20})
        h2 = compute_params_hash({"lookback": 21})
        assert h1 != h2


# ---------------------------------------------------------------------------
# Cache validity
# ---------------------------------------------------------------------------

class TestCacheValidity:
    def _write_and_get_hash(self, tmp_path) -> str:
        df = _make_factor_df(5)
        write_factor_partition(
            df, tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", FACTOR_META, SOURCE_INGESTED
        )
        return compute_params_hash(FACTOR_META)

    def test_valid_cache(self, tmp_path) -> None:
        expected_hash = self._write_and_get_hash(tmp_path)
        assert is_cache_valid(
            tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3,
            expected_hash, SOURCE_INGESTED,
        )

    def test_invalid_when_missing(self, tmp_path) -> None:
        assert not is_cache_valid(
            tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3,
            "somehash", SOURCE_INGESTED,
        )

    def test_invalid_when_params_hash_differs(self, tmp_path) -> None:
        self._write_and_get_hash(tmp_path)
        assert not is_cache_valid(
            tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3,
            "wronghash123", SOURCE_INGESTED,
        )

    def test_invalid_when_source_data_advanced(self, tmp_path) -> None:
        expected_hash = self._write_and_get_hash(tmp_path)
        newer_ingested = SOURCE_INGESTED + 1
        assert not is_cache_valid(
            tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3,
            expected_hash, newer_ingested,
        )

    def test_valid_when_source_same(self, tmp_path) -> None:
        expected_hash = self._write_and_get_hash(tmp_path)
        assert is_cache_valid(
            tmp_path, "cmo", "1.0.0", "1h", "BTCUSDT", 2024, 3,
            expected_hash, SOURCE_INGESTED,
        )
