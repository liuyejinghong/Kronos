"use client";

import {
  AlertTriangle,
  Ban,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  CircleX,
  ClipboardList,
  Clock,
  Hourglass,
  Loader2,
  ListChecks,
} from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";
import { shortTaskId } from "@/components/conversation/chat-stream";

/** Frozen 8-state machine (kronos/runtime/tasks.py LEGAL_TRANSITIONS). */
export type ConversationTaskState =
  | "queued"
  | "running"
  | "cancel_requested"
  | "succeeded"
  | "failed"
  | "cancelled"
  | "budget_exhausted"
  | "blocked";

export type TaskEventView = {
  seq: number;
  kind: string;
  detail: string | null;
};

/** One polled run projected for display (P16 conversation session scope). */
export type TaskProgressTask = {
  taskId: string;
  kind: string;
  state: ConversationTaskState;
  stage: string;
  attempt: number;
  errorRef: string | null;
  resultAvailable: boolean;
  events: TaskEventView[];
  /** Transient poll/notice text (e.g. 状态刷新失败). */
  noticeZh?: string | null;
  cancelConfirmVisible?: boolean;
  cancelling?: boolean;
};

export type TaskProgressAreaProps = {
  tasks: TaskProgressTask[];
  onCancelRequest?: (taskId: string) => void;
  onCancelConfirm?: (taskId: string) => void;
  onCancelDismiss?: (taskId: string) => void;
  /** Click「查看结论」on a succeeded task. */
  onVerdictClick?: (taskId: string) => void;
};

const STATE_META: Record<
  ConversationTaskState,
  { label: string; className: string; icon: ReactNode }
> = {
  queued: {
    label: "排队中",
    className: "border-slate-200 bg-slate-50 text-slate-600",
    icon: <CircleDashed className="h-3.5 w-3.5" />,
  },
  running: {
    label: "执行中",
    className: "border-sky-100 bg-sky-50 text-sky-800",
    icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
  },
  cancel_requested: {
    label: "取消请求中（等待执行方确认）",
    className: "border-amber-200 bg-amber-50 text-amber-800",
    icon: <Hourglass className="h-3.5 w-3.5 animate-pulse" />,
  },
  succeeded: {
    label: "已完成",
    className: "border-teal-100 bg-teal-50 text-teal-800",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
  },
  failed: {
    label: "失败",
    className: "border-rose-200 bg-rose-50 text-rose-800",
    icon: <CircleX className="h-3.5 w-3.5" />,
  },
  cancelled: {
    label: "已取消",
    className: "border-slate-200 bg-slate-100 text-slate-500",
    icon: <CircleSlash className="h-3.5 w-3.5" />,
  },
  budget_exhausted: {
    label: "预算不足",
    className: "border-amber-200 bg-amber-50 text-amber-900",
    icon: <Ban className="h-3.5 w-3.5" />,
  },
  blocked: {
    label: "受阻",
    className: "border-amber-200 bg-amber-50 text-amber-900",
    icon: <AlertTriangle className="h-3.5 w-3.5" />,
  },
};

const TERMINAL_STATES: ReadonlySet<ConversationTaskState> = new Set([
  "succeeded",
  "failed",
  "cancelled",
  "budget_exhausted",
  "blocked",
]);

const KIND_ZH: Record<string, string> = {
  evaluate_strategy: "策略评估",
  ensure_data: "数据准备",
};

const EVENT_KIND_ZH: Record<string, string> = {
  submitted: "已提交",
  claimed: "已被执行方认领",
  cancel_requested: "收到取消请求",
  cancelled: "已取消",
  succeeded: "已完成",
  failed: "失败",
  budget_exhausted: "预算不足",
  blocked: "受阻",
  lease_expired_recovered: "租约过期恢复",
  heartbeat: "心跳",
};

const MAX_EVENTS_SHOWN = 4;

/**
 * 任务进度位：本会话内出现过的任务（轮询数据由 P16 的 conversation-home 提供）。
 * 覆盖 queued/running/cancel_requested/succeeded/failed/cancelled/
 * budget_exhausted/blocked 全态；两步取消在此展示确认步骤。
 */
export function TaskProgressArea({
  tasks,
  onCancelRequest,
  onCancelConfirm,
  onCancelDismiss,
  onVerdictClick,
}: TaskProgressAreaProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="border-b border-slate-200 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <ListChecks className="h-4 w-4" />
          任务进度
          {tasks.some((task) => !TERMINAL_STATES.has(task.state)) ? (
            <span className="inline-flex items-center gap-1 rounded border border-sky-100 bg-sky-50 px-1.5 py-0.5 text-[11px] font-medium text-sky-700">
              <Loader2 className="h-3 w-3 animate-spin" />
              每 2 秒自动刷新
            </span>
          ) : null}
        </h2>
      </header>
      <div className="grid gap-2 p-4">
        {tasks.length === 0 ? (
          <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
            当前没有进行中的任务。研究或回测执行时，任务状态会实时显示在这里。
          </div>
        ) : (
          tasks.map((task) => (
            <TaskRow
              key={task.taskId}
              onCancelConfirm={onCancelConfirm}
              onCancelDismiss={onCancelDismiss}
              onCancelRequest={onCancelRequest}
              onVerdictClick={onVerdictClick}
              task={task}
            />
          ))
        )}
      </div>
    </section>
  );
}

