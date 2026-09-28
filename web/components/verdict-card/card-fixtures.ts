/**
 * Typed demo fixtures for the verdict card (P17).
 *
 * Five states cover the acceptance matrix from the P17 task line:
 * valid-observe / limited-redesign / insufficient-zero-trades / invalid /
 * param-not-activated neighborhood. They feed both the `?demo=` mode on the
 * history page and the node:test projection tests.
 *
 * Every fixture must satisfy the frozen P05 contract validators:
 * - MetricValue: exactly one of value / non-empty reason (null is never 0).
 * - NeighborhoodBlock: pseudo_robust_note required when any grid point has
 *   param_activated=false.
 * - execution_authority is always "none".
 */

import type {
  DemoVerdictJson,
  GridPointJson,
  MetricValueJson,
  MetricsBlockJson,
  NeighborhoodBlockJson,
} from "@/lib/api-verdicts";

function metric(value: number): MetricValueJson {
  return { value, reason: null };
}

function nullMetric(reason: string): MetricValueJson {
  return { value: null, reason };
}

const BOUNDARY_LIMITATIONS = [
  "Boundary: testnet and backtest results do not prove live-trading performance.",
  "Boundary: this verdict holds only for the declared sample window of the frozen snapshot; it is not a claim about periods outside that window.",
  "Boundary: results apply only to the Kronos threshold-variant strategy semantics and do not transfer to other strategy families.",
];

function holdComparisonMetrics(): MetricsBlockJson {
  return {
    net_return: metric(0.021),
    benchmark_return: nullMetric("benchmark_out_of_scope"),
    excess_return: nullMetric("benchmark_out_of_scope"),
    max_drawdown: metric(-0.041),
    win_rate: nullMetric("single_position_rule"),
    profit_factor: nullMetric("single_position_rule"),
    trade_count: 1,
    avg_hold_bars: metric(43200),
    avg_win: nullMetric("single_position_rule"),
    avg_loss: nullMetric("single_position_rule"),
    sample_warning: null,
  };
}

function cashComparisonMetrics(): MetricsBlockJson {
  return {
    net_return: metric(0.0),
    benchmark_return: nullMetric("benchmark_out_of_scope"),
    excess_return: nullMetric("benchmark_out_of_scope"),
    max_drawdown: metric(0.0),
    win_rate: nullMetric("no_position"),
    profit_factor: nullMetric("no_position"),
    trade_count: 0,
    avg_hold_bars: nullMetric("no_position"),
    avg_win: nullMetric("no_position"),
    avg_loss: nullMetric("no_position"),
    sample_warning: null,
  };
}

function activatedGrid(): GridPointJson[] {
  return [
    {
      atr_period: 14,
      volatility_multiplier: 2.0,
      trades_changed: false,
      param_activated: true,
      net_pnl: 512.4,
    },
    {
      atr_period: 10,
      volatility_multiplier: 2.0,
      trades_changed: true,
      param_activated: true,
      net_pnl: 388.1,
    },
    {
      atr_period: 20,
      volatility_multiplier: 2.5,
      trades_changed: true,
      param_activated: true,
      net_pnl: 201.9,
    },
    {
      atr_period: 14,
      volatility_multiplier: 1.5,
      trades_changed: false,
      param_activated: true,
      net_pnl: 512.4,
    },
  ];
}

function inactiveGrid(): GridPointJson[] {
  return [
    ...activatedGrid(),
    {
      atr_period: 21,
      volatility_multiplier: 3.0,
      trades_changed: false,
      param_activated: false,
      net_pnl: null,
    },
  ];
}

const ACTIVE_NEIGHBORHOOD: NeighborhoodBlockJson = {
  grid: activatedGrid(),
  pseudo_robust_note: null,
};

const INACTIVE_NEIGHBORHOOD: NeighborhoodBlockJson = {
  grid: inactiveGrid(),
  pseudo_robust_note:
    "Grid point (atr_period=21, volatility_multiplier=3.0) never entered the decision path: " +
    "its unchanged trades must NOT be read as robustness evidence for that parameter.",
};

