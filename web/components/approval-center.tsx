"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, CirclePause, ShieldAlert, X } from "lucide-react";

import { kronosApi } from "@/lib/api";
import { compactLabel } from "@/lib/utils";

type ApprovalCenterProps = {
  runId: string;
  taskId: string;
};

const gateLabels = [
  "Prompt 启用",
  "候选实现",
  "模拟盘准入",
  "组合准入",
  "实盘申请",
];

export function ApprovalCenter({ runId, taskId }: ApprovalCenterProps) {
  const queryClient = useQueryClient();
  const approvalsQuery = useQuery({
    queryKey: ["approvals"],
    queryFn: kronosApi.approvals,
  });
  const resolveMutation = useMutation({
    mutationFn: (payload: { approvalId: string; approved: boolean }) =>
      kronosApi.resolveApproval({
        approvalId: payload.approvalId,
        runId,
        taskId,
        approved: payload.approved,
        reasonZh: payload.approved ? "人工批准通过。" : "人工驳回，等待 Agent 改造。",
      }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["approvals"] });
    },
  });

  if (approvalsQuery.isLoading) {
    return <div className="h-36 animate-pulse rounded border border-slate-200 bg-slate-100" />;
  }

  if (approvalsQuery.isError) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        无法读取审批中心。
      </div>
    );
  }

  const approvals = approvalsQuery.data?.items ?? [];

  if (approvals.length === 0) {
    return (
      <div className="grid gap-3">
        <div className="rounded border border-slate-200 bg-slate-50 p-3">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
            <CirclePause className="h-4 w-4 text-amber-700" />
            当前没有待审批项
          </div>
          <p className="mt-1 text-xs leading-5 text-slate-500">
            审批项在 prompt 生效、进入模拟盘或申请实盘时自动生成。当前 Agent 可以继续推进研究和验证。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {gateLabels.map((label) => (
            <span
              key={label}
              className="rounded border border-slate-200 bg-white px-2.5 py-1 text-xs text-slate-600"
            >
              {label}
            </span>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="grid gap-3">
      {approvals.map((approval) => (
        <div key={approval.approval_id} className="rounded border border-amber-200 bg-amber-50 p-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 font-semibold text-amber-950">
                <ShieldAlert className="h-4 w-4 shrink-0" />
                <span className="break-words">{approval.title_zh}</span>
              </div>
              <p className="mt-1 break-words text-sm leading-6 text-amber-900">
                {approval.reason_zh}
              </p>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-amber-800">
                <span>{compactLabel(approval.approval_type)}</span>
                {approval.candidate_id ? <span>候选：{approval.candidate_id}</span> : null}
                <span>{approval.blocking ? "阻塞项" : "非阻塞项"}</span>
              </div>
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                className="inline-flex h-9 items-center gap-1 rounded bg-teal-700 px-3 text-xs font-semibold text-white hover:bg-teal-800"
                type="button"
                onClick={() =>
                  resolveMutation.mutate({ approvalId: approval.approval_id, approved: true })
                }
              >
                <Check className="h-3.5 w-3.5" />
                批准
              </button>
              <button
                className="inline-flex h-9 items-center gap-1 rounded border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 hover:bg-slate-50"
                type="button"
                onClick={() =>
                  resolveMutation.mutate({ approvalId: approval.approval_id, approved: false })
                }
              >
                <X className="h-3.5 w-3.5" />
                驳回
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
