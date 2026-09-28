/**
 * Pure projection: StrategyVerdict JSON -> verdict-card view model (P17).
 *
 * No React, no I/O, no runtime imports — this module is executed both by the
 * Next bundle and directly by `node --test` (type stripping), so it must stay
 * dependency-free and use erasable-only TypeScript. It is deterministic: the
 * same verdict JSON always projects to the same view model (verified by test).
 *
 * Hard rules encoded here (specs/verdict-card + policy.py):
 * - Every null MetricValue renders its null reason, NEVER 0 (zero-denominator
 *   metrics are "null + reason" in the contract).
 * - insufficient/invalid verdicts get a dedicated refusal panel (拒判说明)
 *   listing the blockers instead of a disposition.
 * - A neighborhood grid point with param_activated=false must surface the
 *   pseudo-robustness note and must never read as robustness evidence.
 * - execution_authority is always "none": the fixed footer text grants no
 *   trading permission of any kind.
 */

import type {
  ComparisonBaselineJson,
  ComparisonJson,
  EvidenceStatusJson,
  MetricValueJson,
  MetricsBlockJson,
  NeighborhoodBlockJson,
  NextActionJson,
  NextActionKindJson,
  SliceJson,
  StressKindJson,
  StressRunJson,
  VerdictJson,
} from "@/lib/api-verdicts";

// --------------------------------------------------------------- labels

export type BadgeTone = "green" | "blue" | "amber" | "red" | "grey";

export type BadgeVm = {
  code: string;
  labelZh: string;
  tone: BadgeTone;
};

export const EVIDENCE_STATUS_BADGES: Record<EvidenceStatusJson, BadgeVm> = {
  valid: { code: "valid", labelZh: "有效", tone: "green" },
  limited: { code: "limited", labelZh: "受限", tone: "amber" },
  insufficient: { code: "insufficient", labelZh: "证据不足", tone: "grey" },
  invalid: { code: "invalid", labelZh: "无效", tone: "red" },
};

export const DISPOSITION_BADGES: Record<"observe" | "redesign" | "retire_current_revision", BadgeVm> =
  {
    observe: { code: "observe", labelZh: "观察", tone: "blue" },
    redesign: { code: "redesign", labelZh: "改造", tone: "amber" },
    retire_current_revision: {
      code: "retire_current_revision",
      labelZh: "放弃当前修订",
      tone: "red",
    },
  };

/** Disposition null = refuse to judge (暂不判断), rendered as a grey badge. */
export const REFUSED_DISPOSITION_BADGE: BadgeVm = {
  code: "null",
  labelZh: "暂不判断",
  tone: "grey",
};

const REASON_CODE_LABELS: Record<string, string> = {
  snapshot_invalid: "快照无效",
  insufficient_zero_trades: "零笔闭合交易",
  insufficient_null_core_metrics: "核心指标不可算",
  below_min_trades: "低于最低样本线",
  param_not_activated: "参数未生效",
  cost_flip_under_stress: "成本压力翻负",
  neighborhood_inconsistent: "邻域不一致",
  underperform_both_baselines: "双基准跑输",
  max_drawdown_exceeds_policy_flag: "回撤超阈值",
};

/** Full blocker sentences used by the 拒判说明 panel, keyed by reason code. */
const REASON_CODE_BLOCKERS: Record<string, string> = {
  snapshot_invalid:
    "数据快照未通过质量门槛（来源、完整性或质量检查失败），本卡所有数值不能作为判断依据。",
  insufficient_zero_trades:
    "评估窗口内没有任何闭合交易：不能由 0 胜率推导失败，也不能由无亏损推导稳健。",
  insufficient_null_core_metrics:
    "净收益、最大回撤、胜率或盈亏比等核心指标不可计算（零分母），系统拒绝判断。",
  below_min_trades:
    "闭合交易数低于预先冻结的工程警戒线（默认 30 笔），仅提示样本不足，不自动无效。",
  param_not_activated:
    "邻域中存在从未进入决策路径的参数点：其交易结构不变不能当作稳健证据。",
  cost_flip_under_stress: "成本上浮压力情景下净收益由正转负：当前边际扛不住更高成本。",
  neighborhood_inconsistent: "激活的邻域点中多数改变了交易结构：参数敏感，结果不稳健。",
  underperform_both_baselines: "净收益同时低于「持有同币种」与「空仓」两个基准。",
  max_drawdown_exceeds_policy_flag: "最大回撤超过政策标记线（仅提示，不单独决定处置）。",
};

