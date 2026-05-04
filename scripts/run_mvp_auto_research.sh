#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p logs

export UV_CACHE_DIR="${UV_CACHE_DIR:-$PROJECT_ROOT/.uv-cache}"

KRONOS_CONFIG="${KRONOS_CONFIG:-configs/dev.toml}"
KRONOS_OUTPUT_PATH="${KRONOS_OUTPUT_PATH:-reports/research}"
KRONOS_SYMBOLS="${KRONOS_SYMBOLS:-BTCUSDT,ETHUSDT,SOLUSDT}"
KRONOS_CANDIDATES="${KRONOS_CANDIDATES:-}"
KRONOS_WATCHLIST_CANDIDATES="${KRONOS_WATCHLIST_CANDIDATES:-range_chop_filter,body_energy}"
KRONOS_TIMEFRAME="${KRONOS_TIMEFRAME:-1m}"
KRONOS_PERIODS="${KRONOS_PERIODS:-1,5,20}"
KRONOS_TRAIN_SIZE="${KRONOS_TRAIN_SIZE:-720}"
KRONOS_VALIDATION_SIZE="${KRONOS_VALIDATION_SIZE:-360}"
KRONOS_TEST_SIZE="${KRONOS_TEST_SIZE:-360}"
KRONOS_STEP_SIZE="${KRONOS_STEP_SIZE:-360}"
KRONOS_MIN_HISTORY_DAYS="${KRONOS_MIN_HISTORY_DAYS:-90}"
KRONOS_SYNC_DATA="${KRONOS_SYNC_DATA:-1}"
KRONOS_SYNC_SINCE="${KRONOS_SYNC_SINCE:-}"
KRONOS_RUN_ID="${KRONOS_RUN_ID:-$(date -u +%Y%m%dT%H%M%SZ-mvp-auto-run)}"

args=(
  research auto-run
  --symbols "$KRONOS_SYMBOLS"
  --watchlist-candidates "$KRONOS_WATCHLIST_CANDIDATES"
  --timeframe "$KRONOS_TIMEFRAME"
  --periods "$KRONOS_PERIODS"
  --train-size "$KRONOS_TRAIN_SIZE"
  --validation-size "$KRONOS_VALIDATION_SIZE"
  --test-size "$KRONOS_TEST_SIZE"
  --step-size "$KRONOS_STEP_SIZE"
  --min-history-days "$KRONOS_MIN_HISTORY_DAYS"
  --run-id "$KRONOS_RUN_ID"
  --output-path "$KRONOS_OUTPUT_PATH"
  --config "$KRONOS_CONFIG"
)

if [[ -n "$KRONOS_CANDIDATES" ]]; then
  args+=(--candidates "$KRONOS_CANDIDATES")
fi

if [[ "$KRONOS_SYNC_DATA" == "1" || "$KRONOS_SYNC_DATA" == "true" ]]; then
  args+=(--sync-data)
  if [[ -n "$KRONOS_SYNC_SINCE" ]]; then
    args+=(--sync-since "$KRONOS_SYNC_SINCE")
  fi
fi

uv run kronos "${args[@]}"
