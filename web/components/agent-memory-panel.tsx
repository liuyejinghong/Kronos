"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clipboard,
  FileText,
  Link2,
  XCircle,
} from "lucide-react";
import { useMemo, type ReactNode } from "react";

import type {
  AgentMemoryDashboard,
  MemoryCheckItem,
  MemoryCheckSeverity,
  MemorySummaryItem,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type AgentMemoryPanelProps = {
  memory?: AgentMemoryDashboard;
  isLoading: boolean;
};

export function AgentMemoryPanel({ memory, isLoading }: AgentMemoryPanelProps) {
  if (isLoading) {
    return (
      <section className="grid gap-4">
        <div className="h-56 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
        <div className="grid gap-4 xl:grid-cols-2">
          <div className="h-72 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
          <div className="h-72 animate-pulse rounded-lg border border-slate-200 bg-slate-100" />
        </div>
      </section>
    );
  }

  if (!memory) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        Agent 记忆控制台暂时读不到。请确认本地后端已启动；这里不会写入长期记忆，也不会触发交易。
      </section>
    );
  }

  const blockingOrWarnings = memory.check.items.filter((item) => item.severity !== "passed");

  return (
    <section className="grid min-w-0 gap-5">
      <FirstScreenState memory={memory} />

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <SummaryList
          emptyText="暂无可展示的决策记录。"
          items={memory.decisions}
          title="最近决策与拒绝方案"
        />
        <SummaryList
          emptyText="暂无可展示的经验教训。"
          items={memory.lessons}
          title="经验教训"
        />
      </div>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
        <HandoffBlock prompt={memory.handoff.prompt_md} sourcePaths={memory.handoff.source_paths} />
        <CheckBlock checkStatus={memory.check.status} items={blockingOrWarnings} memory={memory} />
      </div>
    </section>
  );
}

function FirstScreenState({ memory }: { memory: AgentMemoryDashboard }) {
  const state = memory.state;
  return (
    <section className="grid min-w-0 gap-4 rounded-lg border border-slate-200 bg-white p-4 xl:grid-cols-[minmax(0,0.95fr)_minmax(0,1.05fr)]">
      <div className="min-w-0">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Badge tone="teal">v{state.current_version}</Badge>
          <Badge tone="sky">下一版本 v{state.next_version}</Badge>
          <Badge tone="slate">只读记忆</Badge>
        </div>
        <h2 className="text-base font-semibold text-slate-950">Agent 记忆与交接控制台</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          首屏先回答：现在验收什么、最近成功证据是什么、下一步该做什么。
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <InfoTile label="当前验收对象" value={state.current_acceptance_target_zh} />
          <InfoTile label="最新成功运行 / 验收记录" value={state.latest_successful_run_zh} />
          <InfoTile label="最高优先级" value={state.highest_priority_zh} />
          <InfoTile label="建议下一步" value={state.next_action_zh} />
        </div>
      </div>

      <div className="grid min-w-0 gap-3">
        <SourceBlock title="产品边界" text={state.product_boundary_zh} paths={state.source_paths} />
        <SourceBlock title="首屏来源文档" text="所有摘要都来自仓库文件；控制台不会依赖当前聊天上下文。" paths={state.source_paths} />
      </div>
    </section>
  );
}