const NULL_REASON_LABELS: Record<string, string> = {
  all_ties: "全部交易打平",
  benchmark_out_of_scope: "基准指标归基准比较表",
  zero_denominator: "分母为零",
  no_closed_trades: "没有闭合交易",
  no_position: "空仓无可评估交易",
  single_position_rule: "单一持仓规则下该指标不适用",
};

const NEXT_ACTION_KIND_LABELS: Record<NextActionKindJson, string> = {
  adjust_param: "调整参数",
  add_filter: "增加过滤条件",
  switch_symbol: "更换币种",
  switch_timeframe: "更换周期",
  collect_more_data: "补充数据",
  drop_revision: "放弃当前修订",
};

const STRESS_KIND_LABELS: Record<StressKindJson, string> = {
  cost_up: "成本上浮压力",
  delay: "延迟压力",
};

const BASELINE_LABELS: Record<ComparisonBaselineJson, string> = {
  hold_same_symbol: "持有同币种基准（不交易）",
  cash: "空仓基准（持有现金）",
};

export const AUTHORITY_FOOTER_ZH =
  "无任何交易权限：本结论不授予任何下单、模拟盘或实盘许可，观察也不是交易许可。";

// ------------------------------------------------------------- metric rows

export type MetricUnit = "percent" | "ratio" | "bars" | "quote";

type MetricSpec = { key: string; labelZh: string; unit: MetricUnit };

const METRIC_SPECS: MetricSpec[] = [
  { key: "net_return", labelZh: "净收益", unit: "percent" },
  { key: "benchmark_return", labelZh: "基准收益", unit: "percent" },
  { key: "excess_return", labelZh: "超额收益", unit: "percent" },
  { key: "max_drawdown", labelZh: "最大回撤", unit: "percent" },
  { key: "win_rate", labelZh: "胜率", unit: "percent" },
  { key: "profit_factor", labelZh: "盈亏比", unit: "ratio" },
  { key: "avg_hold_bars", labelZh: "平均持仓", unit: "bars" },
  { key: "avg_win", labelZh: "平均盈利", unit: "quote" },
  { key: "avg_loss", labelZh: "平均亏损", unit: "quote" },
];

const UNIT_LABELS: Record<MetricUnit, string> = {
  percent: "%（占比，闭合交易口径）",
  ratio: "×（比值）",
  bars: "根K线",
  quote: "计价货币",
};

export type MetricRow = {
  key: string;
  labelZh: string;
  unitLabel: string;
  display: string;
  isNull: boolean;
};

function formatNumber(value: number, digits: number): string {
  const normalized = Object.is(value, -0) ? 0 : value;
  return normalized.toFixed(digits);
}

function formatMetricValue(metric: MetricValueJson, unit: MetricUnit): string {
  if (metric.value === null) {
    const known = metric.reason !== null ? NULL_REASON_LABELS[metric.reason] : undefined;
    const reasonZh = known ?? metric.reason ?? "未给出原因";
    return `不可算（${reasonZh}）`;
  }
  switch (unit) {
    case "percent":
      return `${formatNumber(metric.value * 100, 2)}%`;
    case "ratio":
      return `${formatNumber(metric.value, 2)}×`;
    case "bars":
      return `${formatNumber(metric.value, 1)} 根K线`;
    case "quote":
      return `${formatNumber(metric.value, 2)} 计价货币`;
  }
}

