import { ArrowRight, FileText, GitBranch, ListChecks, ShieldAlert, SlidersHorizontal, Wrench } from "lucide-react";
import type { ReactNode } from "react";
import Link from "next/link";

import { AppShell } from "@/components/app-shell";

/** 降级面板清单：原功能不变，仅从主导航移除，集中在旧版工作台内。 */
const LEGACY_PANELS: Array<{ name: string; location: string; description: string; icon: ReactNode }> = [
  {
    name: "paper 状态",
    location: "工作台 · 今日",
    description: "模拟盘最新状态、订单、成交与错误。",
    icon: <ListChecks className="h-4 w-4" />,
  },
  {
    name: "记忆",
    location: "工作台 · 记忆",
    description: "Agent 记忆控制台：状态、决策、教训与交接包。",
    icon: <GitBranch className="h-4 w-4" />,
  },
  {
    name: "候选池",
    location: "工作台 · 候选池",
    description: "候选策略列表、状态分布与候选详情。",
    icon: <SlidersHorizontal className="h-4 w-4" />,
  },
  {
    name: "报告",
    location: "工作台 · 报告",
    description: "Agent 研究报告与 paper 报告阅读器。",
    icon: <FileText className="h-4 w-4" />,
  },
  {
    name: "运行",
    location: "工作台 · 时间线",
    description: "运行简报与事件时间线。",
    icon: <ListChecks className="h-4 w-4" />,
  },
  {
    name: "审批",
    location: "工作台 · 操作台 → 审批",
    description: "人工闸口事项列表与处理。",
    icon: <ShieldAlert className="h-4 w-4" />,
  },
  {
    name: "材料",
    location: "工作台 · 操作台 → 材料",
    description: "旧策略说明、失败记录等研究材料导入。",
    icon: <FileText className="h-4 w-4" />,
  },
];

/**
 * 高级（只读）入口：所有旧面板集中保留在旧版工作台（/legacy）中，
 * 功能不变，仅从主导航降级。静态页面，不请求后端接口。
 */
export default function AdvancedPage() {
  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600">
            <Wrench className="h-3.5 w-3.5" />
            高级
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">
            高级（只读）
          </h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            以下旧面板保留原功能，仅从主导航移除。它们集中在本地的旧版工作台中。
          </p>
          <Link
            className="mt-3 inline-flex h-10 items-center gap-2 rounded bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800"
            href="/legacy"
          >
            打开旧版工作台
            <ArrowRight className="h-4 w-4" />
          </Link>
        </header>

        <section className="overflow-hidden rounded-lg border border-slate-200 bg-white">
          <div className="border-b border-slate-200 px-4 py-3 text-sm font-semibold text-slate-950">
            面板与入口对照
          </div>
          <ul className="grid gap-px bg-slate-200">
            {LEGACY_PANELS.map((panel) => (
              <li className="bg-white px-4 py-3" key={panel.name}>
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="flex items-center gap-2 text-sm font-semibold text-slate-800">
                    {panel.icon}
                    {panel.name}
                  </span>
                  <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
                    {panel.location}
                  </span>
                </div>
                <p className="mt-1 break-words text-xs leading-5 text-slate-500">
                  {panel.description}
                </p>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </AppShell>
  );
}
