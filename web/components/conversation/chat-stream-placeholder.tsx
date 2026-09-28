import { MessagesSquare } from "lucide-react";

import { cn } from "@/lib/utils";

/** 预留的消息预览结构。P16 接入会话服务后替换为真实消息模型。 */
export type ChatMessagePreview = {
  messageId: string;
  role: "owner" | "assistant";
  contentZh: string;
};

export type ChatStreamPlaceholderProps = {
  messages?: ChatMessagePreview[];
  inputPlaceholder?: string;
};

/**
 * 对话区占位：预留消息流与输入框布局。默认无消息、输入框禁用，
 * 不绑定任何事件、不请求后端接口。
 */
export function ChatStreamPlaceholder({
  messages = [],
  inputPlaceholder = "向研究助手提问，例如：当前策略表现如何？",
}: ChatStreamPlaceholderProps) {
  return (
    <section className="flex min-h-[360px] flex-col rounded-lg border border-slate-200 bg-white">
      <header className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">对话</h2>
        <p className="mt-1 text-xs text-slate-500">问结论、调参重跑、追问证据都会在这里进行。</p>
      </header>

      <div className="flex-1 p-4">
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
            <MessagesSquare className="h-6 w-6 text-slate-400" />
            <p className="text-sm font-medium text-slate-600">对话还没有开始</p>
            <p className="max-w-sm text-xs leading-5 text-slate-500">
              对话与任务执行能力将在后续版本接入；当前页面是界面骨架，不会请求后端接口。
            </p>
          </div>
        ) : (
          <ul className="grid content-start gap-3">
            {messages.map((message) => (
              <li
                className={cn(
                  "max-w-[85%] rounded-lg border px-3 py-2 text-sm leading-6",
                  message.role === "owner"
                    ? "ml-auto border-teal-100 bg-teal-50 text-teal-950"
                    : "border-slate-200 bg-slate-50 text-slate-800",
                )}
                key={message.messageId}
              >
                {message.contentZh}
              </li>
            ))}
          </ul>
        )}
      </div>

      <footer className="border-t border-slate-200 p-3">
        <div className="flex items-center gap-2">
          <input
            aria-label="对话输入（即将开放）"
            className="h-10 min-w-0 flex-1 rounded border border-slate-200 bg-slate-50 px-3 text-sm placeholder:text-slate-400"
            disabled
            placeholder={inputPlaceholder}
            type="text"
          />
          <button
            className="inline-flex h-10 shrink-0 items-center rounded bg-slate-300 px-4 text-sm font-semibold text-white"
            disabled
            type="button"
          >
            发送
          </button>
        </div>
      </footer>
    </section>
  );
}