function metricRows(metrics: MetricsBlockJson): MetricRow[] {
  return METRIC_SPECS.map((spec) => {
    const metric = metrics[spec.key as keyof MetricsBlockJson] as MetricValueJson;
    const isNull = metric.value === null;
    return {
      key: spec.key,
      labelZh: spec.labelZh,
      unitLabel: UNIT_LABELS[spec.unit],
      display: formatMetricValue(metric, spec.unit),
      isNull,
    };
  });
}

function tradeCountDisplay(tradeCount: number): string {
  return `${tradeCount} 笔`;
}

// --------------------------------------------------------- card projection

export type ComparisonVm = {
  baseline: ComparisonBaselineJson;
  baselineLabelZh: string;
  note: string;
  rows: MetricRow[];
  tradeCountDisplay: string;
};

export type NeighborhoodRowVm = {
  atrPeriod: number;
  volatilityMultiplier: number;
  tradesChanged: boolean;
  paramActivated: boolean;
  netPnlDisplay: string;
};

export type NeighborhoodVm = {
  rows: NeighborhoodRowVm[];
  pseudoRobustNote: string | null;
  hasInactiveParams: boolean;
};

export type HoldoutVm = {
  devWindow: string;
  holdoutWindow: string;
  exposedCount: number;
  exposedWarning: boolean;
};

export type NextStepVm = {
  kind: NextActionKindJson;
  kindLabelZh: string;
  detail: string;
};

export type ReasonChipVm = {
  code: string;
  labelZh: string;
  known: boolean;
};

export type RefusalVm = {
  titleZh: string;
  blockersZh: string[];
};

export type VerdictCardViewModel = {
  meta: {
    runId: string;
    parentRunId: string | null;
    strategyRevisionId: string;
    specHash: string;
    snapshotId: string;
    engineVersion: string;
    policyVersion: string;
    generatedAtText: string;
  };
  evidenceBadge: BadgeVm;
  dispositionBadge: BadgeVm | null;
  summaryText: string;
  keyEvidenceText: string;
  mainLimitations: string[];
  nextSteps: NextStepVm[];
  metricsRows: MetricRow[];
  tradeCountDisplay: string;
  sampleWarning: string | null;
  comparisons: ComparisonVm[];
  /** Evidence sections: null when the caller has no joined evidence bundle. */
  timeSlices: SliceJson[];
  symbolSlices: SliceJson[];
  neighborhood: NeighborhoodVm | null;
  holdout: HoldoutVm | null;
  stress: Array<{ kindLabelZh: string; description: string }>;
  reasonChips: ReasonChipVm[];
  artifactRefs: Array<{ key: string; path: string }>;
  refusal: RefusalVm | null;
  authorityFooterZh: string;
};

function formatGeneratedAt(generatedAt: number): string {
  // Deterministic UTC text (no locale, no timezone dependence).
  return `${new Date(generatedAt).toISOString().replace("T", " ").slice(0, 16)} UTC`;
}

function findComparison(
  comparisons: ComparisonJson[],
  baseline: ComparisonBaselineJson,
): ComparisonJson | null {
  return comparisons.find((comparison) => comparison.baseline === baseline) ?? null;
}

function shortMetricInline(metric: MetricValueJson, unit: MetricUnit): string {
  return formatMetricValue(metric, unit);
}

