"""Immutable data snapshot freezing with quality gates (package P07).

Binds one evaluation to an immutable, content-addressed dataset: builds a
:class:`~kronos.research.verdict.contracts.DataSnapshotManifest` from a P06
:class:`~kronos.research.verdict.readiness.DataReadinessPlan` by running the
per-symbol x dataset quality gates over the local parquet store for the target
window (including warmup), then freezes the manifest to disk and can later
re-verify it against the store (tamper / drift detection).

Quality gates (one False vote anywhere taints the whole snapshot; the frozen
contract coerces ``overall_status`` to ``invalid`` — this module constructs
with ``"valid"`` and lets contract validation coerce, never reimplementing the
one-vote-veto rule):

- ``closed_bars_only`` (klines_1m): every bar's ``available_at`` (bar close,
  the PIT anchor) must be <= the next bar's ``event_time``, and the final bar
  must be closed by the window end. Full deterministic scan of all boundary
  rows — no sampling (spec: 时间可知性必须显式, no future visibility).
- ``no_interior_gaps``: reuses :func:`kronos.data.storage.query.detect_gaps`
  against the window and fails when any gap region overlaps it; head/tail
  completeness is folded in (first and last grid point of the gated span must
  exist).
- ``no_duplicates``: no duplicate ``event_time`` per symbol/dataset.
- ``no_synthetic_mix``: the venue column must be all ``"binance"``. Funding
  has no venue column by schema and counts as its declared source. Any
  synthetic row names the whole dataset venue ``"synthetic"``, which by itself
  forces the snapshot invalid (contract one-vote-veto).
- ``resample_buckets_complete`` (klines_1m): every bucket of the resample
  timeframe (default 15m) inside the gated span — warmup included — must hold
  exactly all of its 1m bars.
- ``funding_coverage``: funding settlements must span the window at venue
  cadence: every 8h grid slot in the span must contain at least one event.
  Symbols on the documented denser 4h/1h cadence still satisfy the slot check
  (see ``FUNDING_CADENCE_NOTE``); a missing settlement is any >1x-cadence
  hole, matching ``detect_gaps`` semantics (>= 2x interval flags).

Content hash (partition-layout independent, documented algorithm): for each
row inside the gated span build the canonical line ``"{event_time},{symbol}"``
extended with the replay-relevant values — ``{open},{high},{low},{close}``
for klines_1m and ``{funding_rate}`` for funding — with floats serialized via
``repr()`` (shortest round-trip, stable across runs); sort rows ascending,
join with ``"\n"`` (no trailing newline), UTF-8 encode, take SHA-256 hex
digest. The hash binds data values, not file bytes or partition layout, so
regrouping the same rows changes nothing while any value edit changes the
hash: same snapshot id implies the same backtest result (同快照 ID = 同结果).
``snapshot_id`` is a short hash over the window bounds, symbols and the
dataset content hashes; rebuilding with the same inputs deterministically
reuses the same id (快照复用, never silently moving the data cutoff).
"""

from __future__ import annotations

import hashlib
import os
import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final

import pandas as pd
from pydantic import ValidationError

from kronos.common.log import get_logger
from kronos.data.storage.query import DATASET_INTERVAL_MS, TIMEFRAME_MINUTES, detect_gaps, load
from kronos.research.verdict.contracts import DatasetManifest, DataSnapshotManifest

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from kronos.research.verdict.contracts import DatasetName
    from kronos.research.verdict.readiness import DataReadinessPlan

log = get_logger("kronos.research.verdict.snapshot")

DAY_MS: Final[int] = 86_400_000
MINUTE_MS: Final[int] = DATASET_INTERVAL_MS["klines_1m"]
FUNDING_INTERVAL_MS: Final[int] = DATASET_INTERVAL_MS["funding"]

# Datasets bound into a snapshot. OI is intentionally absent (spec: 不拉无关数据).
SNAPSHOT_DATASETS: Final[tuple[DatasetName, ...]] = ("klines_1m", "funding")

# Declared provenance of every dataset in the snapshot (Binance USDM public data).
SNAPSHOT_SOURCE: Final[str] = "binance_usdm_public"
REAL_VENUE: Final[str] = "binance"
SYNTHETIC_VENUE: Final[str] = "synthetic"
MIXED_VENUE: Final[str] = "mixed"
VENUE_COLUMN: Final[str] = "venue"

