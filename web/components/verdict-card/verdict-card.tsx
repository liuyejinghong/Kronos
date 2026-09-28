"use client";

/**
 * 结论卡（P17）。首屏固定回答四件事：当前结论 / 最重要证据 / 最大限制 / 下一步；
 * 展开后是全量证据：指标表、基准比较、时间与币种切片、邻域表、保留集、压力情景、
 * 原因码与产物引用。所有数字与文案来自 card-projection 的确定性投影：
 * null 指标永远显示原因，绝不显示 0；insufficient/invalid 显示「拒判说明」面板。
 */

import {
  AlertTriangle,
  ChevronDown,
  ClipboardList,
  FileBox,
  Lock,
  Scale,
  ShieldQuestionMark,
} from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import type { VerdictJson } from "@/lib/api-verdicts";
import { cn } from "@/lib/utils";

import {
  projectVerdictCard,
  type BadgeTone,
  type BadgeVm,
  type VerdictCardPreviewVm,
  type VerdictCardViewModel,
} from "./card-projection";

const TONE_CLASSES: Record<BadgeTone, string> = {
  green: "border-emerald-200 bg-emerald-50 text-emerald-800",
  blue: "border-blue-200 bg-blue-50 text-blue-700",
  amber: "border-amber-200 bg-amber-50 text-amber-800",
  red: "border-red-200 bg-red-50 text-red-700",
  grey: "border-slate-200 bg-slate-100 text-slate-600",
};

function Badge({ badge, className }: { badge: BadgeVm; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded border px-2 py-0.5 text-xs font-semibold",
        TONE_CLASSES[badge.tone],
        className,
      )}
    >
      {badge.labelZh}
    </span>
  );
}

function SectionCard({
  title,
  children,
  warn = false,
}: {
  title: string;
  children: ReactNode;
  warn?: boolean;
}) {
  return (
    <section
      className={cn(
        "rounded-lg border p-3",
        warn ? "border-amber-300 bg-amber-50/60" : "border-slate-200 bg-white",
      )}
    >
      <h4
        className={cn(
          "flex items-center gap-1.5 text-xs font-semibold",
          warn ? "text-amber-800" : "text-slate-600",
        )}
      >
        {warn ? <AlertTriangle className="h-3.5 w-3.5" /> : null}
        {title}
      </h4>
      <div className="mt-2">{children}</div>
    </section>
  );
}

