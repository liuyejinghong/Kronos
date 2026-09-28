import { MessagesSquare } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { ChatStreamPlaceholder } from "@/components/conversation/chat-stream-placeholder";
import { StrategySummaryCard } from "@/components/conversation/strategy-summary-card";
import { TaskProgressArea } from "@/components/conversation/task-progress-area";
import { VerdictCardArea } from "@/components/conversation/verdict-card-area";

/**
 * 首页：策略对话（占位骨架）。
 * 静态页面——不请求任何后端接口；真实对话、任务轮询与结论数据由 P16/P17 接入。
 */
export default function ConversationHomePage() {
  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            <MessagesSquare className="h-3.5 w-3.5" />
            策略对话
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">
            和研究助手聊聊你的策略
          </h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            问结论、调参重跑、追问证据——对话是主入口。旧面板仍可在「高级（只读）」中使用。
          </p>
        </header>

        <StrategySummaryCard summary={null} />

        <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(300px,1fr)]">
          <ChatStreamPlaceholder />
          <div className="grid min-w-0 content-start gap-4">
            <TaskProgressArea tasks={[]} />
            <VerdictCardArea verdict={null} />
          </div>
        </div>
      </div>
    </AppShell>
  );
}
