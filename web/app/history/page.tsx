import { History } from "lucide-react";
import { Suspense } from "react";

import { AppShell } from "@/components/app-shell";
import { HistoryClient } from "@/components/history/history-client";

/**
 * 历史与证据页（P17）。
 * 列表视图依赖的「历史结论列表」后端接口尚未提供（M2/P18 范围）；
 * 详情与比较视图按 run_id / demo 引用工作，入口见列表页说明。
 */
export default function HistoryPage() {
  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600">
            <History className="h-3.5 w-3.5" />
            历史与证据
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">
            历史与证据
          </h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            回看每次研究的结论卡，并排比较两次结论的关键指标与参数差异。
          </p>
        </header>
        <Suspense
          fallback={
            <section className="rounded-lg border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
              正在读取 URL 参数 …
            </section>
          }
        >
          <HistoryClient />
        </Suspense>
      </div>
    </AppShell>
  );
}