function SummaryList({
  emptyText,
  items,
  title,
}: {
  emptyText: string;
  items: MemorySummaryItem[];
  title: string;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-base font-semibold text-slate-950">{title}</h2>
      </div>
      <div className="grid gap-3 p-4">
        {items.length === 0 ? (
          <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            {emptyText}
          </div>
        ) : (
          items.map((item, index) => (
            <div
              key={`${item.title_zh}-${index}`}
              className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3"
            >
              <div className="break-words font-semibold text-slate-950">{item.title_zh}</div>
              <p className="mt-2 break-words text-sm leading-6 text-slate-600">{item.body_zh}</p>
              <SourcePills paths={item.source_paths} />
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function HandoffBlock({ prompt, sourcePaths }: { prompt: string; sourcePaths: string[] }) {
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-slate-950">一键交接包</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            给新会话 / 新模型复制使用，保留事实源和安全禁令。
          </p>
        </div>
        <button
          className="inline-flex h-9 items-center justify-center gap-2 rounded bg-slate-900 px-3 text-sm font-semibold text-white transition hover:bg-slate-800"
          type="button"
          onClick={() => void navigator.clipboard?.writeText(prompt)}
        >
          <Clipboard className="h-4 w-4" />
          复制
        </button>
      </div>
      <div className="p-4">
        <pre className="max-h-96 min-w-0 overflow-auto whitespace-pre-wrap break-words rounded border border-slate-200 bg-slate-50 p-3 text-xs leading-5 text-slate-700">
          {prompt}
        </pre>
        <SourcePills paths={sourcePaths} />
      </div>
    </section>
  );
}

function CheckBlock({
  checkStatus,
  items,
  memory,
}: {
  checkStatus: MemoryCheckSeverity;
  items: MemoryCheckItem[];
  memory: AgentMemoryDashboard;
}) {
  const visibleItems = items.length > 0 ? items : memory.check.items.slice(0, 4);
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-slate-950">记忆一致性检查</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            {memory.check.passed_count} 项通过，{memory.check.warning_count} 项警告，{memory.check.blocking_count} 项阻塞。
          </p>
        </div>
        <StatusBadge severity={checkStatus} />
      </div>
      <div className="grid gap-3 p-4">
        {visibleItems.map((item) => (
          <CheckRow key={item.check_id} item={item} />
        ))}
      </div>
    </section>
  );
}

function CheckRow({ item }: { item: MemoryCheckItem }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 break-words font-semibold text-slate-950">{item.title_zh}</div>
        <StatusBadge severity={item.severity} />
      </div>
      <p className="mt-2 break-words text-sm leading-6 text-slate-600">{item.detail_zh}</p>
      {item.suggestion_zh ? (
        <div className="mt-2 break-words rounded border border-amber-200 bg-amber-50 p-2 text-xs leading-5 text-amber-950">
          {item.suggestion_zh}
        </div>
      ) : null}
      <SourcePills paths={item.source_paths} />
    </div>
  );
}

function SourceBlock({ paths, text, title }: { paths: string[]; text: string; title: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        <FileText className="h-4 w-4" />
        {title}
      </div>
      <p className="mt-2 break-words text-sm leading-6 text-slate-600">{text}</p>
      <SourcePills paths={paths} />
    </div>
  );
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 break-words text-sm font-medium leading-6 text-slate-900">{value}</div>
    </div>
  );
}

function SourcePills({ paths }: { paths: string[] }) {
  const uniquePaths = useMemo(() => Array.from(new Set(paths)).slice(0, 8), [paths]);
  if (uniquePaths.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-2">
      {uniquePaths.map((path) => (
        <span
          key={path}
          className="inline-flex min-w-0 max-w-full items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-600"
        >
          <Link2 className="h-3 w-3 shrink-0" />
          <span className="min-w-0 truncate">{path}</span>
        </span>
      ))}
    </div>
  );
}

function Badge({ children, tone }: { children: ReactNode; tone: "teal" | "sky" | "slate" }) {
  const toneClass = {
    teal: "border-teal-100 bg-teal-50 text-teal-800",
    sky: "border-sky-100 bg-sky-50 text-sky-800",
    slate: "border-slate-200 bg-slate-50 text-slate-700",
  }[tone];
  return (
    <span className={cn("inline-flex items-center rounded border px-2.5 py-1 text-xs font-semibold", toneClass)}>
      {children}
    </span>
  );
}

function StatusBadge({ severity }: { severity: MemoryCheckSeverity }) {
  const config = {
    passed: {
      className: "border-teal-100 bg-teal-50 text-teal-800",
      icon: <CheckCircle2 className="h-3.5 w-3.5" />,
      label: "通过",
    },
    warning: {
      className: "border-amber-200 bg-amber-50 text-amber-800",
      icon: <AlertTriangle className="h-3.5 w-3.5" />,
      label: "警告",
    },
    blocking: {
      className: "border-rose-100 bg-rose-50 text-rose-800",
      icon: <XCircle className="h-3.5 w-3.5" />,
      label: "阻塞",
    },
  }[severity];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-semibold", config.className)}>
      {config.icon}
      {config.label}
    </span>
  );
}