function buildSummaryText(verdict: VerdictJson): string {
  const net = verdict.metrics.net_return;
  const excess = verdict.metrics.excess_return;
  const trades = tradeCountDisplay(verdict.metrics.trade_count);
  const netText = shortMetricInline(net, "percent");
  const excessText = shortMetricInline(excess, "percent");
  const tail = `净收益 ${netText}，超额收益 ${excessText}（${trades}）`;
  if (verdict.evidence_status === "invalid") {
    return `证据无效：数据快照未通过门槛，系统拒绝判断；阻塞项与已有产物见下方说明。${tail}仅供核查，不可用于决策。`;
  }
  if (verdict.evidence_status === "insufficient") {
    if (verdict.reason_codes.includes("insufficient_zero_trades")) {
      return `证据不足：本窗口没有闭合交易，系统拒绝判断；不能由 0 胜率推导失败，也不能由无亏损推导稳健。`;
    }
    return `证据不足：核心指标不可计算，系统拒绝判断；阻塞项见拒判说明。`;
  }
  if (verdict.disposition === null) {
    return "系统拒绝判断（处置为空）：阻塞项见拒判说明。";
  }
  if (verdict.disposition === "observe") {
    return `证据${EVIDENCE_STATUS_BADGES[verdict.evidence_status].labelZh}，建议观察：${tail}。`;
  }
  if (verdict.disposition === "redesign") {
    const redesignReasons = [
      "cost_flip_under_stress",
      "neighborhood_inconsistent",
      "param_not_activated",
    ];
    const topReasonCode = redesignReasons.find((code) => verdict.reason_codes.includes(code));
    const reasonText = topReasonCode
      ? (REASON_CODE_LABELS[topReasonCode] ?? topReasonCode)
      : "存在可验证的弱点";
    return `证据${EVIDENCE_STATUS_BADGES[verdict.evidence_status].labelZh}，建议改造（${reasonText}）：${tail}。`;
  }
  return `证据有效但净收益同时低于持有与空仓基准，建议放弃当前修订：${tail}。`;
}

function buildKeyEvidenceText(verdict: VerdictJson): string {
  const comparison =
    findComparison(verdict.comparisons, "hold_same_symbol") ??
    findComparison(verdict.comparisons, "cash") ??
    verdict.comparisons[0];
  if (!comparison) {
    return "本结论没有基准比较数据。";
  }
  const baselineZh = BASELINE_LABELS[comparison.baseline];
  const own = verdict.metrics;
  const base = comparison.metrics;
  return (
    `对${baselineZh}：策略净收益 ${shortMetricInline(own.net_return, "percent")} vs ` +
    `基准 ${shortMetricInline(base.net_return, "percent")}，超额 ` +
    `${shortMetricInline(own.excess_return, "percent")}；` +
    `${tradeCountDisplay(own.trade_count)}；` +
    `胜率 ${shortMetricInline(own.win_rate, "percent")}，` +
    `盈亏比 ${shortMetricInline(own.profit_factor, "ratio")}。` +
    `口径：${comparison.note}`
  );
}

function projectNeighborhood(neighborhood: NeighborhoodBlockJson): NeighborhoodVm {
  const rows = neighborhood.grid.map((point) => ({
    atrPeriod: point.atr_period,
    volatilityMultiplier: point.volatility_multiplier,
    tradesChanged: point.trades_changed,
    paramActivated: point.param_activated,
    netPnlDisplay:
      point.net_pnl === null ? "未记录" : `${formatNumber(point.net_pnl, 2)} 计价货币`,
  }));
  const hasInactiveParams = neighborhood.grid.some((point) => !point.param_activated);
  return {
    rows,
    pseudoRobustNote: neighborhood.pseudo_robust_note,
    hasInactiveParams,
  };
}

function buildRefusal(verdict: VerdictJson): RefusalVm | null {
  if (verdict.evidence_status !== "insufficient" && verdict.evidence_status !== "invalid") {
    return null;
  }
  const blockersZh = verdict.reason_codes.map((code) => {
    const known = REASON_CODE_BLOCKERS[code];
    return known ?? `未识别的阻塞原因码：${code}`;
  });
  if (blockersZh.length === 0) {
    blockersZh.push("系统拒绝判断，但未给出具体原因码；请核查证据产物。");
  }
  return {
    titleZh: "拒判说明：证据不足以支撑研究处置（disposition 为空）",
    blockersZh,
  };
}