function TaskRow({
  task,
  onCancelRequest,
  onCancelConfirm,
  onCancelDismiss,
  onVerdictClick,
}: {
  task: TaskProgressTask;
  onCancelRequest?: (taskId: string) => void;
  onCancelConfirm?: (taskId: string) => void;
  onCancelDismiss?: (taskId: string) => void;
  onVerdictClick?: (taskId: string) => void;
}) {
  const meta = STATE_META[task.state] ?? {
    label: task.state,
    className: "border-slate-200 bg-slate-50 text-slate-600",
    icon: <CircleDashed className="h-3.5 w-3.5" />,
  };
  const terminal = TERMINAL_STATES.has(task.state);
  const cancellable = !terminal && task.state !== "cancel_requested";
  const id = `task-${task.taskId}`;

  return (
    <div
      className="rounded border border-slate-200 bg-slate-50 px-3 py-2"
      data-task-state={task.state}
      id={id}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="min-w-0 break-words text-sm text-slate-800">
          <span className="font-medium">{KIND_ZH[task.kind] ?? task.kind}</span>
          <span className="ml-2 font-mono text-xs text-slate-400" title={task.taskId}>
            {shortTaskId(task.taskId)}
          </span>
          {task.attempt > 1 ? (
            <span className="ml-2 text-xs text-slate-400">第 {task.attempt} 次尝试</span>
          ) : null}
        </span>
        <span
          className={cn(
            "inline-flex shrink-0 items-center gap-1 rounded border px-2 py-0.5 text-xs font-medium",
            meta.className,
          )}
        >
          {meta.icon}
          {meta.label}
        </span>
      </div>

      {task.stage ? (
        <p className="mt-1 break-words text-xs leading-5 text-slate-500">阶段：{task.stage}</p>
      ) : null}

      {task.state === "failed" && task.errorRef ? (
        <p className="mt-1 break-all rounded border border-rose-100 bg-white px-2 py-1 text-xs leading-5 text-rose-700">
          错误码 <span className="font-mono">{task.errorRef}</span>
          <span className="ml-1 text-rose-600">
            — 重试提示：调整表述或参数后重新发送即可再次发起评估。
          </span>
        </p>
      ) : null}

      {task.state === "budget_exhausted" ? (
        <p className="mt-1 text-xs leading-5 text-amber-800">
          本轮预算不足，任务未执行；等待预算重置或减少操作后重试。
        </p>
      ) : null}

      {task.state === "blocked" ? (
        <p className="mt-1 text-xs leading-5 text-amber-800">
          任务被依赖阻塞（例如数据未就绪）；处理依赖后重新发起。
        </p>
      ) : null}

      {task.noticeZh ? (
        <p className="mt-1 text-xs leading-5 text-amber-700">{task.noticeZh}</p>
      ) : null}

      {task.cancelConfirmVisible && cancellable ? (
        <div className="mt-2 rounded border border-amber-300 bg-amber-50 px-2.5 py-2">
          <p className="text-xs font-medium leading-5 text-amber-900">确认取消该任务？</p>
          <p className="mt-0.5 text-xs leading-5 text-amber-700">
            {task.state === "queued"
              ? "任务尚未开始执行，确认后将直接取消（无需执行方确认）。"
              : "将发送取消请求；执行方需要先停止当前工作，再由其确认取消完成。"}
          </p>
          <div className="mt-1.5 flex gap-2">
            <button
              className="inline-flex items-center gap-1 rounded border border-rose-300 bg-white px-2 py-1 text-xs font-semibold text-rose-700 transition hover:bg-rose-50 disabled:opacity-60"
              disabled={task.cancelling}
              onClick={() => onCancelConfirm?.(task.taskId)}
              type="button"
            >
              {task.cancelling ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              确认取消
            </button>
            <button
              className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-60"
              disabled={task.cancelling}
              onClick={() => onCancelDismiss?.(task.taskId)}
              type="button"
            >
              继续执行
            </button>
          </div>
        </div>
      ) : null}

      <div className="mt-1.5 flex flex-wrap items-center gap-2">
        {cancellable ? (
          <button
            className="rounded border border-slate-300 bg-white px-2 py-1 text-xs font-medium text-slate-600 transition hover:bg-slate-100 disabled:opacity-60"
            disabled={task.cancelling}
            onClick={() => onCancelRequest?.(task.taskId)}
            type="button"
          >
            取消任务
          </button>
        ) : null}
        {task.state === "succeeded" && task.resultAvailable ? (
          <button
            className="inline-flex items-center gap-1 rounded border border-teal-200 bg-teal-50 px-2 py-1 text-xs font-medium text-teal-800 transition hover:bg-teal-100"
            onClick={() => onVerdictClick?.(task.taskId)}
            type="button"
          >
            <ClipboardList className="h-3 w-3" />
            查看结论
          </button>
        ) : null}
        {task.state === "cancel_requested" ? (
          <span className="text-xs leading-5 text-amber-700">
            取消请求已发出；等待执行方确认停止（期间保持轮询）。
          </span>
        ) : null}
      </div>

      {task.events.length > 0 ? (
        <details className="mt-1.5">
          <summary className="cursor-pointer select-none text-xs text-slate-400 hover:text-slate-600">
            事件日志（{task.events.length}）
          </summary>
          <ul className="mt-1 grid gap-0.5">
            {task.events.slice(-MAX_EVENTS_SHOWN).map((event) => (
              <li className="break-all font-mono text-[11px] leading-5 text-slate-400" key={event.seq}>
                <span className="inline-flex items-center gap-1">
                  <Clock className="h-2.5 w-2.5" />#{event.seq}
                </span>{" "}
                {EVENT_KIND_ZH[event.kind] ?? event.kind}
                {event.detail ? ` — ${event.detail}` : ""}
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
