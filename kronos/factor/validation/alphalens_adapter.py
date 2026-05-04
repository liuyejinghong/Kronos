"""Alphalens adapter for Kronos factor validation reports."""

from __future__ import annotations

import os
import tempfile
from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import pandas as pd

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


def _prepare_matplotlib_runtime() -> None:
    mpl_dir = Path(tempfile.gettempdir()) / "kronos-mpl"
    mpl_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_dir))
    os.environ.setdefault("XDG_CACHE_HOME", str(mpl_dir))

    import matplotlib

    matplotlib.use("Agg", force=True)


def _load_alphalens_modules() -> dict[str, Any]:
    _prepare_matplotlib_runtime()

    import matplotlib.pyplot as plt
    from alphalens import performance, plotting, tears, utils

    return {
        "performance": performance,
        "plotting": plotting,
        "plt": plt,
        "tears": tears,
        "utils": utils,
    }


def _to_utc_index(epoch_ms: pd.Series) -> pd.DatetimeIndex:
    return pd.DatetimeIndex(pd.to_datetime(epoch_ms.astype("int64"), unit="ms", utc=True))


def _parse_time_input(value: str | int | None) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    return int(pd.Timestamp(value, tz="UTC").timestamp() * 1000)


def load_prices_for_alphalens(
    symbols: list[str],
    *,
    base_path: Path,
    timeframe: str,
    since: str | int | None = None,
    until: str | int | None = None,
    as_of: str | int | None = None,
    periods: Sequence[int] = (1, 3, 5),
) -> pd.DataFrame:
    """Load multi-asset price data with the required forward-return buffer."""
    from kronos.data.storage.query import TIMEFRAME_MINUTES, load_universe

    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(f"Unsupported timeframe for Alphalens loader: {timeframe}")

    until_ms = _parse_time_input(until)
    if until_ms is not None:
        buffer_ms = TIMEFRAME_MINUTES[timeframe] * max(periods) * 60_000
        until_ms += buffer_ms

    return load_universe(
        symbols,
        base_path=base_path,
        timeframe=timeframe,
        since=since,
        until=until_ms,
        as_of=as_of,
    )


def factor_to_alphalens_series(
    factor_df: pd.DataFrame,
    *,
    factor_value_column: str = "value",
    factor_time_column: str = "available_at",
) -> pd.Series:
    """Convert Kronos long-form factor output into Alphalens factor series."""
    required = {factor_time_column, "symbol", factor_value_column}
    missing = required - set(factor_df.columns)
    if missing:
        raise ValueError(f"Missing required factor columns for Alphalens adapter: {sorted(missing)}")

    clean = factor_df[[factor_time_column, "symbol", factor_value_column]].dropna(
        subset=[factor_value_column]
    )
    clean = clean.copy()
    clean["date"] = _to_utc_index(clean[factor_time_column])
    series = clean.set_index(["date", "symbol"])[factor_value_column].sort_index()
    series.index = series.index.set_names(["date", "asset"])
    series.name = "factor"
    return series.astype(float)


def prices_to_alphalens_frame(
    prices_df: pd.DataFrame,
    *,
    price_value_column: str = "close",
    price_time_column: str = "available_at",
) -> pd.DataFrame:
    """Convert Kronos long-form prices into Alphalens wide price frame."""
    required = {price_time_column, "symbol", price_value_column}
    missing = required - set(prices_df.columns)
    if missing:
        raise ValueError(f"Missing required price columns for Alphalens adapter: {sorted(missing)}")

    clean = prices_df[[price_time_column, "symbol", price_value_column]].copy()
    clean["date"] = _to_utc_index(clean[price_time_column])
    wide = (
        clean.pivot_table(index="date", columns="symbol", values=price_value_column, aggfunc="last")
        .sort_index()
        .astype(float)
    )
    wide.index.name = "date"
    return wide


def prepare_alphalens_factor_data(
    factor_df: pd.DataFrame,
    prices_df: pd.DataFrame,
    *,
    factor_value_column: str = "value",
    factor_time_column: str = "available_at",
    price_value_column: str = "close",
    price_time_column: str = "available_at",
    quantiles: int = 5,
    periods: Sequence[int] = (1, 3, 5),
    max_loss_tolerance: float = 1.0,
) -> tuple[pd.DataFrame, dict[str, object]]:
    """Prepare cleaned Alphalens factor data plus run metadata."""
    modules = _load_alphalens_modules()
    utils = modules["utils"]

    factor = factor_to_alphalens_series(
        factor_df,
        factor_value_column=factor_value_column,
        factor_time_column=factor_time_column,
    )
    prices = prices_to_alphalens_frame(
        prices_df,
        price_value_column=price_value_column,
        price_time_column=price_time_column,
    )
    bar_delta = _infer_bar_timedelta(cast("pd.DatetimeIndex", prices.index))
    forward_returns = _build_forward_returns_frame(prices, periods, utils)
    factor_data = utils.get_clean_factor(
        factor,
        forward_returns,
        quantiles=quantiles,
        max_loss=max_loss_tolerance,
    )
    with suppress(ValueError):
        factor_data.index.levels[0].freq = pd.tseries.frequencies.to_offset(
            utils.timedelta_to_string(bar_delta)
        )

    raw_count = len(factor.index)
    dropped_ratio = 0.0 if raw_count == 0 else 1.0 - (len(factor_data.index) / raw_count)
    universe = sorted(str(asset) for asset in factor.index.get_level_values("asset").unique())

    metadata: dict[str, object] = {
        "quantiles": quantiles,
        "periods": list(periods),
        "filter_zscore": None,
        "max_loss": dropped_ratio,
        "universe": universe,
        "factor_rows": raw_count,
        "clean_rows": len(factor_data.index),
    }
    return factor_data, metadata