export function projectVerdictCard(verdict: VerdictJson): VerdictCardViewModel {
  return {
    meta: {
      runId: verdict.run_id,
      parentRunId: verdict.parent_run_id,
      strategyRevisionId: verdict.strategy_revision_id,
      specHash: verdict.spec_hash,
      snapshotId: verdict.snapshot_id,
      engineVersion: verdict.engine_version,
      policyVersion: verdict.policy_version,
      generatedAtText: formatGeneratedAt(verdict.generated_at),
    },
    evidenceBadge: EVIDENCE_STATUS_BADGES[verdict.evidence_status],
    dispositionBadge:
      verdict.disposition === null ? null : DISPOSITION_BADGES[verdict.disposition],
    summaryText: buildSummaryText(verdict),
    keyEvidenceText: buildKeyEvidenceText(verdict),
    mainLimitations: verdict.limitations.slice(0, 3),
    nextSteps: verdict.next_actions.map((action: NextActionJson) => ({
      kind: action.kind,
      kindLabelZh: NEXT_ACTION_KIND_LABELS[action.kind] ?? action.kind,
      detail: action.detail,
    })),
    metricsRows: metricRows(verdict.metrics),
    tradeCountDisplay: tradeCountDisplay(verdict.metrics.trade_count),
    sampleWarning: verdict.metrics.sample_warning,
    comparisons: verdict.comparisons.map((comparison) => ({
      baseline: comparison.baseline,
      baselineLabelZh: BASELINE_LABELS[comparison.baseline] ?? comparison.baseline,
      note: comparison.note,
      rows: metricRows(comparison.metrics),
      tradeCountDisplay: tradeCountDisplay(comparison.metrics.trade_count),
    })),
    timeSlices: verdict.time_slices ?? [],
    symbolSlices: verdict.symbol_slices ?? [],
    neighborhood: verdict.neighborhood ? projectNeighborhood(verdict.neighborhood) : null,
    holdout: verdict.holdout
      ? {
          devWindow: verdict.holdout.dev_window,
          holdoutWindow: verdict.holdout.holdout_window,
          exposedCount: verdict.holdout.exposed_count,
          exposedWarning: verdict.holdout.exposed || verdict.holdout.exposed_count > 0,
        }
      : null,
    stress: (verdict.stress ?? []).map((run: StressRunJson) => ({
      kindLabelZh: STRESS_KIND_LABELS[run.kind] ?? run.kind,
      description: run.description,
    })),
    reasonChips: verdict.reason_codes.map((code) => ({
      code,
      labelZh: REASON_CODE_LABELS[code] ?? code,
      known: code in REASON_CODE_LABELS,
    })),
    artifactRefs: Object.entries(verdict.artifact_refs)
      .map(([key, path]) => ({ key, path }))
      .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0)),
    refusal: buildRefusal(verdict),
    authorityFooterZh: AUTHORITY_FOOTER_ZH,
  };
}

// ------------------------------------------- first-screen preview (P15 shim)

export type VerdictCardPreviewVm = {
  conclusionZh: string;
  keyEvidenceZh: string;
  mainLimitationZh: string;
  nextStepZh: string;
};

/**
 * Projects the first screen (四件事) into the shape consumed by
 * components/conversation/verdict-card-area.tsx (VerdictCardPreview).
 */
export function buildVerdictCardPreview(verdict: VerdictJson): VerdictCardPreviewVm {
  const card = projectVerdictCard(verdict);
  const firstStep = card.nextSteps[0];
  return {
    conclusionZh: card.summaryText,
    keyEvidenceZh: card.keyEvidenceText,
    mainLimitationZh: card.mainLimitations[0] ?? "（无已记录限制）",
    nextStepZh: firstStep
      ? `【${firstStep.kindLabelZh}】${firstStep.detail}`
      : "（无建议的后续动作）",
  };
}

// ------------------------------------------------------- comparison (同快照比较)

export type CompareCellVm = {
  display: string;
  isNull: boolean;
  raw: number | null;
};

export type CompareRowVm = {
  key: string;
  labelZh: string;
  a: CompareCellVm;
  b: CompareCellVm;
  deltaDisplay: string | null;
};

