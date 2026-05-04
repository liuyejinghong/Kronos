"""Unit tests for Alphalens adapter and report export."""

from __future__ import annotations

import json

import pandas as pd
import pyarrow as pa

from kronos.data.storage.parquet_store import write_partition
from kronos.factor.validation import (
    ValidationConfig,
    ValidationOutcome,
    ValidationResult,
    export_alphalens_report,
    load_prices_for_alphalens,
    persist_validation_result,
    prepare_alphalens_factor_data,
)


def _factor_frame() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows: list[dict[str, object]] = []
    for step in range(6):
        for symbol, value in [("BTCUSDT", 1.0 + step), ("ETHUSDT", -1.0 - step)]:
            rows.append({
                "available_at": base + step * 3_600_000,
                "symbol": symbol,
                "value": value if step > 0 else None,
            })
    return pd.DataFrame(rows)


def _price_frame() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows: list[dict[str, object]] = []
    for step in range(10):
        rows.append({
            "available_at": base + step * 3_600_000,
            "symbol": "BTCUSDT",
            "close": 100.0 + step,
        })
        rows.append({
            "available_at": base + step * 3_600_000,
            "symbol": "ETHUSDT",
            "close": 200.0 + step * 0.5,
        })
    return pd.DataFrame(rows)


def _write_price_partitions(tmp_path) -> None:
    base = 1_700_000_000_000
    now = 1_800_000_000_000
    for symbol, open_price in [("BTCUSDT", 100.0), ("ETHUSDT", 200.0)]:
        event_times = [base + i * 60_000 for i in range(12)]
        table = pa.table({
            "event_time": pa.array(event_times, type=pa.int64()),
            "available_at": pa.array([t + 60_000 for t in event_times], type=pa.int64()),
            "ingested_at": pa.array([now] * 12, type=pa.int64()),
            "symbol": [symbol] * 12,
            "open": pa.array([open_price + i for i in range(12)], type=pa.float64()),
            "high": pa.array([open_price + i + 1 for i in range(12)], type=pa.float64()),
            "low": pa.array([open_price + i - 1 for i in range(12)], type=pa.float64()),
            "close": pa.array([open_price + i + 0.5 for i in range(12)], type=pa.float64()),
            "volume": pa.array([100.0] * 12, type=pa.float64()),
        })
        write_partition(table, tmp_path, symbol, "klines_1m", 2023, 11)


def _validation_result() -> ValidationResult:
    return ValidationResult(
        outcome=ValidationOutcome.PASS,
        ic_table=pd.DataFrame([{"period": 1, "ic": 0.1, "rank_ic": 0.2, "n_obs": 10}]),
        mean_rank_ic=0.2,
        rank_ic_positive_ratio=0.7,
        ic_ir=1.0,
        quantile_returns=pd.Series({1: -0.01, 2: 0.01}, dtype=float),
        top_minus_bottom=0.02,
        median_turnover=0.3,
        top_turnover=0.2,
        bottom_turnover=0.4,
        decay=pd.DataFrame([{"period": 1, "mean_rank_ic": 0.2, "rank_ic_positive_ratio": 0.7}]),
        forward_returns=pd.DataFrame({"fwd_1": [0.01, 0.02]}),
        n_obs=10,
        skipped_pct=0.0,
        config=ValidationConfig(periods=[1, 3], quantiles=2),
    )


class TestPrepareAlphalensFactorData:
    def test_outputs_utc_factor_data_and_metadata(self) -> None:
        factor_data, metadata = prepare_alphalens_factor_data(
            _factor_frame(),
            _price_frame(),
            quantiles=2,
            periods=[1, 3],
        )

        dates = factor_data.index.get_level_values("date")
        assert str(dates.tz) == "UTC"
        assert metadata["filter_zscore"] is None
        assert metadata["periods"] == [1, 3]
        assert metadata["quantiles"] == 2
        assert 0.0 <= float(metadata["max_loss"]) <= 1.0


class TestLoadPricesForAlphalens:
    def test_loads_universe_with_forward_buffer(self, tmp_path) -> None:
        _write_price_partitions(tmp_path)
        base = 1_700_000_000_000

        df = load_prices_for_alphalens(
            ["BTCUSDT", "ETHUSDT"],
            base_path=tmp_path,
            timeframe="1m",
            since=base,
            until=base + 5 * 60_000,
            periods=[3],
        )

        assert set(df["symbol"].unique()) == {"BTCUSDT", "ETHUSDT"}
        assert len(df) == 16


class TestExportAlphalensReport:
    def test_exports_versioned_report_images(self, tmp_path) -> None:
        factor_data, _ = prepare_alphalens_factor_data(
            _factor_frame(),
            _price_frame(),
            quantiles=2,
            periods=[1, 3],
        )

        run_dir, exported = export_alphalens_report(
            factor_data,
            factor_name="factor_x",
            factor_version="1.0.0",
            periods=[1, 3],
            base_dir=tmp_path,
            run_id="run001",
        )

        assert run_dir == tmp_path / "factor_x" / "1.0.0"
        assert len(exported) == 3
        assert all(path.exists() for path in exported)

    def test_persist_validation_result_merges_alphalens_metadata(self, tmp_path) -> None:
        factor_data, metadata = prepare_alphalens_factor_data(
            _factor_frame(),
            _price_frame(),
            quantiles=2,
            periods=[1, 3],
        )
        run_dir = persist_validation_result(
            _validation_result(),
            "factor_x",
            base_dir=tmp_path,
            run_id="run002",
            factor_version="1.0.0",
            timeframe="1h",
            universe=["BTCUSDT", "ETHUSDT"],
            extra_report_metadata={"alphalens": metadata},
        )

        content = json.loads((run_dir / "metrics.json").read_text())
        assert content["report_metadata"]["alphalens"]["filter_zscore"] is None
        assert content["report_metadata"]["alphalens"]["periods"] == [1, 3]
        assert content["report_metadata"]["factor_version"] == "1.0.0"
        assert content["report_metadata"]["run_id"] == "run002"
        assert factor_data.index.names == ["date", "asset"]
