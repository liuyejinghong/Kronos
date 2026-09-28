import { GitBranch, Target } from "lucide-react";

/**
 * 当前策略摘要数据。P16 起由会话状态（SessionDetail.current_revision）填充；
 * 既有必填字段保持不变，新增字段全部可选。
 */
export type StrategySummary = {
  strategyName: string;
  symbol: string;
  timeframe: string;
  revisionLabel: string;
  summaryZh?: string;
  /** 例如「倍数 1 · ATR 14」（来自 params）。 */
  paramsZh?: string;
  /** 完整修订 id（revision id 链）。 */
  revisionId?: string;
  /** 修订链深度：根修订为 1，每派生一次 +1。 */
  chainDepth?: number;
};

export type StrategySummaryCardProps = {
  summary: StrategySummary | null;
};

/**
 * 首页「当前策略摘要」位。summary 为空时展示空状态提示，不发任何请求。
 */
export function StrategySummaryCard({ summary }: StrategySummaryCardProps) {
  if (!summary) {
    return (
      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
          <Target className="h-4 w-4" />
          当前策略摘要
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          还没有当前策略。完成首次研究后，这里会显示策略名称、交易对、周期和当前修订。
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <Target className="h-4 w-4 text-teal-700" />
          {summary.strategyName}
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600">
            {summary.symbol}
          </span>
          <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600">
            {summary.timeframe}
          </span>
          {summary.paramsZh ? (
            <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600">
              {summary.paramsZh}
            </span>
          ) : null}
          {typeof summary.chainDepth === "number" ? (
            <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-slate-600">
              <GitBranch className="h-3 w-3" />
              第 {summary.chainDepth} 代修订
            </span>
          ) : null}
          <span
            className="rounded border border-teal-100 bg-teal-50 px-2 py-0.5 font-semibold text-teal-800"
            title={summary.revisionId}
          >
            {summary.revisionLabel}
          </span>
        </div>
      </div>
      {summary.revisionId ? (
        <p className="mt-2 break-all font-mono text-[11px] leading-5 text-slate-400">
          revision {summary.revisionId}
        </p>
      ) : null}
      {summary.summaryZh ? (
        <p className="mt-1 break-words text-sm leading-6 text-slate-600">{summary.summaryZh}</p>
      ) : null}
    </section>
  );
}

/** 从会话的当前修订（StrategySpec JSON）推导摘要卡片数据。 */
export function summaryFromRevision(spec: {
  variant_label_zh: string;
  symbols: string[];
  signal_timeframe: string;
  params: { atr_period: number; volatility_multiplier: number };
  strategy_revision_id: string;
}): StrategySummary {
  return {
    strategyName: spec.variant_label_zh,
    symbol: spec.symbols.join(" / "),
    timeframe: spec.signal_timeframe,
    revisionLabel: `修订 ${shortRevisionId(spec.strategy_revision_id)}`,
    paramsZh: `倍数 ${formatSpecNumber(spec.params.volatility_multiplier)} · ATR ${spec.params.atr_period}`,
    revisionId: spec.strategy_revision_id,
    chainDepth: spec.strategy_revision_id.split("-").length,
  };
}

/** 修订 id 链可能很长：摘要 chip 只显示末段，完整 id 放在 title/副行。 */
export function shortRevisionId(revisionId: string): string {
  const parts = revisionId.split("-");
  return parts.length > 0 ? (parts[parts.length - 1] ?? revisionId) : revisionId;
}

/** 与服务端 ``{value:g}`` 一致的紧凑数字格式（1.0 → 1，2.5 → 2.5）。 */
export function formatSpecNumber(value: number): string {
  return String(value);
}
