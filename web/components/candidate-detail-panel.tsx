"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight, FilePlus2, FileText, GitBranch, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";

import { kronosApi, type CandidateDetail } from "@/lib/api";
import { cn, compactLabel, scoreFromRank } from "@/lib/utils";

const lifecycleSteps = [
  { id: "material_intake", label: "材料进入" },
  { id: "migration_review", label: "迁移审查" },
  { id: "hypothesis", label: "假设" },
  { id: "experiment_planned", label: "实验计划" },
  { id: "validating", label: "验证" },
  { id: "agent_analysis", label: "Agent 分析" },
  { id: "committee_scoring", label: "投委会评分" },
  { id: "simulate", label: "模拟盘" },
  { id: "live_approval_required", label: "实盘审批" },
];

type CandidateDetailPanelProps = {
  candidateId: string | null;
  onAddMaterial?: () => void;
};

export function CandidateDetailPanel({ candidateId, onAddMaterial }: CandidateDetailPanelProps) {
  const detailQuery = useQuery({
    queryKey: ["candidate-detail", candidateId],
    queryFn: () => kronosApi.candidateDetail(candidateId ?? ""),
    enabled: Boolean(candidateId),
  });

  if (!candidateId) {
    return (
      <PanelShell title="候选详情" description="从左侧候选池选择一个策略资产">
        <EmptyState />
      </PanelShell>
    );
  }

  if (detailQuery.isLoading) {
    return (
      <PanelShell title="候选详情" description="正在读取迁移资料">
        <div className="grid gap-3">
          <div className="h-8 animate-pulse rounded bg-slate-100" />
          <div className="h-20 animate-pulse rounded bg-slate-100" />
          <div className="h-28 animate-pulse rounded bg-slate-100" />
        </div>
      </PanelShell>
    );
  }

  if (detailQuery.isError || !detailQuery.data) {
    return (
      <PanelShell title="候选详情" description="读取失败">
        <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
          无法读取该候选策略详情，请确认本地 API 正常运行。
        </div>
      </PanelShell>
    );
  }

  return (
    <PanelShell title="候选详情" description="迁移、验证和准入状态">
      <CandidateDetailContent detail={detailQuery.data} onAddMaterial={onAddMaterial} />
    </PanelShell>
  );
}

function CandidateDetailContent({
  detail,
  onAddMaterial,
}: {
  detail: CandidateDetail;
  onAddMaterial?: () => void;
}) {
  const score = scoreFromRank(detail.migration_rank);
  return (
    <div className="grid gap-5">
      <div className="min-w-0">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <h3 className="break-words text-lg font-semibold text-slate-950">{detail.title_zh}</h3>
            <p className="mt-1 break-words text-xs text-slate-500">{detail.candidate_id}</p>
          </div>
          <span className="rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            {detail.status_label_zh}
          </span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
          <Metric label="迁移优先级" value={`#${detail.migration_rank}`} />
          <Metric label="迁移分" value={`${score}`} />
          <Metric label="研究族群" value={compactLabel(detail.family)} />
          <Metric label="来源" value={compactLabel(detail.origin)} />
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
          <GitBranch className="h-4 w-4 text-teal-700" />
          生命周期
        </div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 xl:grid-cols-3">
          {lifecycleSteps.map((step) => {
            const active = step.id === detail.lifecycle_state;
            return (
              <div
                key={step.id}
                className={cn(
                  "min-h-12 rounded border px-2.5 py-2 text-xs leading-relaxed",
                  active
                    ? "border-teal-300 bg-teal-50 font-semibold text-teal-900"
                    : "border-slate-200 bg-slate-50 text-slate-500",
                )}
              >
                {step.label}
              </div>
            );
          })}
        </div>
      </div>

      <div className="rounded border border-sky-100 bg-sky-50 p-3">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800">
            <ShieldCheck className="h-4 w-4 text-sky-700" />
            下一步判断
          </div>
          {onAddMaterial ? (
            <button
              className="inline-flex h-8 items-center gap-1.5 rounded bg-slate-900 px-2.5 text-xs font-semibold text-white hover:bg-slate-800"
              type="button"
              onClick={onAddMaterial}
            >
              <FilePlus2 className="h-3.5 w-3.5" />
              补材料
            </button>
          ) : null}
        </div>
        <p className="break-words text-sm leading-6 text-slate-700">{detail.next_action_zh}</p>
      </div>

      <div className="grid gap-3">
        <DecisionBlock
          title="验证证据"
          body={
            detail.artifact_paths.length > 0
              ? `已绑定 ${detail.artifact_paths.length} 个证据产物。`
              : "缺少 crypto 市场专项验证报告；下一步应补充材料或让 Agent 为这个候选生成实验计划。"
          }
        />
        <DecisionBlock
          title="Agent 分歧"
          body={`支持侧：旧策略迁移优先级 #${detail.migration_rank}；反对侧：仍需要 crypto 市场专项证据确认。`}
        />
        <DecisionBlock title="投委会结论" body={detail.next_action_zh} />
      </div>

      <div>
        <div className="mb-2 text-sm font-semibold text-slate-800">旧资产来源</div>
        <div className="flex flex-wrap gap-2">
          {detail.source_strategies.map((source) => (
            <span
              key={source}
              className="rounded border border-amber-100 bg-amber-50 px-2.5 py-1 text-xs text-amber-800"
            >
              {source}
            </span>
          ))}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-800">
          <FileText className="h-4 w-4 text-slate-600" />
          证据产物
        </div>
        {detail.artifact_paths.length === 0 ? (
          <div className="rounded border border-slate-200 bg-white p-3 text-sm text-slate-500">
            该候选项暂未绑定专属证据文件；后续 Agent 验证会把报告挂到这里。
          </div>
        ) : (
          <div className="grid gap-2">
            {detail.artifact_paths.map((artifact) => (
              <div key={artifact.path} className="flex min-w-0 items-center gap-2 text-sm">
                <ArrowRight className="h-4 w-4 shrink-0 text-slate-400" />
                <code className="truncate rounded bg-slate-100 px-2 py-1 text-xs">
                  {artifact.path}
                </code>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function PanelShell({
  title,
  description,
  children,
}: {
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <section className="h-full min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">{title}</h2>
        <p className="mt-1 text-xs text-slate-500">{description}</p>
      </div>
      <div className="p-4">{children}</div>
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-900">{value}</div>
    </div>
  );
}

function DecisionBlock({ title, body }: { title: string; body: string }) {
  return (
    <div className="rounded border border-slate-200 bg-white p-3">
      <div className="text-xs font-semibold text-slate-500">{title}</div>
      <p className="mt-1 break-words text-sm leading-6 text-slate-700">{body}</p>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="flex min-h-56 items-center justify-center rounded border border-dashed border-slate-300 bg-slate-50 px-4 text-center text-sm leading-6 text-slate-500">
      选择候选项后，可以查看它来自哪些旧策略、当前处于哪个 Agent 生命周期阶段，以及下一步是否进入实验或模拟盘。
    </div>
  );
}
