import { Target } from "lucide-react";

/** 当前策略摘要数据。P16/P17 接入真实数据时填充。 */
export type StrategySummary = {
  strategyName: string;
  symbol: string;
  timeframe: string;
  revisionLabel: string;
  summaryZh?: string;
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
          <span className="rounded border border-teal-100 bg-teal-50 px-2 py-0.5 font-semibold text-teal-800">
            {summary.revisionLabel}
          </span>
        </div>
      </div>
      {summary.summaryZh ? (
        <p className="mt-2 break-words text-sm leading-6 text-slate-600">{summary.summaryZh}</p>
      ) : null}
    </section>
  );
}
