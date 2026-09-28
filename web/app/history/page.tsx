import { History, Inbox } from "lucide-react";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";

/**
 * 历史与证据页（占位骨架）。
 * 静态页面——不请求任何后端接口；会话与结论列表由 P14/P16 提供数据后接入。
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
            历史会话、结论卡与证据会按时间列在这里，便于回溯每次研究的依据。
          </p>
        </header>

        <section className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center">
          <Inbox className="h-8 w-8 text-slate-400" />
          <p className="text-base font-semibold text-slate-700">还没有研究记录</p>
          <p className="max-w-md text-sm leading-6 text-slate-500">
            完成第一次策略研究后，历史会话、结论卡与证据会出现在这里。
          </p>
          <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
            <Link
              className="inline-flex h-10 items-center rounded bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
              href="/"
            >
              去策略对话
            </Link>
            <Link
              className="inline-flex h-10 items-center rounded border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
              href="/advanced"
            >
              查看高级（只读）入口
            </Link>
          </div>
        </section>
      </div>
    </AppShell>
  );
}