function baseVerdict(
  overrides: Partial<DemoVerdictJson> & { run_id: string; metrics: MetricsBlockJson },
): DemoVerdictJson {
  return {
    schema_version: 1,
    parent_run_id: null,
    strategy_revision_id: "rev-rbreak-usdm-v3",
    spec_hash: "9d2f6a1b7c4e0583af21dc6b9e07f45a3c8d12e690ab4f7cd35e8216a04b9c7d",
    snapshot_id: "snap-20260801-btcethsol-1m",
    engine_version: "kronos-backtest-0.5.0",
    policy_version: "v0.5.0-p0",
    evidence_status: "valid",
    disposition: "observe",
    reason_codes: [],
    comparisons: [
      {
        baseline: "hold_same_symbol",
        note: "Funding payments are counted: the hold baseline pays/receives funding on its position.",
        metrics: holdComparisonMetrics(),
      },
      {
        baseline: "cash",
        note: "Cash baseline holds no position: no funding is paid or received.",
        metrics: cashComparisonMetrics(),
      },
    ],
    limitations: [...BOUNDARY_LIMITATIONS],
    next_actions: [
      {
        kind: "collect_more_data",
        detail:
          "No disqualifying trigger fired: extend the sample window or re-evaluate on new data before further tuning.",
      },
    ],
    artifact_refs: {
      ledger: "runs/demo-valid-observe/ledger.json",
      evidence: "runs/demo-valid-observe/evidence.json",
      snapshot: "snapshots/snap-20260801-btcethsol-1m/manifest.json",
      manifest: "runs/demo-valid-observe/verdict.json",
    },
    generated_at: 1790553600000,
    execution_authority: "none",
    time_slices: [
      { rule_id: "time:equal_thirds:0", label: "前三分之一", sample_bars: 43200, trade_count: 16 },
      { rule_id: "time:equal_thirds:1", label: "中三分之一", sample_bars: 43200, trade_count: 14 },
      { rule_id: "time:equal_thirds:2", label: "后三分之一", sample_bars: 43200, trade_count: 16 },
    ],
    symbol_slices: [
      { rule_id: "symbol:BTCUSDT", label: "BTCUSDT", sample_bars: 43200, trade_count: 21 },
      { rule_id: "symbol:ETHUSDT", label: "ETHUSDT", sample_bars: 43200, trade_count: 17 },
      { rule_id: "symbol:SOLUSDT", label: "SOLUSDT", sample_bars: 43200, trade_count: 8 },
    ],
    neighborhood: ACTIVE_NEIGHBORHOOD,
    holdout: {
      dev_window: "2026-04-01 .. 2026-07-31 (60%)",
      holdout_window: "2026-08-01 .. 2026-09-15 (30%)",
      exposed_count: 0,
      exposed: false,
    },
    stress: [
      { kind: "cost_up", description: "Fee and slippage doubled versus the base scenario." },
      { kind: "delay", description: "Entry delayed by one closed 1m bar." },
    ],
    ...overrides,
  };
}

/** valid x observe: 46 closed trades, positive excess vs hold, clean neighborhood. */
const VALID_OBSERVE: DemoVerdictJson = baseVerdict({
  run_id: "demo-valid-observe",
  metrics: {
    net_return: metric(0.0832),
    benchmark_return: metric(0.021),
    excess_return: metric(0.0622),
    max_drawdown: metric(-0.094),
    win_rate: metric(0.52),
    profit_factor: metric(1.41),
    trade_count: 46,
    avg_hold_bars: metric(38.6),
    avg_win: metric(96.4),
    avg_loss: metric(-71.2),
    sample_warning: null,
  },
});

/** limited x redesign: below the 30-trade warning line AND net flips under cost_up. */
const LIMITED_REDESIGN: DemoVerdictJson = baseVerdict({
  run_id: "demo-limited-redesign",
  evidence_status: "limited",
  disposition: "redesign",
  reason_codes: ["below_min_trades", "cost_flip_under_stress"],
  metrics: {
    net_return: metric(0.031),
    benchmark_return: metric(0.024),
    excess_return: metric(0.007),
    max_drawdown: metric(-0.121),
    win_rate: metric(0.44),
    profit_factor: metric(1.08),
    trade_count: 18,
    avg_hold_bars: metric(52.3),
    avg_win: metric(84.1),
    avg_loss: metric(-79.6),
    sample_warning: "Only 18 closed trades: below the pre-declared 30-trade engineering line.",
  },
  limitations: [
    ...BOUNDARY_LIMITATIONS,
    "Cost stress flips the net return sign: the current edge does not survive doubled costs.",
  ],
  next_actions: [
    {
      kind: "collect_more_data",
      detail:
        "Closed-trade count is below the pre-declared engineering warning line: collect more data before judging performance.",
    },
    {
      kind: "add_filter",
      detail:
        "Add an entry filter that raises expected per-trade edge so results survive the cost_up stress scenario.",
    },
  ],
  neighborhood: ACTIVE_NEIGHBORHOOD,
  holdout: {
    dev_window: "2026-04-01 .. 2026-07-31 (60%)",
    holdout_window: "2026-08-01 .. 2026-09-15 (30%)",
    exposed_count: 1,
    exposed: true,
  },
});

