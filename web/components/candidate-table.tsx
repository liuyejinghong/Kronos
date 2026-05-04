"use client";

import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  useReactTable,
} from "@tanstack/react-table";
import { ArrowDownUp, ArrowRight, Database, Layers3 } from "lucide-react";
import { useMemo } from "react";

import type { CandidateListItem } from "@/lib/api";
import { cn, compactLabel, scoreFromRank } from "@/lib/utils";

type CandidateTableProps = {
  candidates: CandidateListItem[];
  selectedCandidateId: string | null;
  onSelectCandidate: (candidateId: string) => void;
  isLoading?: boolean;
};

const columnHelper = createColumnHelper<CandidateListItem>();

export function CandidateTable({
  candidates,
  selectedCandidateId,
  onSelectCandidate,
  isLoading = false,
}: CandidateTableProps) {
  const columns = useMemo(
    () => [
      columnHelper.accessor("migration_rank", {
        header: "优先级",
        cell: (info) => (
          <span className="inline-flex h-7 min-w-8 items-center justify-center rounded border border-slate-200 bg-slate-50 px-2 text-xs font-semibold text-slate-700">
            #{info.getValue()}
          </span>
        ),
      }),
      columnHelper.accessor("title_zh", {
        header: "候选策略 / 因子",
        cell: (info) => {
          const row = info.row.original;
          return (
            <div className="min-w-0">
              <div className="truncate font-medium text-slate-950">{info.getValue()}</div>
              <div className="mt-1 flex min-w-0 items-center gap-1 text-xs text-slate-500">
                <Database className="h-3.5 w-3.5 shrink-0" />
                <span className="truncate">{row.candidate_id}</span>
              </div>
            </div>
          );
        },
      }),
      columnHelper.accessor("family", {
        header: "来源 / 族群",
        cell: (info) => (
          <div className="grid gap-1">
            <span className="inline-flex max-w-full items-center gap-1 rounded border border-sky-100 bg-sky-50 px-2 py-1 text-xs text-sky-800">
              <Layers3 className="h-3.5 w-3.5 shrink-0" />
              <span className="truncate">{compactLabel(info.getValue())}</span>
            </span>
            <span className="truncate text-xs text-slate-500">
              {compactLabel(info.row.original.origin)}
            </span>
          </div>
        ),
      }),
      columnHelper.display({
        id: "decision",
        header: "当前判断",
        cell: (info) => (
          <div className="grid gap-1">
            <span className="inline-flex rounded border border-teal-100 bg-teal-50 px-2 py-1 text-xs font-medium text-teal-800">
              {decisionLabel(info.row.original)}
            </span>
            <span className="text-xs text-slate-500">{info.row.original.status_label_zh}</span>
          </div>
        ),
      }),
      columnHelper.display({
        id: "gap",
        header: "证据缺口",
        cell: (info) => (
          <div className="max-w-[180px] text-xs leading-5 text-slate-600">
            {evidenceGap(info.row.original)}
          </div>
        ),
      }),
      columnHelper.display({
        id: "score",
        header: "迁移分",
        cell: (info) => {
          const score = scoreFromRank(info.row.original.migration_rank);
          return (
            <div className="flex min-w-[92px] items-center gap-2">
              <div className="h-2 w-14 overflow-hidden rounded bg-slate-200">
                <div
                  className="h-full rounded bg-teal-600"
                  style={{ width: `${score}%` }}
                />
              </div>
              <span className="w-7 text-right text-xs tabular-nums text-slate-600">{score}</span>
            </div>
          );
        },
      }),
      columnHelper.display({
        id: "action",
        header: "操作",
        cell: () => (
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-teal-700">
            查看详情
            <ArrowRight className="h-3.5 w-3.5" />
          </span>
        ),
      }),
    ],
    [],
  );

  // TanStack Table intentionally exposes dynamic helpers; this component does not pass them to memoized children.
  // eslint-disable-next-line react-hooks/incompatible-library
  const table = useReactTable({
    data: candidates,
    columns,
    getCoreRowModel: getCoreRowModel(),
  });

  if (isLoading) {
    return (
      <div className="grid gap-2 p-4">
        {Array.from({ length: 5 }).map((_, index) => (
          <div key={index} className="h-12 animate-pulse rounded border border-slate-200 bg-slate-100" />
        ))}
      </div>
    );
  }

  if (candidates.length === 0) {
    return (
      <div className="flex min-h-48 items-center justify-center px-6 text-center text-sm text-slate-500">
        当前还没有进入候选池的策略资产。导入旧策略材料后，这里会显示迁移排序和研究阶段。
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[840px] table-fixed border-separate border-spacing-0 text-left text-sm">
        <thead>
          {table.getHeaderGroups().map((headerGroup) => (
            <tr key={headerGroup.id}>
              {headerGroup.headers.map((header) => (
                <th
                  key={header.id}
                  className="sticky top-0 z-10 border-b border-slate-200 bg-slate-50 px-3 py-3 text-xs font-semibold uppercase tracking-normal text-slate-500"
                >
                  <div className="flex items-center gap-1">
                    {flexRender(header.column.columnDef.header, header.getContext())}
                    {header.column.id === "migration_rank" ? (
                      <ArrowDownUp className="h-3.5 w-3.5 text-slate-400" />
                    ) : null}
                  </div>
                </th>
              ))}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const isSelected = row.original.candidate_id === selectedCandidateId;
            return (
              <tr
                key={row.id}
                className={cn(
                  "border-b border-slate-100 transition-colors hover:bg-slate-50",
                  isSelected && "bg-teal-50/70 hover:bg-teal-50",
                )}
              >
                {row.getVisibleCells().map((cell) => (
                  <td key={cell.id} className="border-b border-slate-100 px-3 py-3 align-middle">
                    <button
                      className="block w-full min-w-0 text-left"
                      type="button"
                      onClick={() => onSelectCandidate(row.original.candidate_id)}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </button>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function decisionLabel(candidate: CandidateListItem) {
  if (candidate.migration_rank <= 3) {
    return "优先验证";
  }
  if (candidate.migration_rank <= 6) {
    return "候选改造";
  }
  return "暂缓观察";
}

function evidenceGap(candidate: CandidateListItem) {
  if (candidate.migration_rank <= 6) {
    return "缺 crypto 专项回测、滚动验证和失败边界。";
  }
  return "先保留旧资产信息，等待更高优先级候选验证后再推进。";
}
