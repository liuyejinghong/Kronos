"use client";

/**
 * 结论详情视图（P17 历史页）。数据源二选一：
 * - `demoKey`：内置演示 verdict（card-fixtures），无需后端；
 * - `runId`：从 GET /api/verdicts/{run_id} 拉取已发布的结论。
 */

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowLeft, FlaskConical } from "lucide-react";
import Link from "next/link";

import {
  CARD_FIXTURES,
  CARD_FIXTURE_KEYS,
  isCardFixtureKey,
} from "@/components/verdict-card/card-fixtures";
import { VerdictCard } from "@/components/verdict-card/verdict-card";
import { fetchVerdictByRun } from "@/lib/api-verdicts";

function BackToListLink() {
  return (
    <Link
      className="inline-flex items-center gap-1 text-sm font-semibold text-slate-600 transition hover:text-slate-900"
      href="/history"
    >
      <ArrowLeft className="h-4 w-4" />
      返回历史与证据
    </Link>
  );
}

export type VerdictDetailViewProps = {
  runId?: string;
  demoKey?: string;
};

export function VerdictDetailView({ runId, demoKey }: VerdictDetailViewProps) {
  const shouldFetch =
    demoKey === undefined && runId !== undefined && runId.trim() !== "";
  const normalizedRunId = shouldFetch && runId !== undefined ? runId.trim() : "";
  // Hooks must run unconditionally: disabled when rendering a demo fixture or
  // an empty reference (TanStack keeps a disabled query idle).
  const query = useQuery({
    enabled: shouldFetch,
    queryKey: ["verdict", normalizedRunId],
    queryFn: () => fetchVerdictByRun(normalizedRunId),
    retry: false,
  });

  if (demoKey !== undefined) {
    if (!isCardFixtureKey(demoKey)) {
      return (
        <div className="grid gap-4">
          <BackToListLink />
          <section className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4">
            <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-800">
              <AlertTriangle className="h-4 w-4" />
              未知演示状态：{demoKey}
            </div>
            <p className="mt-2 text-sm leading-6 text-amber-800">
              可用演示状态：{CARD_FIXTURE_KEYS.join("、")}
            </p>
          </section>
        </div>
      );
    }
    const fixture = CARD_FIXTURES[demoKey];
    return (
      <div className="grid min-w-0 gap-4">
        <BackToListLink />
        <p className="flex items-center gap-1.5 text-xs text-slate-500">
          <FlaskConical className="h-3.5 w-3.5" />
          内置演示数据（?demo={demoKey}），与真实接口字段结构一致，用于走查卡片状态。
        </p>
        <VerdictCard verdict={fixture} />
      </div>
    );
  }

  if (!shouldFetch) {
    return (
      <div className="grid gap-4">
        <BackToListLink />
        <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center">
          <p className="text-sm leading-6 text-slate-500">
            缺少结论引用：请使用 /history?run_id=&lt;run_id&gt; 进入，或从对话中的结论卡进入。
          </p>
        </section>
      </div>
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <BackToListLink />
      {query.isPending ? (
        <section className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
          正在加载结论 {normalizedRunId} …
        </section>
      ) : null}
      {query.isError ? (
        <section className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4">
          <div className="flex items-center gap-1.5 text-sm font-semibold text-amber-800">
            <AlertTriangle className="h-4 w-4" />
            无法读取结论
          </div>
          <p className="mt-2 break-words text-sm leading-6 text-amber-800">
            {query.error instanceof Error ? query.error.message : String(query.error)}
          </p>
          <p className="mt-2 text-sm leading-6 text-amber-700">
            常见原因：该 run 还没有发布结论（回测未完成或失败），或 run_id 不存在。
            结论在对话任务成功发布后才会出现；也可以先看内置演示状态。
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Link
              className="inline-flex h-9 items-center rounded border border-amber-300 bg-white px-3 text-xs font-semibold text-amber-800 transition hover:bg-amber-100"
              href="/"
            >
              去策略对话
            </Link>
            <Link
              className="inline-flex h-9 items-center rounded border border-amber-300 bg-white px-3 text-xs font-semibold text-amber-800 transition hover:bg-amber-100"
              href="/history?demo=valid-observe"
            >
              看演示结论卡
            </Link>
          </div>
        </section>
      ) : null}
      {query.data ? (
        <>
          <p className="text-xs text-slate-500">
            任务状态：<span className="font-mono">{query.data.state}</span>
          </p>
          <VerdictCard verdict={query.data.verdict} />
        </>
      ) : null}
    </div>
  );
}