def _build_forward_returns_frame(
    prices: pd.DataFrame,
    periods: Sequence[int],
    utils: Any,
) -> pd.DataFrame:
    bar_delta = _infer_bar_timedelta(cast("pd.DatetimeIndex", prices.index))
    stacked_periods: dict[str, pd.Series] = {}

    for period in periods:
        period_delta = pd.Timedelta(bar_delta * period)
        column_name = utils.timedelta_to_string(period_delta)
        period_returns = (prices.shift(-period) / prices) - 1.0
        stacked = cast("pd.Series", period_returns.stack())
        stacked.index = stacked.index.set_names(["date", "asset"])
        stacked_periods[column_name] = stacked

    return pd.DataFrame(stacked_periods).sort_index()


def _infer_bar_timedelta(index: pd.DatetimeIndex) -> pd.Timedelta:
    if len(index) < 2:
        raise ValueError("At least two price timestamps are required to infer bar frequency")

    diffs = index.to_series().diff().dropna()
    positive_diffs = diffs[diffs > pd.Timedelta(0)]
    if positive_diffs.empty:
        raise ValueError("Could not infer a positive bar frequency from prices index")
    return pd.Timedelta(positive_diffs.min())


def export_alphalens_tear_sheets(
    factor_data: pd.DataFrame,
    output_dir: str | Path,
    *,
    periods: Sequence[int],
) -> list[Path]:
    """Render and save Alphalens tear sheet images."""
    modules = _load_alphalens_modules()
    plt = modules["plt"]
    tears = modules["tears"]

    target_dir = Path(output_dir)
    target_dir.mkdir(parents=True, exist_ok=True)

    exported: list[Path] = []
    returns_path = target_dir / "returns_tear_sheet.png"
    information_path = target_dir / "information_tear_sheet.png"
    turnover_path = target_dir / "turnover_tear_sheet.png"

    saved = _capture_grid_figure(
        lambda: tears.create_returns_tear_sheet(factor_data),
        returns_path,
    )
    if saved is not None:
        exported.append(saved)

    saved = _capture_grid_figure(
        lambda: _render_information_tear_sheet(factor_data),
        information_path,
    )
    if saved is not None:
        exported.append(saved)

    _save_turnover_tear_sheet(factor_data, turnover_path, periods)
    exported.append(turnover_path)

    plt.close("all")
    return exported


def _capture_grid_figure(render_fn: Callable[[], None], output_path: Path) -> Path | None:
    modules = _load_alphalens_modules()
    plt = modules["plt"]
    tears = modules["tears"]

    original_show = plt.show
    original_close = tears.GridFigure.close
    saved_path: Path | None = None

    def quiet_show(*args: object, **kwargs: object) -> None:
        return None

    def saving_close(self: object) -> None:
        nonlocal saved_path
        figure = getattr(self, "fig", None)
        if figure is not None:
            figure.savefig(output_path, bbox_inches="tight")
            saved_path = output_path
        original_close(self)

    plt.show = quiet_show
    tears.GridFigure.close = saving_close
    try:
        render_fn()
    finally:
        plt.show = original_show
        tears.GridFigure.close = original_close

    return saved_path


def _render_information_tear_sheet(factor_data: pd.DataFrame) -> None:
    modules = _load_alphalens_modules()
    performance = modules["performance"]
    tears = modules["tears"]

    original_mean_ic = performance.mean_information_coefficient

    def compatible_mean_information_coefficient(*args: object, **kwargs: object) -> object:
        if kwargs.get("by_time") == "M":
            kwargs["by_time"] = "ME"
        return original_mean_ic(*args, **kwargs)

    performance.mean_information_coefficient = compatible_mean_information_coefficient
    try:
        tears.create_information_tear_sheet(factor_data)
    finally:
        performance.mean_information_coefficient = original_mean_ic


def _save_turnover_tear_sheet(
    factor_data: pd.DataFrame,
    output_path: Path,
    periods: Sequence[int],
) -> None:
    modules = _load_alphalens_modules()
    performance = modules["performance"]
    plotting = modules["plotting"]
    plt = modules["plt"]

    quantile_factor = factor_data["factor_quantile"]
    quantile_turnover = {
        period: pd.concat(
            [
                performance.quantile_turnover(quantile_factor, quantile, period)
                for quantile in quantile_factor.sort_values().unique().tolist()
            ],
            axis=1,
        )
        for period in periods
    }
    autocorrelation = pd.concat(
        [performance.factor_rank_autocorrelation(factor_data, period) for period in periods],
        axis=1,
    )

    valid_turnover_periods = [
        period for period in periods if not quantile_turnover[period].isnull().all().all()
    ]
    valid_autocorr_periods = [
        period for period in autocorrelation.columns if not autocorrelation[period].isnull().all()
    ]
    rows = max(1, len(valid_turnover_periods) + len(valid_autocorr_periods))

    fig, axes = plt.subplots(rows, 1, figsize=(14, max(1, rows) * 4))
    axes_list = list(axes.flat) if hasattr(axes, "flat") else [axes]

    row_index = 0
    for period in valid_turnover_periods:
        plotting.plot_top_bottom_quantile_turnover(
            quantile_turnover[period],
            period=period,
            ax=axes_list[row_index],
        )
        row_index += 1

    for period in valid_autocorr_periods:
        plotting.plot_factor_rank_auto_correlation(
            autocorrelation[period],
            period=period,
            ax=axes_list[row_index],
        )
        row_index += 1

    if row_index == 0:
        axes_list[0].text(0.5, 0.5, "No turnover diagnostics available", ha="center", va="center")
        axes_list[0].set_axis_off()

    fig.tight_layout()
    fig.savefig(output_path, bbox_inches="tight")
    plt.close(fig)
