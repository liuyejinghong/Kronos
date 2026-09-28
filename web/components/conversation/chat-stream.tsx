"use client";

import { AlertTriangle, Ban, Loader2, MessagesSquare, RefreshCw, Send } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type FormEvent, type KeyboardEvent } from "react";

import { cn } from "@/lib/utils";
import { shortRevisionId } from "@/components/conversation/strategy-summary-card";

/** Assistant message payload keys as persisted by the conversation service. */
export type AssistantMessagePayload = {
  echo_text?: string;
  refusal_reason?: string;
  revision_id?: string;
  parent_revision_id?: string;
  diff?: Array<{ field: string; old: string; new: string }>;
  task_id?: string;
  verdict_refs?: string[];
};

export type ChatMessageView = {
  key: string;
  role: "user" | "assistant";
  text: string;
  /** Persisted assistant status (submitted / refused / answered / ...). */
  status?: string | null;
  payload?: AssistantMessagePayload | null;
  /** Optimistic message not yet confirmed by the server. */
  optimistic?: boolean;
};

export type ChatStreamProps = {
  messages: ChatMessageView[];
  /** A POST is in flight; input + chips disabled. */
  submitting: boolean;
  /** Set when the last send failed; shows the banner + retry button. */
  errorZh: string | null;
  /** The text whose send failed (retry re-sends it). */
  retryText: string | null;
  /** Hard-disable the input (bootstrap error / demo mode). */
  inputDisabled?: boolean;
  inputDisabledReasonZh?: string;
  /** Override the empty-state copy (demo walkthrough). */
  emptyTitleZh?: string;
  emptyBodyZh?: string;
  onSend: (text: string) => void;
  onRetry: () => void;
  /** Click on a task chip inside a submitted message. */
  onTaskLinkClick?: (taskId: string) => void;
};

const REFUSAL_ZH: Record<string, string> = {
  live_trading: "实盘/下单请求超出当前版本边界：v0.5 只支持本地回测研究，不会连接交易所。",
  unsupported_template: "该策略模板不在支持范围：当前仅支持 Kronos 变体（kronos_threshold_v1）。",
};

/**
 * 对话流：用户/助手消息、结构化载荷（差异回显 / 澄清追问 / 拒绝 / 任务提交）、
 * 输入框（Enter 发送、发送中禁用）。纯展示 + 回调，不发请求。
 */