# Canonical columns the gate helpers and content hashing read; used to
# normalize the column-less empty frame that query.load returns when a store
# has no files at all. Superset over both snapshot datasets.
_EMPTY_COLUMNS: Final[tuple[str, ...]] = (
    "event_time",
    "available_at",
    "symbol",
    VENUE_COLUMN,
    "open",
    "high",
    "low",
    "close",
    "funding_rate",
)

DEFAULT_BUCKET_TIMEFRAME: Final[str] = "15m"

# Funding cadence documentation: Binance USDM settles funding on the 8h UTC
# grid (00:00 / 08:00 / 16:00); some symbols settle on a denser 4h or 1h
# cadence. Coverage is judged against the 8h slot grid, so denser-cadence
# symbols pass without special casing; any slot without a settlement is a
# failure (>1x cadence hole), consistent with detect_gaps (>= 2x flags).
FUNDING_CADENCE_NOTE: Final[str] = (
    "funding coverage is judged on the 8h UTC slot grid; symbols with the "
    "documented denser 4h/1h cadence still satisfy slot membership, and any "
    "slot without a settlement (>2x-cadence gap) fails"
)

# All gates recorded into quality_checks: the five frozen required keys plus
# funding_coverage (also surfaced as the dedicated manifest field).
GATE_KEYS: Final[tuple[str, ...]] = (
    "closed_bars_only",
    "no_interior_gaps",
    "no_duplicates",
    "no_synthetic_mix",
    "resample_buckets_complete",
    "funding_coverage",
)

GATE_LABELS: Final[dict[str, str]] = {
    "closed_bars_only": "存在未闭合K线(未来可见)",
    "no_interior_gaps": "存在内部缺口",
    "no_duplicates": "存在重复记录",
    "no_synthetic_mix": "混入合成/非binance数据",
    "resample_buckets_complete": "重采样桶不完整",
    "funding_coverage": "资金费率覆盖不足",
}
_DATASET_LABELS: Final[dict[str, str]] = {"klines_1m": "1m K线", "funding": "资金费率"}
_OVERALL_LABELS: Final[dict[str, str]] = {"valid": "有效", "invalid": "无效"}


