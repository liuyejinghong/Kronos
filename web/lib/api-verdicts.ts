/**
 * Typed client for the verdict API (P17).
 *
 * Endpoint: `GET /api/verdicts/{run_id}` (kronos/web/routes/conversation.py).
 * Casing note: the FastAPI response model (`VerdictResponse`) and the embedded
 * `StrategyVerdict` payload both serialize **snake_case** (pydantic default;
 * no alias generator exists anywhere in kronos/web), so the types below mirror
 * the frozen field names from kronos/research/verdict/contracts.py verbatim
 * instead of the camelCase guess in the package brief.
 *
 * This module contains types only plus one fetch helper; all rendering logic
 * lives in components/verdict-card/card-projection.ts (pure, node-testable).
 */

import { API_BASE } from "@/lib/api";

export type MetricValueJson = {
  value: number | null;
  reason: string | null;
};

export type MetricsBlockJson = {
  net_return: MetricValueJson;
  benchmark_return: MetricValueJson;
  excess_return: MetricValueJson;
  max_drawdown: MetricValueJson;
  win_rate: MetricValueJson;
  profit_factor: MetricValueJson;
  trade_count: number;
  avg_hold_bars: MetricValueJson;
  avg_win: MetricValueJson;
  avg_loss: MetricValueJson;
  sample_warning: string | null;
};

export type ComparisonBaselineJson = "hold_same_symbol" | "cash";

export type ComparisonJson = {
  baseline: ComparisonBaselineJson;
  note: string;
  metrics: MetricsBlockJson;
};

export type SliceJson = {
  rule_id: string;
  label: string;
  sample_bars: number;
  trade_count: number;
};

export type GridPointJson = {
  atr_period: number;
  volatility_multiplier: number;
  trades_changed: boolean;
  param_activated: boolean;
  net_pnl: number | null;
};

export type NeighborhoodBlockJson = {
  grid: GridPointJson[];
  pseudo_robust_note: string | null;
};

export type HoldoutBlockJson = {
  dev_window: string;
  holdout_window: string;
  exposed_count: number;
  exposed: boolean;
};

export type StressKindJson = "cost_up" | "delay";

export type StressRunJson = {
  kind: StressKindJson;
  description: string;
};

export type NextActionKindJson =
  | "adjust_param"
  | "add_filter"
  | "switch_symbol"
  | "switch_timeframe"
  | "collect_more_data"
  | "drop_revision";

export type NextActionJson = {
  kind: NextActionKindJson;
  detail: string;
};

export type EvidenceStatusJson = "valid" | "limited" | "insufficient" | "invalid";

export type DispositionJson = "observe" | "redesign" | "retire_current_revision" | null;

/** Mirror of the frozen StrategyVerdict contract (P05), as serialized by pydantic. */
export type StrategyVerdictJson = {
  schema_version: 1;
  run_id: string;
  parent_run_id: string | null;
  strategy_revision_id: string;
  spec_hash: string;
  snapshot_id: string;
  engine_version: string;
  policy_version: string;
  evidence_status: EvidenceStatusJson;
  disposition: DispositionJson;
  reason_codes: string[];
  metrics: MetricsBlockJson;
  comparisons: ComparisonJson[];
  limitations: string[];
  next_actions: NextActionJson[];
  artifact_refs: Record<string, string>;
  generated_at: number;
  execution_authority: "none";
};

/** `GET /api/verdicts/{run_id}` response body (VerdictResponse in the backend). */
export type VerdictApiResponse = {
  run_id: string;
  state: string;
  verdict: StrategyVerdictJson;
  artifact_refs: Record<string, string>;
};

/**
 * EvidenceBundle-only sections (time/symbol slices, neighborhood, holdout,
 * stress). These are NOT part of StrategyVerdict on the wire — they live in
 * the evidence artifact referenced by `artifact_refs.evidence`. The card
 * renders them when a caller joins them in (demo fixtures do; the API-only
 * path shows an explicit placeholder instead of pretending they exist).
 */
export type EvidenceSectionsJson = {
  time_slices: SliceJson[];
  symbol_slices: SliceJson[];
  neighborhood: NeighborhoodBlockJson;
  holdout: HoldoutBlockJson;
  stress: StressRunJson[];
};

/** Card input: a wire verdict, optionally with joined evidence sections. */
export type VerdictJson = StrategyVerdictJson & Partial<EvidenceSectionsJson>;

/** Demo fixture shape: full verdict plus every evidence section. */
export type DemoVerdictJson = StrategyVerdictJson & EvidenceSectionsJson;

export async function fetchVerdictByRun(
  runId: string,
  init?: { signal?: AbortSignal },
): Promise<VerdictApiResponse> {
  const response = await fetch(`${API_BASE}/verdicts/${encodeURIComponent(runId)}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const detail = await response.text().catch(() => "");
    const trimmed = detail.trim().slice(0, 300);
    throw new Error(
      trimmed.length > 0
        ? `获取结论失败（HTTP ${response.status}）：${trimmed}`
        : `获取结论失败（HTTP ${response.status}）`,
    );
  }
  return (await response.json()) as VerdictApiResponse;
}
