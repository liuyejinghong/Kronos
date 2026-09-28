import { CheckCircle2, CircleDashed, CircleSlash, CircleX, Loader2, ListChecks } from "lucide-react";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/** 任务四态 + 排队/取消，覆盖全态走查（执行中/完成/失败/取消）。 */
export type ConversationTaskState = "queued" | "running" | "done" | "failed" | "cancelled";

/** 预留的任务预览结构。P16 接入任务进度轮询后替换为真实任务模型。 */
export type ConversationTaskPreview = {
  taskId: string;
  titleZh: string;
  state: ConversationTaskState;
};

export type TaskProgressAreaProps = {
  tasks: ConversationTaskPreview[];
};

const STATE_META: Record<ConversationTaskState, { label: string; className: string; icon: ReactNode }> = {
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
  done: {
    label: "已完成",
    className: "border-teal-100 bg-teal-50 text-teal-800",
    icon: <CheckCircle2 className="h-3.5 w-3.5" />,
  },
  failed: {
    label: "失败",
    className: "border-amber-200 bg-amber-50 text-amber-900",
    icon: <CircleX className="h-3.5 w-3.5" />,
  },
  cancelled: {
    label: "已取消",
    className: "border-slate-200 bg-slate-100 text-slate-500",
    icon: <CircleSlash className="h-3.5 w-3.5" />,
  },
};

/**
 * 任务进度位。tasks 为空时展示空状态提示，不发任何请求。
 */
export function TaskProgressArea({ tasks }: TaskProgressAreaProps) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white">
      <header className="border-b border-slate-200 px-4 py-3">
        <h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950">
          <ListChecks className="h-4 w-4" />
          任务进度
        </h2>
      </header>
      <div className="grid gap-2 p-4">
        {tasks.length === 0 ? (
          <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
            当前没有进行中的任务。研究或回测执行时，任务状态会实时显示在这里。
          </div>
        ) : (
          tasks.map((task) => {
            const meta = STATE_META[task.state];
            return (
              <div
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-slate-200 bg-slate-50 px-3 py-2"
                key={task.taskId}
              >
                <span className="min-w-0 break-words text-sm text-slate-800">{task.titleZh}</span>
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
            );
          })
        )}
      </div>
    </section>
  );
}