export function ChatStream({
  messages,
  submitting,
  errorZh,
  retryText,
  inputDisabled = false,
  inputDisabledReasonZh,
  emptyTitleZh,
  emptyBodyZh,
  onSend,
  onRetry,
  onTaskLinkClick,
}: ChatStreamProps) {
  const [draft, setDraft] = useState("");
  const listRef = useRef<HTMLDivElement | null>(null);

  const inputBlocked = submitting || inputDisabled;
  const lastClarificationKey = findLastClarificationKey(messages);
  const scrollSignal = useMemo(
    () => messages.map((message) => `${message.key}:${message.optimistic ? 1 : 0}`).join(","),
    [messages],
  );

  useEffect(() => {
    const node = listRef.current;
    if (node) {
      node.scrollTop = node.scrollHeight;
    }
  }, [scrollSignal]);

  function submitDraft() {
    const text = draft.trim();
    if (!text || inputBlocked) {
      return;
    }
    onSend(text);
    setDraft("");
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    submitDraft();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter" && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submitDraft();
    }
  }

  return (
    <section className="flex min-h-[420px] flex-col rounded-lg border border-slate-200 bg-white">
      <header className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">对话</h2>
        <p className="mt-1 text-xs text-slate-500">问结论、调参重跑、追问证据都会在这里进行。</p>
      </header>

      <div className="flex-1 p-4" ref={listRef}>
        {messages.length === 0 ? (
          <div className="flex h-full min-h-[220px] flex-col items-center justify-center gap-2 rounded border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
            <MessagesSquare className="h-6 w-6 text-slate-400" />
            <p className="text-sm font-medium text-slate-600">
              {emptyTitleZh ?? "对话还没有开始"}
            </p>
            <p className="max-w-sm text-xs leading-5 text-slate-500">
              {emptyBodyZh ??
                "发一句「当前结论如何？」开始；明确调参（如「倍数改成 2.0」）会创建修订并直接执行。"}
            </p>
          </div>
        ) : (
          <ul className="grid content-start gap-3">
            {messages.map((message) => (
              <li
                className={cn(
                  "flex",
                  message.role === "user" ? "justify-end" : "justify-start",
                )}
                key={message.key}
              >
                <div className={cn("max-w-[92%] min-w-0", message.role === "user" && "text-right")}>
                  {message.role === "user" ? (
                    <div
                      className={cn(
                        "inline-block break-words rounded-lg border px-3 py-2 text-left text-sm leading-6",
                        message.optimistic
                          ? "border-teal-100 bg-teal-50/60 text-teal-950/70"
                          : "border-teal-100 bg-teal-50 text-teal-950",
                      )}
                    >
                      {message.text}
                      {message.optimistic ? (
                        <span className="ml-2 inline-flex items-center gap-1 align-middle text-xs text-teal-700">
                          <Loader2 className="h-3 w-3 animate-spin" />
                          发送中
                        </span>
                      ) : null}
                    </div>
                  ) : (
                    <AssistantBubble
                      message={message}
                      showQuickReplies={message.key === lastClarificationKey}
                      chipsDisabled={inputBlocked}
                      onSend={onSend}
                      onTaskLinkClick={onTaskLinkClick}
                    />
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {errorZh ? (
        <div className="mx-4 mb-2 flex flex-wrap items-center gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <span className="min-w-0 flex-1 break-words">
            发送失败：{errorZh}
            {retryText ? "（消息未送达，可重试）" : ""}
          </span>
          {retryText ? (
            <button
              className="inline-flex shrink-0 items-center gap-1 rounded border border-amber-300 bg-white px-2 py-1 font-medium text-amber-900 transition hover:bg-amber-100"
              onClick={onRetry}
              type="button"
            >
              <RefreshCw className="h-3 w-3" />
              重试
            </button>
          ) : null}
        </div>
      ) : null}

      <footer className="border-t border-slate-200 p-3">
        <form className="flex items-center gap-2" onSubmit={handleSubmit}>
          <input
            aria-label="对话输入"
            className="h-10 min-w-0 flex-1 rounded border border-slate-200 bg-slate-50 px-3 text-sm text-slate-900 placeholder:text-slate-400 focus:border-teal-300 focus:bg-white focus:outline-none disabled:opacity-60"
            disabled={inputBlocked}
            maxLength={4000}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              inputDisabledReasonZh ?? (submitting ? "消息发送中…" : "向研究助手提问，例如：当前策略表现如何？")
            }
            type="text"
            value={draft}
          />
          <button
            className="inline-flex h-10 shrink-0 items-center gap-1.5 rounded bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            disabled={inputBlocked || draft.trim().length === 0}
            type="submit"
          >
            {submitting ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            发送
          </button>
        </form>
      </footer>
    </section>
  );
}

function AssistantBubble({
  message,
  showQuickReplies,
  chipsDisabled,
  onSend,
  onTaskLinkClick,
}: {
  message: ChatMessageView;
  showQuickReplies: boolean;
  chipsDisabled: boolean;
  onSend: (text: string) => void;
  onTaskLinkClick?: (taskId: string) => void;
}) {
  const payload = message.payload ?? {};
  const status = message.status ?? null;

  if (status === "refused") {
    return (
      <RefusalCard reason={payload.refusal_reason ?? null} text={message.text} />
    );
  }

  if (status === "budget_exhausted") {
    return (
      <div className="inline-block max-w-full rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-left">
        <div className="flex items-center gap-1.5 text-xs font-semibold text-amber-900">
          <Ban className="h-3.5 w-3.5" />
          预算不足，未创建评估任务
        </div>
        <p className="mt-1 break-words whitespace-pre-wrap text-sm leading-6 text-amber-950">
          {message.text}
        </p>
        {payload.diff && payload.diff.length > 0 ? (
          <DiffTable diff={payload.diff} />
        ) : null}
      </div>
    );
  }

  return (
    <div className="inline-block max-w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left">
      <p className="break-words whitespace-pre-wrap text-sm leading-6 text-slate-800">
        {message.text}
      </p>

      {status === "clarification_needed" ? (
        <p className="mt-1 text-[11px] text-slate-500">需要你补充一句才能继续。</p>
      ) : null}

      {payload.diff && payload.diff.length > 0 ? <DiffTable diff={payload.diff} /> : null}

      {payload.revision_id ? (
        <p className="mt-1 break-all font-mono text-[11px] leading-5 text-slate-500">
          修订 {shortRevisionId(payload.revision_id)}
          {payload.parent_revision_id
            ? ` ← 父修订 ${shortRevisionId(payload.parent_revision_id)}`
            : ""}
        </p>
      ) : null}

      {payload.task_id ? (
        <button
          className="mt-2 inline-flex items-center gap-1.5 rounded border border-sky-200 bg-sky-50 px-2 py-1 text-xs font-medium text-sky-800 transition hover:bg-sky-100"
          onClick={() => onTaskLinkClick?.(payload.task_id as string)}
          type="button"
        >
          评估任务 {shortTaskId(payload.task_id)} → 查看下方任务进度
        </button>
      ) : null}

      {payload.verdict_refs && payload.verdict_refs.length > 0 ? (
        <div className="mt-2 flex flex-wrap gap-1">
          {payload.verdict_refs.map((ref) => (
            <span
              className="max-w-full truncate rounded border border-slate-200 bg-white px-1.5 py-0.5 font-mono text-[11px] text-slate-500"
              key={ref}
              title={ref}
            >
              {ref}
            </span>
          ))}
        </div>
      ) : null}

      {showQuickReplies ? (
        <QuickReplies
          disabled={chipsDisabled}
          onPick={onSend}
          question={message.text}
        />
      ) : null}
    </div>
  );
}

function RefusalCard({ reason, text }: { reason: string | null; text: string }) {
  return (
    <div className="inline-block max-w-full rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-left">
      <div className="flex items-center gap-1.5 text-xs font-semibold text-rose-800">
        <Ban className="h-3.5 w-3.5" />
        已拒绝（不会创建任务）
      </div>
      <p className="mt-1 break-words whitespace-pre-wrap text-sm leading-6 text-rose-950">
        {text}
      </p>
      {reason ? (
        <p className="mt-1 break-words text-xs leading-5 text-rose-700">
          {REFUSAL_ZH[reason] ?? `拒绝原因：${reason}`}
        </p>
      ) : null}
    </div>
  );
}

/** 参数/符号/周期 变更差异（父修订 → 子修订）。 */
export function DiffTable({ diff }: { diff: Array<{ field: string; old: string; new: string }> }) {
  if (diff.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 rounded border border-slate-200 bg-white">
      <div className="border-b border-slate-100 px-2.5 py-1.5 text-[11px] font-semibold text-slate-500">
        修订差异（当前 → 新）
      </div>
      <ul className="grid gap-1 px-2.5 py-1.5">
        {diff.map((entry) => (
          <li className="flex flex-wrap items-baseline gap-x-2 text-xs leading-5" key={entry.field}>
            <span className="font-mono text-slate-500">{entry.field}</span>
            <span className="font-mono text-slate-400">{entry.old}</span>
            <span aria-hidden className="text-slate-400">
              →
            </span>
            <span className="font-mono font-semibold text-teal-800">{entry.new}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** 澄清追问下的快捷回复 chips：只填充合法话术，点击即发送。 */
export function QuickReplies({
  question,
  disabled,
  onPick,
}: {
  question: string;
  disabled: boolean;
  onPick: (text: string) => void;
}) {
  const replies = quickRepliesFor(question);
  if (replies.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {replies.map((reply) => (
        <button
          className="rounded-full border border-teal-200 bg-teal-50 px-2.5 py-1 text-xs font-medium text-teal-800 transition hover:bg-teal-100 disabled:cursor-not-allowed disabled:opacity-50"
          disabled={disabled}
          key={reply}
          onClick={() => onPick(reply)}
          type="button"
        >
          {reply}
        </button>
      ))}
    </div>
  );
}

/**
 * 从澄清问题文本推断可选回答（仅生成合法话术，不解析参数语义）。
 * 服务端会把半截调整存为 pending 并在下一轮合并，所以这里只管把话说全。
 */
export function quickRepliesFor(question: string): string[] {
  const numberMatch = question.match(/\d+(?:\.\d+)?/);
  if (/哪个参数|哪一项|要调/.test(question) && numberMatch) {
    const value = numberMatch[0];
    return [`倍数改成 ${value}`, `ATR 改成 ${value}`];
  }
  if (/15m|1h|时间|周期/.test(question) && /(还是|换成|切换|支持)/.test(question)) {
    return ["换成 15m", "换成 1h"];
  }
  if (/倍数|乘数|multiplier/i.test(question)) {
    return ["倍数改成 2.0", "倍数改成 1.5", "倍数改成 0.5"];
  }
  if (/ATR|atr_period|period/i.test(question)) {
    return ["ATR 改成 20", "ATR 改成 14", "ATR 改成 30"];
  }
  if (/交易对|标的|币种|symbol/i.test(question)) {
    return ["换成 ETHUSDT", "换成 SOLUSDT"];
  }
  if (numberMatch) {
    const value = numberMatch[0];
    return [`倍数改成 ${value}`, `ATR 改成 ${value}`];
  }
  if (/更激进|更保守|激进|保守/.test(question)) {
    return ["倍数改成 0.5", "倍数改成 2.0"];
  }
  return [];
}

function findLastClarificationKey(messages: ChatMessageView[]): string | null {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index];
    if (message && message.role === "assistant" && message.status === "clarification_needed") {
      return message.key;
    }
  }
  return null;
}

export function shortTaskId(taskId: string): string {
  return taskId.length > 10 ? `${taskId.slice(0, 10)}…` : taskId;
}
