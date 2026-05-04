"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FileText, ShieldAlert, Target, TrendingUp } from "lucide-react";
import type { ReactNode } from "react";

import { kronosApi, type ArtifactRef } from "@/lib/api";
import { compactLabel } from "@/lib/utils";

type RunBriefPanelProps = {
  modelConfigured: boolean;
  onOpenReport: () => void;
  runId: string;
};

export function RunBriefPanel({ modelConfigured, onOpenReport, runId }: RunBriefPanelProps) {
  const briefQuery = useQuery({
    queryKey: ["agent-run-brief", runId],
    queryFn: () => kronosApi.agentRunBrief(runId),
    retry: 1,
  });

  if (briefQuery.isLoading) {
    return (
      <section className="grid min-w-0 gap-3 rounded-lg border border-slate-200 bg-white p-4 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded border border-slate-200 bg-slate-100" />
        ))}
      </section>
    );
  }

  if (briefQuery.isError || !briefQuery.data) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        当前批次还没有可读的 Agent 汇总报告。完成一次 `agent run-once` 后，这里会显示研究目标、结论、证据、下一步和审批状态。
      </section>
    );
  }

  const brief = briefQuery.data;

  return (
    <section className="grid min-w-0 gap-4 rounded-lg border border-slate-200 bg-white p-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(0,0.8fr)]">
      <div className="min-w-0">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <span className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-medium text-slate-600">
            {compactLabel(brief.status)}
          </span>
          <span className="rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            {brief.evidence_count} 个关键证据
          </span>
          <span className="rounded border border-sky-100 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-800">
            {brief.event_count} 条事件
          </span>
          <span
            className={`rounded border px-2.5 py-1 text-xs font-semibold ${
              modelConfigured
                ? "border-teal-100 bg-teal-50 text-teal-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            {modelConfigured ? "模型可用于后续研究" : "本轮非 DeepSeek 实时生成"}
          </span>
        </div>

        <BriefRow icon={<Target className="h-4 w-4" />} label="现在研究什么" text={brief.goal_zh} />
        <BriefRow
          icon={<TrendingUp className="h-4 w-4" />}
          label="Agent 当前结论"
          text={brief.conclusion_zh}
        />
        <BriefRow
          icon={<ArrowRight className="h-4 w-4" />}
          label="下一步"
          text={brief.next_action_zh}
        />
        <BriefRow
          icon={<ShieldAlert className="h-4 w-4" />}
          label="人工审批"
          text={brief.approval_required ? "需要人工审批后继续。" : "本轮不需要人工审批，仍不会进入实盘。"}
        />
      </div>

      <div className="grid min-w-0 gap-3">
        <ReasonBlock title="支持理由" items={brief.support_reasons} />
        <ReasonBlock title="反对理由 / 风险" items={brief.opposition_reasons} fallback={brief.max_risk_zh} />
        <ArtifactBlock
          artifacts={brief.artifact_paths}
          reportPath={brief.report_path}
          onOpenReport={onOpenReport}
        />
      </div>
    </section>
  );
}

function BriefRow({ icon, label, text }: { icon: ReactNode; label: string; text: string }) {
  return (
    <div className="grid grid-cols-[24px_minmax(0,1fr)] gap-2 border-t border-slate-100 py-3 first:border-t-0 first:pt-0">
      <div className="mt-0.5 text-teal-700">{icon}</div>
      <div className="min-w-0">
        <div className="text-xs font-semibold text-slate-500">{label}</div>
        <p className="mt-1 break-words text-sm leading-6 text-slate-800">{text}</p>
      </div>
    </div>
  );
}

function ReasonBlock({
  title,
  items,
  fallback,
}: {
  title: string;
  items: string[];
  fallback?: string | null;
}) {
  const rows = items.length > 0 ? items : fallback ? [fallback] : ["暂无。"];
  return (
    <div className="rounded border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-semibold text-slate-500">{title}</div>
      <ul className="mt-2 grid gap-1.5">
        {rows.map((item) => (
          <li key={item} className="break-words text-sm leading-6 text-slate-700">
            {item}
          </li>
        ))}
      </ul>
    </div>
  );
}

function ArtifactBlock({
  artifacts,
  onOpenReport,
  reportPath,
}: {
  artifacts: ArtifactRef[];
  onOpenReport: () => void;
  reportPath: string | null;
}) {
  return (
    <div className="rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
        <FileText className="h-3.5 w-3.5" />
        报告与证据
      </div>
      <div className="mt-2 grid gap-2">
        {reportPath ? (
          <button
            className="inline-flex h-10 items-center justify-center rounded bg-slate-900 px-3 text-sm font-semibold text-white transition hover:bg-slate-800"
            type="button"
            onClick={onOpenReport}
          >
            阅读本轮报告
          </button>
        ) : (
          <div className="rounded border border-slate-200 bg-white px-3 py-2 text-sm text-slate-500">
            本轮还没有生成可读报告。
          </div>
        )}
        {artifacts.length > 0 ? (
          <details className="rounded border border-slate-200 bg-white p-3 text-xs text-slate-600">
            <summary className="cursor-pointer font-semibold text-slate-700">
              技术附件 {artifacts.length} 个
            </summary>
            <div className="mt-2 grid gap-2">
              {artifacts.slice(0, 4).map((artifact) => (
                <ArtifactPath key={artifact.path} path={artifact.path} label={artifact.artifact_type} />
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

function ArtifactPath({ path, label }: { path: string; label: string }) {
  return (
    <div className="flex min-w-0 items-center gap-2 rounded border border-slate-200 bg-white px-2.5 py-2 text-xs">
      <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">{label}</span>
      <code className="truncate text-slate-700">{path}</code>
    </div>
  );
}