export type VerdictComparisonViewModel = {
  sides: Array<{ runId: string; labelZh: string }>;
  rows: CompareRowVm[];
  paramDiff: { specHashA: string; specHashB: string; same: boolean; summaryZh: string };
  contextDiff: Array<{ labelZh: string; same: boolean }>;
};

function metricCell(metric: MetricValueJson, unit: MetricUnit): CompareCellVm {
  return {
    display: formatMetricValue(metric, unit),
    isNull: metric.value === null,
    raw: metric.value,
  };
}

function deltaText(a: number, b: number, unit: MetricUnit): string | null {
  const diff = a - b;
  if (unit === "percent") {
    const pp = diff * 100;
    return `${pp >= 0 ? "+" : ""}${formatNumber(pp, 2)}pp`;
  }
  if (unit === "ratio") {
    return `${diff >= 0 ? "+" : ""}${formatNumber(diff, 2)}×`;
  }
  if (unit === "quote") {
    return `${diff >= 0 ? "+" : ""}${formatNumber(diff, 2)}`;
  }
  return `${diff >= 0 ? "+" : ""}${formatNumber(diff, 1)}`;
}

export function projectVerdictComparison(
  a: VerdictJson,
  b: VerdictJson,
): VerdictComparisonViewModel {
  const specs: Array<{ key: string; labelZh: string; unit: MetricUnit }> = [
    { key: "net_return", labelZh: "净收益", unit: "percent" },
    { key: "excess_return", labelZh: "超额收益", unit: "percent" },
    { key: "win_rate", labelZh: "胜率", unit: "percent" },
    { key: "max_drawdown", labelZh: "最大回撤", unit: "percent" },
    { key: "profit_factor", labelZh: "盈亏比", unit: "ratio" },
  ];
  const rows: CompareRowVm[] = specs.map((spec) => {
    const metricA = a.metrics[spec.key as keyof MetricsBlockJson] as MetricValueJson;
    const metricB = b.metrics[spec.key as keyof MetricsBlockJson] as MetricValueJson;
    const cellA = metricCell(metricA, spec.unit);
    const cellB = metricCell(metricB, spec.unit);
    const delta =
      cellA.raw !== null && cellB.raw !== null ? deltaText(cellA.raw, cellB.raw, spec.unit) : null;
    return { key: spec.key, labelZh: spec.labelZh, a: cellA, b: cellB, deltaDisplay: delta };
  });
  rows.push({
    key: "trade_count",
    labelZh: "闭合交易数",
    a: { display: tradeCountDisplay(a.metrics.trade_count), isNull: false, raw: a.metrics.trade_count },
    b: { display: tradeCountDisplay(b.metrics.trade_count), isNull: false, raw: b.metrics.trade_count },
    deltaDisplay: deltaText(a.metrics.trade_count, b.metrics.trade_count, "bars"),
  });

  const sameSpec = a.spec_hash === b.spec_hash;
  return {
    sides: [
      { runId: a.run_id, labelZh: "结论 A" },
      { runId: b.run_id, labelZh: "结论 B" },
    ],
    rows,
    paramDiff: {
      specHashA: a.spec_hash,
      specHashB: b.spec_hash,
      same: sameSpec,
      summaryZh: sameSpec
        ? "参数定义一致（spec_hash 相同）：差异来自数据窗口或引擎执行。"
        : "参数定义不同（spec_hash 不同）：两次结论来自不同策略修订，指标差异可能来自参数变化。",
    },
    contextDiff: [
      { labelZh: `引擎版本 ${a.engine_version} / ${b.engine_version}`, same: a.engine_version === b.engine_version },
      { labelZh: `政策版本 ${a.policy_version} / ${b.policy_version}`, same: a.policy_version === b.policy_version },
      { labelZh: `数据快照 ${a.snapshot_id} / ${b.snapshot_id}`, same: a.snapshot_id === b.snapshot_id },
    ],
  };
}
