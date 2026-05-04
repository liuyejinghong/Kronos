"""Unit tests for signal diagnostics."""

from __future__ import annotations

import json

import pandas as pd

from kronos.factor.diagnostics import analyze_signal_diagnostics, persist_signal_diagnostics_result


def _signals() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for step in range(12):
        timestamp = base + step * 3_600_000
        rows.append({"timestamp": timestamp, "symbol": "BTCUSDT", "signal": 1.0 + step, "factor_name": "momentum"})
        rows.append({"timestamp": timestamp, "symbol": "ETHUSDT", "signal": -1.0 - step, "factor_name": "momentum"})
        rows.append({"timestamp": timestamp, "symbol": "SOLUSDT", "signal": 0.5 + step * 0.2, "factor_name": "momentum"})
        rows.append({"timestamp": timestamp, "symbol": "BTCUSDT", "signal": 0.2 + step * 0.1, "factor_name": "liquidity"})
        rows.append({"timestamp": timestamp, "symbol": "ETHUSDT", "signal": -0.2 - step * 0.1, "factor_name": "liquidity"})
        rows.append({"timestamp": timestamp, "symbol": "SOLUSDT", "signal": 0.1 + step * 0.05, "factor_name": "liquidity"})
    return pd.DataFrame(rows)


def _prices() -> pd.DataFrame:
    base = 1_700_000_000_000
    rows = []
    for step in range(16):
        timestamp = base + step * 3_600_000
        rows.extend([
            {"available_at": timestamp, "symbol": "BTCUSDT", "close": 100 + step, "volume": 300 - step, "funding_rate": 0.0001},
            {"available_at": timestamp, "symbol": "ETHUSDT", "close": 200 - step * 0.4, "volume": 150 + step, "funding_rate": -0.0001},
            {"available_at": timestamp, "symbol": "SOLUSDT", "close": 50 + step * 0.3, "volume": 120 + step * 0.5, "funding_rate": 0.00005},
        ])
    return pd.DataFrame(rows)


class TestSignalDiagnostics:
    def test_analyze_outputs_expected_sections(self) -> None:
        diagnostics = analyze_signal_diagnostics(_signals(), _prices(), periods=[1, 3], quantile_buckets=[5, 10])

        assert not diagnostics.ic_timeseries.empty
        assert "q5" in diagnostics.grouped_returns
        assert "q10" in diagnostics.grouped_returns
        assert not diagnostics.decay.empty
        assert not diagnostics.correlation_matrix.empty
        assert "high_liquidity_rank_ic" in diagnostics.liquidity_filter
        assert "high_vol_rank_ic" in diagnostics.regime_split

    def test_persist_writes_structured_artifacts(self, tmp_path) -> None:
        diagnostics = analyze_signal_diagnostics(_signals(), _prices(), periods=[1, 3], quantile_buckets=[5, 10])
        run_dir, artifacts = persist_signal_diagnostics_result(
            diagnostics,
            signal_name="diagnostics_bundle",
            base_dir=tmp_path,
            run_id="run001",
        )

        assert run_dir == tmp_path / "diagnostics_bundle" / "run001"
        assert set(artifacts) == {
            "summary",
            "ic_timeseries",
            "decay",
            "correlation_matrix",
            "correlation_heatmap",
        }
        payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
        assert payload["signal_name"] == "diagnostics_bundle"
        assert payload["run_id"] == "run001"
