"use client";

/**
 * 同快照比较视图（P17 历史页）。两个结论引用（run_id 或 demo:<key>）并排展示
 * 关键指标（净收益 / 超额 / 胜率 / 交易数等）与参数差异摘要（spec_hash）。
 * demo 引用离线渲染；run 引用经 GET /api/verdicts/{run_id} 拉取。
 */

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Columns2 } from "lucide-react";
import Link from "next/link";

import { CARD_FIXTURES, isCardFixtureKey } from "@/components/verdict-card/card-fixtures";
import {
  projectVerdictComparison,
  type VerdictComparisonViewModel,
} from "@/components/verdict-card/card-projection";
import { fetchVerdictByRun } from "@/lib/api-verdicts";
import { cn } from "@/lib/utils";

export type VerdictRef =
  | { kind: "demo"; key: string }
  | { kind: "run"; runId: string };

export function parseVerdictRef(raw: string): VerdictRef | null {
  const trimmed = raw.trim();
  if (trimmed === "") {
    return null;
  }
  if (trimmed.startsWith("demo:")) {
    const key = trimmed.slice("demo:".length);
    return isCardFixtureKey(key) ? { kind: "demo", key } : null;
  }
  return { kind: "run", runId: trimmed };
}

function BackLink() {
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

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : String(error);
}

function CompareTable({ comparison }: { comparison: VerdictComparisonViewModel }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-slate-200 text-xs text-slate-500">
            <th className="py-1.5 pr-3 font-medium">指标</th>
            <th className="py-1.5 pr-3 font-medium">
              结论 A
              <span className="ml-2 font-mono text-xs font-normal text-slate-400">
                {comparison.sides[0].runId}
              </span>
            </th>
            <th className="py-1.5 pr-3 font-medium">A → B</th>
            <th className="py-1.5 font-medium">
              结论 B
              <span className="ml-2 font-mono text-xs font-normal text-slate-400">
                {comparison.sides[1].runId}
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          {comparison.rows.map((row) => (
            <tr key={row.key} className="border-b border-slate-100 last:border-0">
              <td className="py-1.5 pr-3 font-medium text-slate-800">{row.labelZh}</td>
              <td
                className={cn(
                  "py-1.5 pr-3 font-mono",
                  row.a.isNull ? "text-slate-500" : "text-slate-950",
                )}
              >
                {row.a.display}
              </td>
              <td className="py-1.5 pr-3 font-mono text-xs text-slate-500">
                {row.deltaDisplay ?? "—（存在不可算项）"}
              </td>
              <td
                className={cn(
                  "py-1.5 font-mono",
                  row.b.isNull ? "text-slate-500" : "text-slate-950",
                )}
              >
                {row.b.display}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export type CompareViewProps = {
  refA: string;
  refB: string;
};

export function CompareView({ refA, refB }: CompareViewProps) {
  const parsedA = parseVerdictRef(refA);
  const parsedB = parseVerdictRef(refB);

  const queryA = useQuery({
    enabled: parsedA?.kind === "run",
    queryFn: () => fetchVerdictByRun((parsedA as { kind: "run"; runId: string }).runId),
    queryKey: ["verdict-compare-a", parsedA?.kind === "run" ? parsedA.runId : ""],
    retry: false,
  });
  const queryB = useQuery({
    enabled: parsedB?.kind === "run",
    queryFn: () => fetchVerdictByRun((parsedB as { kind: "run"; runId: string }).runId),
    queryKey: ["verdict-compare-b", parsedB?.kind === "run" ? parsedB.runId : ""],
    retry: false,
  });

  const invalidRefs = [
    ...(parsedA === null ? [refA] : []),
    ...(parsedB === null ? [refB] : []),
  ];
  if (invalidRefs.length > 0) {
    return (
      <div className="grid gap-4">
        <BackLink />
        <section className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-800">
          无效的结论引用：{invalidRefs.join("、")}。run_id 直接填写；内置演示请用
          demo:&lt;状态&gt;（如 demo:valid-observe）。
        </section>
      </div>
    );
  }

  const verdictA = parsedA?.kind === "demo" ? CARD_FIXTURES[parsedA.key] : (queryA.data?.verdict ?? null);
  const verdictB = parsedB?.kind === "demo" ? CARD_FIXTURES[parsedB.key] : (queryB.data?.verdict ?? null);
  const loading =
    (parsedA?.kind === "run" && queryA.isPending) || (parsedB?.kind === "run" && queryB.isPending);
  const fetchError =
    parsedA?.kind === "run" && queryA.isError
      ? errorMessage(queryA.error)
      : parsedB?.kind === "run" && queryB.isError
        ? errorMessage(queryB.error)
        : null;

  const comparison =
    verdictA !== null && verdictB !== null ? projectVerdictComparison(verdictA, verdictB) : null;

  return (
    <div className="grid min-w-0 gap-4">
      <BackLink />
      {loading ? (
        <section className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
          正在加载两个结论 …
        </section>
      ) : null}
      {fetchError ? (
        <section className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-4 text-sm leading-6 text-amber-800">
          {fetchError}
        </section>
      ) : null}
      {comparison ? (
        <section className="rounded-lg border border-slate-200 bg-white p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
            <Columns2 className="h-4 w-4 text-teal-700" />
            同快照比较
          </div>
          <div className="mt-3">
            <CompareTable comparison={comparison} />
          </div>
          <div className="mt-3 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs leading-5 text-slate-600">
            参数差异摘要：{comparison.paramDiff.summaryZh}
          </div>
          <ul className="mt-2 grid gap-1 text-xs text-slate-500">
            {comparison.contextDiff.map((entry) => (
              <li className="flex items-center gap-2" key={entry.labelZh}>
                <span
                  className={cn(
                    "rounded px-1.5 py-0.5 font-semibold",
                    entry.same ? "bg-emerald-50 text-emerald-700" : "bg-amber-50 text-amber-700",
                  )}
                >
                  {entry.same ? "一致" : "不同"}
                </span>
                {entry.labelZh}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