function MetricTable({ rows, tradeCountDisplay }: { rows: VerdictCardViewModel["metricsRows"]; tradeCountDisplay?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[420px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th className="py-1.5 pr-3 font-medium">指标</th>
            <th className="py-1.5 pr-3 font-medium">值（单位）</th>
            <th className="py-1.5 font-medium">说明</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key} className="border-b border-slate-100 last:border-0">
              <td className="py-1.5 pr-3 font-medium text-slate-800">{row.labelZh}</td>
              <td
                className={cn(
                  "py-1.5 pr-3 font-mono",
                  row.isNull ? "text-slate-500" : "text-slate-950",
                )}
              >
                {row.display}
              </td>
              <td className="py-1.5 text-xs text-slate-500">{row.unitLabel}</td>
            </tr>
          ))}
          {tradeCountDisplay !== undefined ? (
            <tr className="border-b border-slate-100 last:border-0">
              <td className="py-1.5 pr-3 font-medium text-slate-800">闭合交易数</td>
              <td className="py-1.5 pr-3 font-mono text-slate-950">{tradeCountDisplay}</td>
              <td className="py-1.5 text-xs text-slate-500">闭合往返交易口径</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function SliceTable({ title, slices }: { title: string; slices: VerdictCardViewModel["timeSlices"] }) {
  if (slices.length === 0) {
    return null;
  }
  return (
    <SectionCard title={title}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[380px] border-collapse text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 text-xs text-slate-500">
              <th className="py-1.5 pr-3 font-medium">切片</th>
              <th className="py-1.5 pr-3 font-medium">样本K线数</th>
              <th className="py-1.5 font-medium">闭合交易数</th>
            </tr>
          </thead>
          <tbody>
            {slices.map((slice) => (
              <tr key={slice.rule_id} className="border-b border-slate-100 last:border-0">
                <td className="py-1.5 pr-3 text-slate-800">
                  {slice.label}
                  <span className="ml-2 font-mono text-xs text-slate-400">{slice.rule_id}</span>
                </td>
                <td className="py-1.5 pr-3 font-mono text-slate-950">{slice.sample_bars}</td>
                <td className="py-1.5 font-mono text-slate-950">{slice.trade_count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </SectionCard>
  );
}

function MetaLine({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex min-w-0 flex-wrap items-baseline gap-x-2">
      <span className="text-xs text-slate-500">{label}</span>
      <span className={cn("min-w-0 break-all text-xs text-slate-800", mono && "font-mono")}>
        {value}
      </span>
    </div>
  );
}

/**
 * Input union: a full wire verdict (history/compare paths), the compact
 * first-screen preview produced by buildVerdictCardPreview (the P15/P16
 * VerdictCardAreaProps contract), or null (empty state). Detection is
 * structural: only full verdicts carry `schema_version`.
 */
export type VerdictCardInput = VerdictJson | VerdictCardPreviewVm | null;

function isFullVerdict(verdict: VerdictCardInput): verdict is VerdictJson {
  return verdict !== null && "schema_version" in verdict && "metrics" in verdict;
}

export type VerdictCardProps = {
  verdict: VerdictCardInput;
  defaultExpanded?: boolean;
};

export function VerdictCard({ verdict, defaultExpanded = false }: VerdictCardProps) {
  if (verdict === null) {
    return (
      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
          <ClipboardList className="h-4 w-4" />
          研究结论
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          还没有研究结论。启动一次研究后，结论卡会显示结论、最重要证据、最大限制和下一步。
        </p>
      </section>
    );
  }
  if (!isFullVerdict(verdict)) {
    // Compact contract (components/conversation/verdict-card-area.tsx):
    // render the first screen (四件事) from the four prepared strings.
    return (
      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <ClipboardList className="h-4 w-4 text-teal-700" />
          研究结论
        </div>
        <dl className="mt-3 grid gap-3">
          {(
            [
              { label: "结论", value: verdict.conclusionZh },
              { label: "最重要证据", value: verdict.keyEvidenceZh },
              { label: "最大限制", value: verdict.mainLimitationZh },
              { label: "下一步", value: verdict.nextStepZh },
            ] as const
          ).map((row) => (
            <div key={row.label}>
              <dt className="text-xs font-medium text-slate-500">{row.label}</dt>
              <dd className="mt-1 break-words text-sm leading-6 text-slate-800">{row.value}</dd>
            </div>
          ))}
        </dl>
      </section>
    );
  }
  return <FullVerdictCard verdict={verdict} defaultExpanded={defaultExpanded} />;
}

function FullVerdictCard({
  verdict,
  defaultExpanded,
}: {
  verdict: VerdictJson;
  defaultExpanded: boolean;
}) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const vm = projectVerdictCard(verdict);

  return (
    <section className="rounded-lg border border-slate-200 bg-white" data-testid="verdict-card">
      <div className="flex flex-wrap items-center gap-2 border-b border-slate-100 px-4 py-3">
        <ClipboardList className="h-4 w-4 text-teal-700" />
        <h3 className="text-sm font-semibold text-slate-950">研究结论</h3>
        <Badge badge={vm.evidenceBadge} />
        {vm.dispositionBadge ? (
          <Badge badge={vm.dispositionBadge} />
        ) : (
          <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-slate-100 px-2 py-0.5 text-xs font-semibold text-slate-600">
            <ShieldQuestionMark className="h-3 w-3" />
            暂不判断
          </span>
        )}
        <span className="ml-auto font-mono text-xs text-slate-400">{vm.meta.runId}</span>
      </div>

      {vm.refusal ? (
        <div className="border-b border-slate-100 bg-slate-50 px-4 py-3">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-slate-800">
            <AlertTriangle className="h-4 w-4 text-amber-600" />
            {vm.refusal.titleZh}
          </div>
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm leading-6 text-slate-600">
            {vm.refusal.blockersZh.map((blocker) => (
              <li key={blocker}>{blocker}</li>
            ))}
          </ul>
        </div>
      ) : null}

      <div className="grid gap-4 px-4 py-4 md:grid-cols-2">
        <div className="md:col-span-2">
          <div className="text-xs font-medium text-slate-500">当前结论</div>
          <p className="mt-1 break-words text-sm leading-6 text-slate-900">{vm.summaryText}</p>
        </div>
        <div className="md:col-span-2">
          <div className="text-xs font-medium text-slate-500">最重要证据</div>
          <p className="mt-1 break-words text-sm leading-6 text-slate-900">{vm.keyEvidenceText}</p>
        </div>
        <div>
          <div className="text-xs font-medium text-slate-500">最大限制（前 3 条）</div>
          <ul className="mt-1 list-inside list-disc space-y-1 text-sm leading-6 text-slate-900">
            {vm.mainLimitations.length > 0 ? (
              vm.mainLimitations.map((limitation) => (
                <li key={limitation} className="break-words">
                  {limitation}
                </li>
              ))
            ) : (
              <li>（无已记录限制）</li>
            )}
          </ul>
        </div>
        <div>
          <div className="text-xs font-medium text-slate-500">下一步</div>
          <ul className="mt-1 list-inside list-decimal space-y-1 text-sm leading-6 text-slate-900">
            {vm.nextSteps.length > 0 ? (
              vm.nextSteps.map((step) => (
                <li key={`${step.kind}:${step.detail}`} className="break-words">
                  <span className="font-semibold">【{step.kindLabelZh}】</span>
                  {step.detail}
                </li>
              ))
            ) : (
              <li>（无建议的后续动作）</li>
            )}
          </ul>
        </div>
      </div>

      {vm.reasonChips.length > 0 ? (
        <div className="flex flex-wrap items-center gap-1.5 px-4 pb-3">
          <span className="text-xs text-slate-500">原因码：</span>
          {vm.reasonChips.map((chip) => (
            <span
              className={cn(
                "rounded border px-1.5 py-0.5 font-mono text-xs",
                chip.known
                  ? "border-slate-200 bg-slate-50 text-slate-700"
                  : "border-dashed border-amber-300 bg-amber-50 text-amber-700",
              )}
              key={chip.code}
              title={chip.code}
            >
              {chip.code}
            </span>
          ))}
        </div>
      ) : null}

      <div className="px-4 pb-3">
        <button
          className="inline-flex items-center gap-1 rounded border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
          onClick={() => setExpanded((previous) => !previous)}
          type="button"
        >
          <ChevronDown
            className={cn("h-3.5 w-3.5 transition-transform", expanded && "rotate-180")}
          />
          {expanded ? "收起全量证据" : "展开全量证据（指标/基准/切片/邻域/产物）"}
        </button>
      </div>

      {expanded ? (
        <div className="grid gap-3 border-t border-slate-100 bg-slate-50/60 px-4 py-4">
          <SectionCard title="运行元信息">
            <div className="grid gap-1.5">
              <MetaLine label="run_id" value={vm.meta.runId} mono />
              {vm.meta.parentRunId ? (
                <MetaLine label="parent_run_id" value={vm.meta.parentRunId} mono />
              ) : null}
              <MetaLine label="策略修订" value={vm.meta.strategyRevisionId} mono />
              <MetaLine label="spec_hash" value={vm.meta.specHash} mono />
              <MetaLine label="数据快照" value={vm.meta.snapshotId} mono />
              <MetaLine label="引擎版本" value={vm.meta.engineVersion} mono />
              <MetaLine label="政策版本" value={vm.meta.policyVersion} mono />
              <MetaLine label="生成时间" value={vm.meta.generatedAtText} />
            </div>
          </SectionCard>

          <SectionCard title="全量指标（闭合交易口径）">
            <MetricTable rows={vm.metricsRows} tradeCountDisplay={vm.tradeCountDisplay} />
            {vm.sampleWarning ? (
              <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-amber-700">
                <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                {vm.sampleWarning}
              </p>
            ) : null}
          </SectionCard>

          {vm.comparisons.map((comparison) => (
            <SectionCard
              key={comparison.baseline}
              title={`基准比较：${comparison.baselineLabelZh}`}
            >
              <MetricTable
                rows={comparison.rows}
                tradeCountDisplay={comparison.tradeCountDisplay}
              />
              <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-slate-500">
                <Scale className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                口径说明（含资金费率与否以此为准）：{comparison.note}
              </p>
            </SectionCard>
          ))}

          <SliceTable slices={vm.timeSlices} title="时间切片（滞后信息，仅供参照）" />
          <SliceTable slices={vm.symbolSlices} title="币种切片" />

          {vm.neighborhood === null &&
          vm.holdout === null &&
          vm.timeSlices.length === 0 &&
          vm.symbolSlices.length === 0 &&
          vm.stress.length === 0 ? (
            <SectionCard title="证据切片 / 邻域 / 保留集 / 压力情景">
              <p className="text-xs leading-5 text-slate-500">
                这些证据块位于 evidence 产物（artifact_refs.evidence）内，verdict 接口未内联；
                接入证据产物后在此展开展示。
              </p>
            </SectionCard>
          ) : null}

          {vm.neighborhood ? (
            <SectionCard title="邻域参数表" warn={vm.neighborhood.hasInactiveParams}>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[460px] border-collapse text-left text-sm">
                  <thead>
                    <tr className="border-b border-slate-200 text-xs text-slate-500">
                      <th className="py-1.5 pr-3 font-medium">atr_period</th>
                      <th className="py-1.5 pr-3 font-medium">volatility_multiplier</th>
                      <th className="py-1.5 pr-3 font-medium">改变交易</th>
                      <th className="py-1.5 pr-3 font-medium">参数生效</th>
                      <th className="py-1.5 font-medium">净盈亏</th>
                    </tr>
                  </thead>
                  <tbody>
                    {vm.neighborhood.rows.map((row) => (
                      <tr
                        key={`${row.atrPeriod}:${row.volatilityMultiplier}`}
                        className="border-b border-slate-100 last:border-0"
                      >
                        <td className="py-1.5 pr-3 font-mono text-slate-950">{row.atrPeriod}</td>
                        <td className="py-1.5 pr-3 font-mono text-slate-950">
                          {row.volatilityMultiplier}
                        </td>
                        <td className="py-1.5 pr-3 text-slate-800">
                          {row.tradesChanged ? "是" : "否"}
                        </td>
                        <td className="py-1.5 pr-3 text-slate-800">
                          {row.paramActivated ? "是" : "否（未进入决策路径）"}
                        </td>
                        <td className="py-1.5 font-mono text-slate-950">{row.netPnlDisplay}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {vm.neighborhood.pseudoRobustNote ? (
                <p className="mt-2 flex items-start gap-1.5 text-xs leading-5 text-amber-700">
                  <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  伪稳健提示：{vm.neighborhood.pseudoRobustNote}
                </p>
              ) : null}
            </SectionCard>
          ) : null}

          {vm.holdout ? (
            <SectionCard title="开发 / 保留集划分" warn={vm.holdout.exposedWarning}>
              <div className="grid gap-1.5">
                <MetaLine label="开发窗口" value={vm.holdout.devWindow} />
                <MetaLine label="保留窗口" value={vm.holdout.holdoutWindow} />
                <MetaLine label="保留集暴露次数" value={String(vm.holdout.exposedCount)} />
              </div>
              {vm.holdout.exposedWarning ? (
                <p className="mt-2 text-xs leading-5 text-amber-700">
                  保留集已被查看并继续调参（{vm.holdout.exposedCount}{" "}
                  次）：保留窗口数字已被污染，只对开发窗口可信，不能当作样本外证据。
                </p>
              ) : (
                <p className="mt-2 text-xs leading-5 text-slate-500">
                  保留集未被暴露：保留窗口数字仍可作为样本外参照。
                </p>
              )}
            </SectionCard>
          ) : null}

          {vm.stress.length > 0 ? (
            <SectionCard title="压力情景">
              <ul className="space-y-1 text-sm leading-6 text-slate-800">
                {vm.stress.map((run) => (
                  <li key={`${run.kindLabelZh}:${run.description}`}>
                    <span className="font-semibold">{run.kindLabelZh}</span>：{run.description}
                  </li>
                ))}
              </ul>
            </SectionCard>
          ) : null}

          {vm.artifactRefs.length > 0 ? (
            <SectionCard title="产物引用（artifact_refs）">
              <ul className="grid gap-1">
                {vm.artifactRefs.map((ref) => (
                  <li className="flex min-w-0 flex-wrap items-baseline gap-x-2" key={ref.key}>
                    <span className="text-xs font-semibold text-slate-600">{ref.key}</span>
                    <span className="min-w-0 break-all font-mono text-xs text-slate-500">
                      {ref.path}
                    </span>
                  </li>
                ))}
              </ul>
              <p className="mt-2 flex items-center gap-1.5 text-xs text-slate-400">
                <FileBox className="h-3.5 w-3.5" />
                逐字段溯源以 artifact 内路径为准；本卡不重算任何指标。
              </p>
            </SectionCard>
          ) : null}
        </div>
      ) : null}

      <div className="flex items-center gap-1.5 border-t border-slate-100 px-4 py-2.5 text-xs text-slate-500">
        <Lock className="h-3.5 w-3.5 shrink-0" />
        {vm.authorityFooterZh}
      </div>
    </section>
  );
}