/** insufficient x null (refuse to judge): zero closed trades, every core metric null. */
const INSUFFICIENT_ZERO_TRADES: DemoVerdictJson = baseVerdict({
  run_id: "demo-insufficient-zero-trades",
  evidence_status: "insufficient",
  disposition: null,
  reason_codes: ["insufficient_zero_trades", "insufficient_null_core_metrics"],
  metrics: {
    net_return: nullMetric("no_closed_trades"),
    benchmark_return: nullMetric("benchmark_out_of_scope"),
    excess_return: nullMetric("no_closed_trades"),
    max_drawdown: nullMetric("no_closed_trades"),
    win_rate: nullMetric("zero_denominator"),
    profit_factor: nullMetric("zero_denominator"),
    trade_count: 0,
    avg_hold_bars: nullMetric("no_closed_trades"),
    avg_win: nullMetric("no_closed_trades"),
    avg_loss: nullMetric("no_closed_trades"),
    sample_warning: "Zero closed trades in the declared window.",
  },
  next_actions: [
    {
      kind: "collect_more_data",
      detail:
        "No closed trades in this window: extend the window or relax entry thresholds so the rule can trade, then re-evaluate.",
    },
    {
      kind: "switch_symbol",
      detail:
        "No trades in any evaluated symbol slice: try a more active or more trending symbol before collecting more data.",
    },
  ],
  neighborhood: {
    grid: activatedGrid().map((point) => ({ ...point, trades_changed: false, net_pnl: null })),
    pseudo_robust_note: null,
  },
});

/** invalid x null (refuse to judge): snapshot failed the one-vote-veto quality gate. */
const INVALID_SNAPSHOT: DemoVerdictJson = baseVerdict({
  run_id: "demo-invalid-snapshot",
  evidence_status: "invalid",
  disposition: null,
  reason_codes: ["snapshot_invalid"],
  metrics: {
    net_return: nullMetric("snapshot_invalid"),
    benchmark_return: nullMetric("snapshot_invalid"),
    excess_return: nullMetric("snapshot_invalid"),
    max_drawdown: nullMetric("snapshot_invalid"),
    win_rate: nullMetric("snapshot_invalid"),
    profit_factor: nullMetric("snapshot_invalid"),
    trade_count: 0,
    avg_hold_bars: nullMetric("snapshot_invalid"),
    avg_win: nullMetric("snapshot_invalid"),
    avg_loss: nullMetric("snapshot_invalid"),
    sample_warning: "Snapshot overall_status=invalid: resample_buckets_complete failed.",
  },
  limitations: [
    ...BOUNDARY_LIMITATIONS,
    "Snapshot quality gate failed (one-vote-veto): all numbers on this card are for audit only.",
  ],
  next_actions: [],
});

/** limited x redesign driven by a param that never activated (pseudo-robust trap). */
const PARAM_NOT_ACTIVATED: DemoVerdictJson = baseVerdict({
  run_id: "demo-param-not-activated",
  evidence_status: "limited",
  disposition: "redesign",
  reason_codes: ["below_min_trades", "param_not_activated"],
  metrics: {
    net_return: metric(0.0415),
    benchmark_return: metric(0.019),
    excess_return: metric(0.0225),
    max_drawdown: metric(-0.102),
    win_rate: metric(0.47),
    profit_factor: metric(1.15),
    trade_count: 24,
    avg_hold_bars: metric(44.0),
    avg_win: metric(90.2),
    avg_loss: metric(-76.8),
    sample_warning: "Only 24 closed trades: below the pre-declared 30-trade engineering line.",
  },
  limitations: [
    ...BOUNDARY_LIMITATIONS,
    "One neighborhood parameter never entered the decision path: robustness to it is unproven.",
  ],
  next_actions: [
    {
      kind: "adjust_param",
      detail:
        "Widen the pre-registered grid so the inactive parameter actually enters the decision path.",
    },
  ],
  neighborhood: INACTIVE_NEIGHBORHOOD,
});

export const CARD_FIXTURES: Record<string, DemoVerdictJson> = {
  "valid-observe": VALID_OBSERVE,
  "limited-redesign": LIMITED_REDESIGN,
  "insufficient-zero-trades": INSUFFICIENT_ZERO_TRADES,
  invalid: INVALID_SNAPSHOT,
  "param-not-activated": PARAM_NOT_ACTIVATED,
};

export const CARD_FIXTURE_KEYS = Object.keys(CARD_FIXTURES);

export function isCardFixtureKey(key: string): boolean {
  return key in CARD_FIXTURES;
}