def _day_floor(ms: int) -> int:
    """Floor an epoch-ms timestamp to the start of its UTC day."""
    return (ms // DAY_MS) * DAY_MS


def _day_ceil(ms: int) -> int:
    """Ceil an epoch-ms timestamp to the next UTC day unless already aligned."""
    return ((ms + DAY_MS - 1) // DAY_MS) * DAY_MS


def _fmt_ms(ms: int) -> str:
    """Format epoch-ms as a UTC 'YYYY-MM-DD HH:MM' string."""
    return datetime.fromtimestamp(ms / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M")


def _load_rows(
    symbol: str,
    dataset: DatasetName,
    *,
    base_path: Path,
    span_start: int,
    span_end: int,
) -> pd.DataFrame:
    """Load one symbol/dataset's rows inside the gated span, sorted by event_time.

    Rows outside ``[span_start, span_end)`` are excluded. When the venue column
    is absent (funding has none by schema) it is filled with the declared
    ``"binance"`` venue so the synthetic-mix gate sees a uniform column.
    """
    rows = load(
        symbol,
        base_path=base_path,
        timeframe="1m",
        dataset=dataset,
        since=span_start,
        until=span_end,
    )
    if rows.empty:
        # query.load returns a column-less frame when the store has no files;
        # normalize so the gate helpers always see the canonical columns.
        return pd.DataFrame(columns=list(_EMPTY_COLUMNS))
    if VENUE_COLUMN not in rows.columns:
        rows = rows.assign(**{VENUE_COLUMN: REAL_VENUE})
    return rows.sort_values("event_time", kind="stable").reset_index(drop=True)


def _check_closed_bars(rows: pd.DataFrame, *, span_end: int) -> bool:
    """No future visibility: each bar must close no later than the next bar opens.

    Full deterministic scan of every consecutive boundary pair; the final bar
    must be closed by ``span_end`` (the window's exclusive end acts as its
    next boundary). Vacuously true for an empty frame (coverage gates fail).
    """
    times = [int(value) for value in rows["event_time"]]
    available_at = [int(value) for value in rows["available_at"]]
    for i in range(len(times) - 1):
        if available_at[i] > times[i + 1]:
            return False
    return not times or available_at[-1] <= span_end


def _check_interior_gaps(
    symbol: str,
    dataset: str,
    *,
    base_path: Path,
    span_start: int,
    span_end: int,
    rows: pd.DataFrame,
) -> bool:
    """No missing interval inside the span (reuses detect_gaps) + head/tail span.

    A store with no rows in the span fails here, so missing data can never
    pass silently (禁止缺失检查默认通过).
    """
    interval_ms = DATASET_INTERVAL_MS[dataset]
    if rows.empty:
        return False
    for gap_start, gap_end in detect_gaps(symbol, dataset, base_path=base_path):
        if gap_end >= span_start and gap_start < span_end:
            return False
    first = int(rows["event_time"].iloc[0])
    last = int(rows["event_time"].iloc[-1])
    return first <= span_start and last >= span_end - interval_ms


def _check_no_duplicates(rows: pd.DataFrame) -> bool:
    """Every event_time must be unique (per symbol/dataset frame)."""
    times = [int(value) for value in rows["event_time"]]
    return len(times) == len(set(times))


def _check_no_synthetic_mix(rows: pd.DataFrame) -> bool:
    """The venue column must be all 'binance' (funding counts as declared source)."""
    return all(str(value) == REAL_VENUE for value in rows[VENUE_COLUMN])


def _check_resample_buckets(
    rows: pd.DataFrame,
    *,
    span_start: int,
    span_end: int,
    bucket_ms: int,
    bucket_bars: int,
) -> bool:
    """Every bucket in the span (warmup included) must hold exactly all its bars."""
    if rows.empty:
        return False
    counts: dict[int, int] = {}
    for value in rows["event_time"]:
        bucket = (int(value) // bucket_ms) * bucket_ms
        counts[bucket] = counts.get(bucket, 0) + 1
    bucket = span_start
    while bucket < span_end:
        if counts.get(bucket, 0) != bucket_bars:
            return False
        bucket += bucket_ms
    return True


def _check_funding_coverage(rows: pd.DataFrame, *, span_start: int, span_end: int) -> bool:
    """Every 8h UTC slot in the span must contain at least one settlement.

    See ``FUNDING_CADENCE_NOTE``: denser 4h/1h cadence symbols satisfy slot
    membership; a missing settlement (the only way a slot is empty) matches
    detect_gaps' >= 2x-interval failure semantics. Also enforces span reach:
    head and tail slots must be settled, so a missing tail fails.
    """
    if rows.empty:
        return False
    times = sorted(int(value) for value in rows["event_time"])
    cursor = 0
    slot = span_start
    while slot < span_end:
        while cursor < len(times) and times[cursor] < slot:
            cursor += 1
        if cursor >= len(times) or times[cursor] >= slot + FUNDING_INTERVAL_MS:
            return False
        slot += FUNDING_INTERVAL_MS
    return True


# Replay-relevant value columns bound into the content hash, per dataset.
# klines: the OHLC decision path; funding: the rate that drives cost. venue /
# available_at are deliberately excluded — they have dedicated gates.
_HASH_VALUE_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "klines_1m": ("open", "high", "low", "close"),
    "funding": ("funding_rate",),
}


def _content_hash(canonical_rows: list[tuple[int | str, ...]]) -> str:
    """SHA-256 over the canonical serialization of value-bearing rows.

    Algorithm: each row is ``(event_time, symbol, *repr()-serialized values)``
    (values: open/high/low/close for klines_1m, funding_rate for funding);
    sort rows ascending; serialize each as ``","``-joined fields; join with
    ``"\\n"`` (no trailing newline); UTF-8 encode; sha256 hexdigest. Layout
    independent: row content decides, never file/partition structure.
    """
    canonical = "\n".join(",".join(str(part) for part in row) for row in sorted(canonical_rows))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _canonical_rows(
    frames: list[pd.DataFrame], dataset: DatasetName
) -> list[tuple[int | str, ...]]:
    """Extract canonical hash rows (identity + values) from already-loaded frames."""
    columns = ("event_time", "symbol", *_HASH_VALUE_COLUMNS[dataset])
    canonical_rows: list[tuple[int | str, ...]] = []
    for frame in frames:
        for record in zip(*(frame[column] for column in columns), strict=True):
            row: list[int | str] = [int(record[0]), str(record[1])]
            row.extend(repr(float(value)) for value in record[2:])
            canonical_rows.append(tuple(row))
    return canonical_rows


def _collect_canonical_rows(
    symbols: list[str],
    dataset: DatasetName,
    *,
    base_path: Path,
    span_start: int,
    span_end: int,
) -> list[tuple[int | str, ...]]:
    """Gather the dataset's canonical rows across symbols from the store."""
    return _canonical_rows(
        [
            _load_rows(
                symbol, dataset, base_path=base_path, span_start=span_start, span_end=span_end
            )
            for symbol in symbols
        ],
        dataset,
    )


def _dataset_venue(venues: set[str]) -> str:
    """Collapse row-level venues into the DatasetManifest venue value."""
    if not venues:
        return REAL_VENUE
    if SYNTHETIC_VENUE in venues:
        return SYNTHETIC_VENUE
    if len(venues) == 1:
        return next(iter(venues))
    return MIXED_VENUE


def _snapshot_id(
    *,
    window_start_ms: int,
    window_end_ms: int,
    warmup_start_ms: int,
    symbols: list[str],
    datasets: list[DatasetManifest],
) -> str:
    """Short content-addressed id: window + symbols + dataset content hashes."""
    parts = [
        str(window_start_ms),
        str(window_end_ms),
        str(warmup_start_ms),
        ",".join(sorted(symbols)),
        *(
            f"{dataset.name}:{dataset.content_sha256}"
            for dataset in sorted(datasets, key=lambda d: d.name)
        ),
    ]
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return f"snap-{digest[:16]}"


def build_snapshot(
    plan: DataReadinessPlan,
    *,
    base_path: Path,
    window_start_ms: int | None = None,
    window_end_ms: int | None = None,
    warmup_start_ms: int | None = None,
    bucket_timeframe: str = DEFAULT_BUCKET_TIMEFRAME,
    mock_available_at: bool = True,
) -> DataSnapshotManifest:
    """Run the quality gates over the store and bind a DataSnapshotManifest.

    Args:
        plan: The P06 readiness plan providing the symbols and default window
            bounds (its gates having already driven repair). The plan's status
            is advisory here: the snapshot gates independently re-validate the
            store, so post-plan drift still yields an invalid snapshot.
        base_path: Base directory of the parquet store.
        window_start_ms: Evaluation window start override (epoch-ms).
        window_end_ms: Evaluation window end override (epoch-ms, exclusive).
        warmup_start_ms: Warmup start override (epoch-ms).
        bucket_timeframe: Resample timeframe for bucket completeness
            (default "15m": every bucket must hold all fifteen 1m bars).
        mock_available_at: True (default) marks knowable-time semantics as
            historically simulated rather than live ingested (spec:
            时间可知性必须显式).

    Returns:
        The manifest; ``overall_status`` is constructed as ``"valid"`` and the
        frozen contract coerces it to ``"invalid"`` when any gate fails or any
        synthetic row is present.

    Raises:
        ValueError: On invalid timeframe, inverted window, warmup after window
            start, span not aligned to the bucket grid, or an empty plan.
    """
    if bucket_timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(
            f"Invalid bucket_timeframe: {bucket_timeframe}. Valid: {sorted(TIMEFRAME_MINUTES)}"
        )
    effective_start = plan.window_start_ms if window_start_ms is None else window_start_ms
    effective_end = plan.window_end_ms if window_end_ms is None else window_end_ms
    effective_warmup = plan.warmup_start_ms if warmup_start_ms is None else warmup_start_ms
    if effective_end <= effective_start:
        raise ValueError("window_end_ms must be after window_start_ms")
    if effective_warmup > effective_start:
        raise ValueError("warmup_start_ms must not be after window_start_ms")

    symbols = list(dict.fromkeys(entry.symbol for entry in plan.entries))
    if not symbols:
        raise ValueError("plan has no entries; cannot determine snapshot symbols")
    if plan.overall_status != "ready":
        log.warning("snapshot.plan_not_ready", overall_status=plan.overall_status)

    # Gated span: target window including warmup, aligned to complete UTC days
    # (same bounds P06's repair targets), so a repaired store passes cleanly.
    span_start = _day_floor(effective_warmup)
    span_end = _day_ceil(effective_end)
    bucket_ms = TIMEFRAME_MINUTES[bucket_timeframe] * MINUTE_MS
    if span_start % bucket_ms != 0 or span_end % bucket_ms != 0:
        raise ValueError(
            "gated span must be aligned to the bucket grid; use UTC-day-aligned bounds"
        )

    gate_failures: dict[str, list[str]] = {gate: [] for gate in GATE_KEYS}
    loaded: dict[tuple[str, DatasetName], pd.DataFrame] = {}

    def _record(gate: str, where: str, ok: bool) -> None:
        if not ok:
            gate_failures[gate].append(where)

    for symbol in symbols:
        for dataset in SNAPSHOT_DATASETS:
            where = f"{symbol}/{dataset}"
            # Load once; the same frames feed the dataset manifest below.
            rows = loaded[(symbol, dataset)] = _load_rows(
                symbol, dataset, base_path=base_path, span_start=span_start, span_end=span_end
            )
            _record(
                "no_interior_gaps",
                where,
                _check_interior_gaps(
                    symbol,
                    dataset,
                    base_path=base_path,
                    span_start=span_start,
                    span_end=span_end,
                    rows=rows,
                ),
            )
            _record("no_duplicates", where, _check_no_duplicates(rows))
            _record("no_synthetic_mix", where, _check_no_synthetic_mix(rows))
            if dataset == "klines_1m":
                _record("closed_bars_only", where, _check_closed_bars(rows, span_end=span_end))
                _record(
                    "resample_buckets_complete",
                    where,
                    _check_resample_buckets(
                        rows,
                        span_start=span_start,
                        span_end=span_end,
                        bucket_ms=bucket_ms,
                        bucket_bars=TIMEFRAME_MINUTES[bucket_timeframe],
                    ),
                )
            else:
                _record(
                    "funding_coverage",
                    where,
                    _check_funding_coverage(rows, span_start=span_start, span_end=span_end),
                )

    datasets: list[DatasetManifest] = []
    for dataset in SNAPSHOT_DATASETS:
        frames = [loaded[(symbol, dataset)] for symbol in symbols]
        canonical_rows = _canonical_rows(frames, dataset)
        venues = {str(value) for frame in frames for value in frame[VENUE_COLUMN]}
        if dataset == "klines_1m":
            coverage_ok = (
                not gate_failures["no_interior_gaps"]
                and not gate_failures["resample_buckets_complete"]
            )
        else:
            coverage_ok = not gate_failures["funding_coverage"]
        datasets.append(
            DatasetManifest(
                name=dataset,
                venue=_dataset_venue(venues),
                source=SNAPSHOT_SOURCE,
                row_count=len(canonical_rows),
                content_sha256=_content_hash(canonical_rows),
                coverage_ok=coverage_ok,
            )
        )

    quality_checks = {gate: not gate_failures[gate] for gate in GATE_KEYS}
    manifest = DataSnapshotManifest(
        snapshot_id=_snapshot_id(
            window_start_ms=effective_start,
            window_end_ms=effective_end,
            warmup_start_ms=effective_warmup,
            symbols=symbols,
            datasets=datasets,
        ),
        symbols=symbols,
        interval="1m",
        window_start_ms=effective_start,
        window_end_ms=effective_end,
        warmup_start_ms=effective_warmup,
        datasets=datasets,
        funding_coverage=quality_checks["funding_coverage"],
        quality_checks=quality_checks,
        frozen_at=int(time.time() * 1000),
        mock_available_at=mock_available_at,
        # One-vote-veto lives in the frozen contract: constructing with
        # "valid" lets validation coerce to "invalid" on any taint.
        overall_status="valid",
    )
    log.info(
        "snapshot.built",
        snapshot_id=manifest.snapshot_id,
        overall_status=manifest.overall_status,
        failed_gates={g: wheres for g, wheres in gate_failures.items() if wheres},
        funding_cadence_note=FUNDING_CADENCE_NOTE,
    )
    return manifest


def freeze_snapshot(manifest: DataSnapshotManifest, *, snapshots_dir: Path) -> Path:
    """Atomically write the manifest to ``<snapshots_dir>/<snapshot_id>.json``.

    Temp-file-plus-replace keeps the frozen file always complete. Because the
    id is content-addressed, re-freezing an identical snapshot rewrites the
    same file (快照复用 is the logged, expected path — never a silent data
    cutoff move).
    """
    snapshots_dir.mkdir(parents=True, exist_ok=True)
    final = snapshots_dir / f"{manifest.snapshot_id}.json"
    reused = final.exists()
    tmp = final.with_suffix(".json.tmp")
    try:
        tmp.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        os.replace(tmp, final)
    except Exception:
        if tmp.exists():
            tmp.unlink()
        raise
    log.info(
        "snapshot.reused" if reused else "snapshot.frozen",
        snapshot_id=manifest.snapshot_id,
        path=str(final),
    )
    return final


def load_snapshot(path: Path) -> DataSnapshotManifest:
    """Load a frozen snapshot manifest from its JSON file."""
    return DataSnapshotManifest.model_validate_json(path.read_text(encoding="utf-8"))


def verify_snapshot_frozen(path: Path, *, base_path: Path) -> bool:
    """Recompute content hashes from the store and compare with the frozen file.

    Returns False on any content hash or row-count mismatch, and also on an
    unreadable (tampered/corrupt) JSON body — a snapshot that cannot be parsed
    cannot be trusted. A missing file raises ``FileNotFoundError``.
    """
    try:
        manifest = load_snapshot(path)
    except ValidationError:
        log.warning("snapshot.verify_unreadable", path=str(path))
        return False
    span_start = _day_floor(manifest.warmup_start_ms)
    span_end = _day_ceil(manifest.window_end_ms)
    for dataset in manifest.datasets:
        canonical_rows = _collect_canonical_rows(
            manifest.symbols,
            dataset.name,
            base_path=base_path,
            span_start=span_start,
            span_end=span_end,
        )
        if (
            len(canonical_rows) != dataset.row_count
            or _content_hash(canonical_rows) != dataset.content_sha256
        ):
            log.warning(
                "snapshot.verify_mismatch",
                path=str(path),
                dataset=dataset.name,
            )
            return False
    return True


def _iter_dataset_lines(manifest: DataSnapshotManifest) -> Iterator[str]:
    """One PM-readable line per dataset (Chinese)."""
    for dataset in manifest.datasets:
        label = _DATASET_LABELS.get(dataset.name, dataset.name)
        coverage = "完整" if dataset.coverage_ok else "不完整"
        yield (
            f"  {label}[{dataset.name}]: venue={dataset.venue} | {dataset.row_count} 条"
            f" | 哈希 {dataset.content_sha256[:12]} | 覆盖{coverage}"
            f" | 来源 {dataset.source}"
        )


def render_snapshot_report(manifest: DataSnapshotManifest) -> str:
    """Render a PM-readable Chinese snapshot report (one line per dataset)."""
    days = (manifest.window_end_ms - manifest.window_start_ms) // DAY_MS
    knowability = "历史模拟(mock)" if manifest.mock_available_at else "实盘抓取"
    lines = [
        "数据快照清单",
        f"快照ID: {manifest.snapshot_id}",
        f"总体状态: {_OVERALL_LABELS[manifest.overall_status]}",
        (
            f"目标窗口: {_fmt_ms(manifest.window_start_ms)} ~ "
            f"{_fmt_ms(manifest.window_end_ms)} UTC({days} 个完整 UTC 日,"
            f" 预热自 {_fmt_ms(manifest.warmup_start_ms)})"
        ),
        f"币种: {'、'.join(manifest.symbols)} | 可知时间: {knowability}",
        *_iter_dataset_lines(manifest),
    ]
    synthetic = [d.name for d in manifest.datasets if d.venue == SYNTHETIC_VENUE]
    if synthetic:
        lines.append("检测到合成数据(整快照判无效): " + "、".join(synthetic))
    failed = sorted(gate for gate, ok in manifest.quality_checks.items() if not ok)
    if failed:
        reason = "、".join(f"{GATE_LABELS.get(gate, gate)}[{gate}]" for gate in failed)
        lines.append(f"质量门未通过: {reason}")
    else:
        lines.append("质量门: 全部通过")
    return "\n".join(lines)
