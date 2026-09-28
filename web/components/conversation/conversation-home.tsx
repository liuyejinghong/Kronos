"use client";

import { AlertTriangle, FlaskConical, Loader2, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import {
  ConversationApiError,
  cancelRun,
  createConversation,
  getConversation,
  getRun,
  getRunEvents,
  getVerdict,
  isTerminalTaskState,
  sendMessage,
  type MessageResult,
  type SessionDetail,
  type StrategySpecJson,
  type Verdict,
} from "@/lib/api-conversation";
import {
  ChatStream,
  type AssistantMessagePayload,
  type ChatMessageView,
} from "@/components/conversation/chat-stream";
import {
  StrategySummaryCard,
  summaryFromRevision,
  type StrategySummary,
} from "@/components/conversation/strategy-summary-card";
import {
  TaskProgressArea,
  type TaskProgressTask,
} from "@/components/conversation/task-progress-area";
import { type VerdictCardPreview } from "@/components/conversation/verdict-card-area";
import { VerdictCardMount } from "@/components/conversation/verdict-card-mount";

const SESSION_STORAGE_KEY = "kronos.conversation.sessionId";
const POLL_INTERVAL_MS = 2000;

// ------------------------------------------------------------------ helpers

function describeError(error: unknown): string {
  if (error instanceof ConversationApiError) {
    return error.status === 0 ? error.message : `${error.message}`;
  }
  return error instanceof Error ? error.message : String(error);
}

function normalizePayload(raw: Record<string, unknown>): AssistantMessagePayload {
  const payload: AssistantMessagePayload = {};
  const stringKey = (key: string): string | undefined => {
    const value = raw[key];
    return typeof value === "string" && value.length > 0 ? value : undefined;
  };
  payload.echo_text = stringKey("echo_text");
  payload.refusal_reason = stringKey("refusal_reason");
  payload.revision_id = stringKey("revision_id");
  payload.parent_revision_id = stringKey("parent_revision_id");
  payload.task_id = stringKey("task_id");
  const diff = raw["diff"];
  if (Array.isArray(diff)) {
    payload.diff = diff
      .filter(
        (entry): entry is { field: string; old: string; new: string } =>
          typeof entry === "object" &&
          entry !== null &&
          typeof (entry as { field?: unknown }).field === "string" &&
          typeof (entry as { old?: unknown }).old === "string" &&
          typeof (entry as { new?: unknown }).new === "string",
      )
      .map((entry) => ({ field: entry.field, old: entry.old, new: entry.new }));
  }
  const refs = raw["verdict_refs"];
  if (Array.isArray(refs)) {
    payload.verdict_refs = refs.filter((ref): ref is string => typeof ref === "string");
  }
  return payload;
}

function toChatMessageView(record: SessionDetail["messages"][number]): ChatMessageView {
  return {
    key: `m-${record.id}`,
    role: record.role,
    text: record.content,
    status: record.status,
    payload: record.role === "assistant" ? normalizePayload(record.payload) : null,
  };
}

// verdict JSON helpers (server sends the StrategyVerdict model dump)

type MetricValueJson = { value?: number | null; reason?: string | null };

type VerdictJson = {
  evidence_status?: string;
  disposition?: string | null;
  reason_codes?: string[];
  limitations?: string[];
  next_actions?: Array<{ kind?: string; detail?: string }>;
  metrics?: {
    net_return?: MetricValueJson;
    max_drawdown?: MetricValueJson;
    win_rate?: MetricValueJson;
    trade_count?: number;
  };
};

const EVIDENCE_STATUS_ZH: Record<string, string> = {
  valid: "有效",
  limited: "有限",
  insufficient: "不足",
  invalid: "无效",
};

const DISPOSITION_ZH: Record<string, string> = {
  observe: "观察保留（observe）",
  redesign: "需要重新设计（redesign）",
  retire_current_revision: "建议弃用当前修订（retire）",
};

function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "无数据";
  }
  return `${(value * 100).toFixed(2)}%`;
}

/** Map the published verdict JSON onto the shared card props contract. */
export function describeVerdict(verdictResponse: Verdict): VerdictCardPreview {
  const verdict = (verdictResponse.verdict ?? {}) as VerdictJson;
  const evidence = EVIDENCE_STATUS_ZH[verdict.evidence_status ?? ""] ?? verdict.evidence_status ?? "未知";
  const disposition =
    verdict.disposition === null || verdict.disposition === undefined
      ? "无（拒绝判定）"
      : (DISPOSITION_ZH[verdict.disposition] ?? verdict.disposition);
  const metrics = verdict.metrics ?? {};
  const tradeCount = typeof metrics.trade_count === "number" ? metrics.trade_count : null;

  const keyParts = [
    `净收益 ${formatRatio(metrics.net_return?.value)}`,
    tradeCount === null ? "平仓笔数无数据" : `${tradeCount} 笔平仓交易`,
    `最大回撤 ${formatRatio(metrics.max_drawdown?.value)}`,
    `胜率 ${formatRatio(metrics.win_rate?.value)}`,
  ];

  const limitation = verdict.limitations?.[0];
  const nextAction = verdict.next_actions?.[0]?.detail;

  return {
    conclusionZh: `证据状态：${evidence}；处置建议：${disposition}。`,
    keyEvidenceZh: `${keyParts.join("；")}。`,
    mainLimitationZh: limitation ?? "未标记限制。",
    nextStepZh: nextAction ?? "无后续动作建议。",
  };
}

// -------------------------------------------------------------- demo fixtures

const DEMO_SUMMARY: StrategySummary = {
  strategyName: "Kronos 变体",
  symbol: "BTCUSDT",
  timeframe: "15m",
  revisionLabel: "修订 9f2c1a7b",
  paramsZh: "倍数 2 · ATR 14",
  revisionId: "1a2b3c4d5e6f-9f2c1a7b-77fe01d3",
  chainDepth: 3,
  summaryZh: "演示样例：基于 R-breaker 分数归一化 q 值的阈值策略，UTC 日内平仓。",
};

const DEMO_MESSAGES: ChatMessageView[] = [
  { key: "demo-u1", role: "user", text: "当前结论如何？" },
  {
    key: "demo-a1",
    role: "assistant",
    status: "answered",
    payload: {
      verdict_refs: ["ledger=/state/ledger.jsonl", "reason_code=below_min_trades"],
    },
    text:
      "当前修订 9f2c1a7b 的最新结论（任务 demo-run-1）：evidence_status=limited，disposition=observe，reason_codes=below_min_trades。",
  },
  { key: "demo-u2", role: "user", text: "把倍数改成 2.0" },
  {
    key: "demo-a2",
    role: "assistant",
    status: "submitted",
    payload: {
      revision_id: "1a2b3c4d5e6f-9f2c1a7b",
      parent_revision_id: "1a2b3c4d5e6f",
      diff: [{ field: "params.volatility_multiplier", old: "1", new: "2" }],
      task_id: "demo-task-running",
    },
    text:
      "已创建修订 9f2c1a7b（父修订 1a2b3c4d5e6f）。差异：params.volatility_multiplier 1 → 2。评估任务已提交。",
  },
  {
    key: "demo-a3",
    role: "assistant",
    status: "clarification_needed",
    payload: { echo_text: "澄清：请指明要调的参数" },
    text: "想把它调成多少？请指明参数：倍数（0, 20] 还是 ATR 周期 [2, 1000]？",
  },
  { key: "demo-u4", role: "user", text: "帮我直接实盘下单" },
  {
    key: "demo-a4",
    role: "assistant",
    status: "refused",
    payload: { refusal_reason: "live_trading" },
    text: "该请求超出当前版本边界，已拒绝。",
  },
  { key: "demo-u5", role: "user", text: "网格策略改成 10 档" },
  {
    key: "demo-a5",
    role: "assistant",
    status: "refused",
    payload: { refusal_reason: "unsupported_template" },
    text: "该策略模板不在支持范围内，已拒绝。",
  },
];

function demoTask(
  taskId: string,
  state: TaskProgressTask["state"],
  extra?: Partial<TaskProgressTask>,
): TaskProgressTask {
  return {
    taskId,
    kind: "evaluate_strategy",
    state,
    stage: "",
    attempt: 1,
    errorRef: state === "failed" ? "backtest_engine_error" : null,
    resultAvailable: state === "succeeded",
    events:
      state === "queued"
        ? [{ seq: 1, kind: "submitted", detail: "kind=evaluate_strategy" }]
        : [
            { seq: 1, kind: "submitted", detail: "kind=evaluate_strategy" },
            { seq: 2, kind: "claimed", detail: "worker=demo-worker lease_ms=600000" },
            ...(state === "cancelled"
              ? [
                  { seq: 3, kind: "cancel_requested", detail: "cancel requested" },
                  { seq: 4, kind: "cancelled", detail: "confirmed by demo-worker" },
                ]
              : [{ seq: 3, kind: state, detail: null }]),
          ],
    noticeZh: null,
    cancelConfirmVisible: false,
    cancelling: false,
    ...extra,
  };
}

const DEMO_TASKS: TaskProgressTask[] = [
  demoTask("demo-task-queued", "queued"),
  demoTask("demo-task-running", "running", { stage: "backtest" }),
  demoTask("demo-task-cancelreq", "cancel_requested", { stage: "backtest" }),
  demoTask("demo-task-succeeded", "succeeded"),
  demoTask("demo-task-failed", "failed"),
  demoTask("demo-task-cancelled", "cancelled"),
  demoTask("demo-task-budget", "budget_exhausted"),
  demoTask("demo-task-blocked", "blocked"),
];

const DEMO_VERDICT: VerdictCardPreview = {
  conclusionZh: "证据状态：有限；处置建议：观察保留（observe）。",
  keyEvidenceZh: "净收益 3.42%；8 笔平仓交易；最大回撤 -5.10%；胜率 62.50%。",
  mainLimitationZh:
    "8 笔平仓交易低于预登记的最小笔数（30 笔）；结论仅供参考（仅警示，不自动判废）。",
  nextStepZh: "延长回测窗口或降低阈值后重新评估，先不要把该修订视为稳健。",
};

/**
 * 首页编排（P16）：?demo=1 时渲染静态演示样例（不请求后端），
 * 否则执行真实会话引导、发送、任务轮询与结论获取。
 */
export function ConversationHome({ demoMode }: { demoMode: boolean }) {
  if (demoMode) {
    return <DemoModeHome />;
  }
  return <LiveHome />;
}

// ------------------------------------------------------------------ live mode

type Phase = "booting" | "ready" | "error";

function LiveHome() {
  const [phase, setPhase] = useState<Phase>("booting");
  const [bootErrorZh, setBootErrorZh] = useState<string | null>(null);

  const [session, setSession] = useState<SessionDetail["session"] | null>(null);
  const [revision, setRevision] = useState<StrategySpecJson | null>(null);
  const [messages, setMessages] = useState<ChatMessageView[]>([]);

  const [optimistic, setOptimistic] = useState<ChatMessageView | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sendErrorZh, setSendErrorZh] = useState<string | null>(null);
  const [retryText, setRetryText] = useState<string | null>(null);

  const [tasks, setTasks] = useState<TaskProgressTask[]>([]);
  const [verdictPreview, setVerdictPreview] = useState<VerdictCardPreview | null>(null);
  const [verdictRunId, setVerdictRunId] = useState<string | null>(null);
  const [verdictErrorZh, setVerdictErrorZh] = useState<string | null>(null);

  const bootRef = useRef(false);
  const tasksRef = useRef<TaskProgressTask[]>([]);
  const lastEventSeqRef = useRef<Record<string, number>>({});
  const verdictRequestedRef = useRef<Set<string>>(new Set());

  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

  const applyDetail = useCallback((detail: SessionDetail) => {
    setSession(detail.session);
    setRevision(detail.current_revision);
    setMessages(detail.messages.map(toChatMessageView));
    // Collect task ids referenced by assistant messages so their progress
    // survives a refresh/restart (spec: 刷新与重启可恢复).
    const referenced: string[] = [];
    for (const record of detail.messages) {
      if (record.role !== "assistant") continue;
      const taskId = record.payload["task_id"];
      if (typeof taskId === "string" && taskId.length > 0) {
        referenced.push(taskId);
      }
    }
    if (referenced.length > 0) {
      setTasks((prev) => {
        const known = new Set(prev.map((task) => task.taskId));
        const additions = referenced
          .filter((taskId) => !known.has(taskId))
          .map(
            (taskId): TaskProgressTask => ({
              taskId,
              kind: "evaluate_strategy",
              state: "queued",
              stage: "",
              attempt: 0,
              errorRef: null,
              resultAvailable: false,
              events: [],
              noticeZh: null,
            }),
          );
        return additions.length > 0 ? [...prev, ...additions] : prev;
      });
    }
  }, []);

  const bootstrap = useCallback(async () => {
    setPhase("booting");
    setBootErrorZh(null);
    try {
      let detail: SessionDetail | null = null;
      const stored = window.localStorage.getItem(SESSION_STORAGE_KEY);
      if (stored) {
        try {
          detail = await getConversation(stored);
        } catch (error) {
          if (!(error instanceof ConversationApiError) || error.status !== 404) {
            throw error;
          }
        }
      }
      if (!detail) {
        const created = await createConversation();
        window.localStorage.setItem(SESSION_STORAGE_KEY, created.session_id);
        detail = await getConversation(created.session_id);
      }
      applyDetail(detail);
      setPhase("ready");
    } catch (error) {
      setBootErrorZh(describeError(error));
      setPhase("error");
    }
  }, [applyDetail]);

  useEffect(() => {
    if (bootRef.current) {
      return;
    }
    bootRef.current = true;
    void bootstrap();
  }, [bootstrap]);

  const loadVerdict = useCallback(async (runId: string) => {
    setVerdictErrorZh(null);
    try {
      const verdict = await getVerdict(runId);
      setVerdictPreview(describeVerdict(verdict));
      setVerdictRunId(runId);
    } catch (error) {
      setVerdictErrorZh(describeError(error));
    }
  }, []);

  const pollTask = useCallback(
    async (taskId: string) => {
      let nextStatus: Awaited<ReturnType<typeof getRun>>;
      try {
        nextStatus = await getRun(taskId);
      } catch {
        setTasks((prev) =>
          prev.map((task) =>
            task.taskId === taskId
              ? { ...task, noticeZh: "状态刷新失败，将继续自动重试。" }
              : task,
          ),
        );
        return;
      }
      let freshEvents: TaskProgressTask["events"] | null = null;
      const afterSeq = lastEventSeqRef.current[taskId] ?? 0;
      try {
        const page = await getRunEvents(taskId, afterSeq);
        if (page.events.length > 0) {
          lastEventSeqRef.current[taskId] = page.events[page.events.length - 1].seq;
          freshEvents = page.events.map((event) => ({
            seq: event.seq,
            kind: event.kind,
            detail: event.detail,
          }));
        }
      } catch {
        // events are supplementary; status polling continues
      }
      setTasks((prev) =>
        prev.map((task) =>
          task.taskId === taskId
            ? {
                ...task,
                state: nextStatus.state,
                kind: nextStatus.kind,
                stage: nextStatus.stage,
                attempt: nextStatus.attempt,
                errorRef: nextStatus.error_ref,
                resultAvailable: nextStatus.result_available,
                noticeZh: null,
                events: freshEvents ? [...task.events, ...freshEvents].slice(-30) : task.events,
              }
            : task,
        ),
      );
      if (
        nextStatus.state === "succeeded" &&
        nextStatus.result_available &&
        !verdictRequestedRef.current.has(taskId)
      ) {
        verdictRequestedRef.current.add(taskId);
        void loadVerdict(taskId);
      }
    },
    [loadVerdict],
  );

  // Poll ONLY while at least one task is non-terminal; stop on terminal state.
  const hasActiveTask = tasks.some((task) => !isTerminalTaskState(task.state));
  useEffect(() => {
    if (!hasActiveTask) {
      return;
    }
    const timer = window.setInterval(() => {
      for (const task of tasksRef.current) {
        if (!isTerminalTaskState(task.state)) {
          void pollTask(task.taskId);
        }
      }
    }, POLL_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
    };
  }, [hasActiveTask, pollTask]);

  const refreshConversation = useCallback(
    async (sessionId: string) => {
      const detail = await getConversation(sessionId);
      applyDetail(detail);
    },
    [applyDetail],
  );

  const submitText = useCallback(
    async (text: string) => {
      if (!session || submitting) {
        return;
      }
      const trimmed = text.trim();
      if (!trimmed) {
        return;
      }
      setSubmitting(true);
      setSendErrorZh(null);
      setRetryText(null);
      const optimisticView: ChatMessageView = {
        key: `optimistic-${Date.now()}`,
        role: "user",
        text: trimmed,
        optimistic: true,
      };
      setOptimistic(optimisticView);
      try {
        const result: MessageResult = await sendMessage(session.session_id, trimmed);
        setOptimistic(null);
        if (result.task_id) {
          const taskId = result.task_id;
          verdictRequestedRef.current.delete(taskId);
          setTasks((prev) =>
            prev.some((task) => task.taskId === taskId)
              ? prev
              : [
                  ...prev,
                  {
                    taskId,
                    kind: "evaluate_strategy",
                    state: "queued",
                    stage: "",
                    attempt: 0,
                    errorRef: null,
                    resultAvailable: false,
                    events: [],
                    noticeZh: null,
                  },
                ],
          );
          void pollTask(taskId);
        }
        await refreshConversation(session.session_id);
      } catch (error) {
        // Rollback the optimistic bubble; keep the text for the retry button.
        setOptimistic(null);
        setSendErrorZh(describeError(error));
        setRetryText(trimmed);
      } finally {
        setSubmitting(false);
      }
    },
    [pollTask, refreshConversation, session, submitting],
  );

  const handleCancelRequest = useCallback((taskId: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.taskId === taskId ? { ...task, cancelConfirmVisible: true } : task,
      ),
    );
  }, []);

  const handleCancelDismiss = useCallback((taskId: string) => {
    setTasks((prev) =>
      prev.map((task) =>
        task.taskId === taskId ? { ...task, cancelConfirmVisible: false } : task,
      ),
    );
  }, []);

  const handleCancelConfirm = useCallback(
    async (taskId: string) => {
      setTasks((prev) =>
        prev.map((task) =>
          task.taskId === taskId ? { ...task, cancelling: true, noticeZh: null } : task,
        ),
      );
      try {
        const status = await cancelRun(taskId);
        setTasks((prev) =>
          prev.map((task) =>
            task.taskId === taskId
              ? {
                  ...task,
                  state: status.state,
                  cancelConfirmVisible: false,
                  cancelling: false,
                  noticeZh:
                    status.state === "cancel_requested"
                      ? "取消请求已发出；等待执行方确认停止。"
                      : null,
                }
              : task,
          ),
        );
      } catch (error) {
        setTasks((prev) =>
          prev.map((task) =>
            task.taskId === taskId
              ? {
                  ...task,
                  cancelling: false,
                  cancelConfirmVisible: false,
                  noticeZh: `取消失败：${describeError(error)}`,
                }
              : task,
          ),
        );
        void pollTask(taskId);
      }
    },
    [pollTask],
  );

  const scrollToElement = useCallback((elementId: string) => {
    document.getElementById(elementId)?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, []);

  const handleTaskLinkClick = useCallback(
    (taskId: string) => {
      scrollToElement(`task-${taskId}`);
    },
    [scrollToElement],
  );

  const handleVerdictClick = useCallback(
    (taskId: string) => {
      scrollToElement("verdict-card-area");
      if (!verdictPreview) {
        void loadVerdict(taskId);
      }
    },
    [loadVerdict, scrollToElement, verdictPreview],
  );

  const summary = revision ? summaryFromRevision(revision) : null;
  const visibleMessages = optimistic ? [...messages, optimistic] : messages;

  if (phase === "booting") {
    return (
      <div className="flex min-h-[280px] flex-col items-center justify-center gap-2 rounded-lg border border-slate-200 bg-white p-8 text-center">
        <Loader2 className="h-5 w-5 animate-spin text-teal-700" />
        <p className="text-sm font-medium text-slate-600">正在连接研究助手…</p>
        <p className="text-xs text-slate-400">正在恢复会话或创建新会话。</p>
      </div>
    );
  }

  if (phase === "error") {
    return (
      <div className="flex min-h-[280px] flex-col items-center justify-center gap-3 rounded-lg border border-rose-200 bg-rose-50 p-8 text-center">
        <AlertTriangle className="h-5 w-5 text-rose-600" />
        <p className="text-sm font-semibold text-rose-900">无法连接研究助手</p>
        <p className="max-w-md break-words text-xs leading-5 text-rose-700">
          {bootErrorZh}
        </p>
        <p className="max-w-md break-words text-xs leading-5 text-rose-600">
          请确认本地服务已启动（uvicorn / kronos web），然后重试。
        </p>
        <button
          className="inline-flex items-center gap-1.5 rounded border border-rose-300 bg-white px-3 py-1.5 text-sm font-medium text-rose-800 transition hover:bg-rose-100"
          onClick={() => void bootstrap()}
          type="button"
        >
          <RefreshCw className="h-4 w-4" />
          重试
        </button>
      </div>
    );
  }

  return (
    <div className="grid min-w-0 gap-4">
      <StrategySummaryCard summary={summary} />

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <ChatStream
          errorZh={sendErrorZh}
          inputDisabled={false}
          messages={visibleMessages}
          onRetry={() => {
            if (retryText) {
              void submitText(retryText);
            }
          }}
          onSend={(text) => void submitText(text)}
          onTaskLinkClick={handleTaskLinkClick}
          retryText={retryText}
          submitting={submitting}
        />
        <div className="grid min-w-0 content-start gap-4">
          <TaskProgressArea
            onCancelConfirm={(taskId) => void handleCancelConfirm(taskId)}
            onCancelDismiss={handleCancelDismiss}
            onCancelRequest={handleCancelRequest}
            onVerdictClick={handleVerdictClick}
            tasks={tasks}
          />
          <div id="verdict-card-area" className="min-w-0">
            <VerdictCardMount verdict={verdictPreview} />
            {verdictRunId ? (
              <p className="mt-1 break-all font-mono text-[11px] leading-5 text-slate-400">
                结论任务 {verdictRunId}
              </p>
            ) : null}
            {verdictErrorZh ? (
              <div className="mt-1 flex flex-wrap items-center gap-2 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-900">
                <span className="min-w-0 flex-1 break-words">结论加载失败：{verdictErrorZh}</span>
                {verdictRunId ? (
                  <button
                    className="shrink-0 rounded border border-amber-300 bg-white px-2 py-1 font-medium"
                    onClick={() => void loadVerdict(verdictRunId)}
                    type="button"
                  >
                    重试
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ demo mode

/**
 * ?demo=1 演示模式：全部为静态样例数据，不发任何请求、不轮询、不可发送。
 * 用于验收走查全状态（8 个任务态 + 5 类助手消息 + 结论卡 + 摘要卡）。
 */
function DemoModeHome() {
  return (
    <div className="grid min-w-0 gap-4">
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-fuchsia-200 bg-fuchsia-50 px-4 py-3 text-sm">
        <FlaskConical className="h-4 w-4 shrink-0 text-fuchsia-700" />
        <span className="font-semibold text-fuchsia-900">演示模式</span>
        <span className="break-words text-xs leading-5 text-fuchsia-700">
          以下内容为静态样例数据（fixture），不会请求后端、不会轮询、不会创建任务。追加{" "}
          <code className="rounded bg-white/70 px-1 font-mono">?demo=1</code> 访问。
        </span>
      </div>

      <StrategySummaryCard summary={DEMO_SUMMARY} />

      <div className="grid min-w-0 gap-4 xl:grid-cols-[minmax(0,1.5fr)_minmax(320px,1fr)]">
        <ChatStream
          errorZh={null}
          inputDisabled
          inputDisabledReasonZh="演示模式：输入框已禁用，不发送消息"
          messages={DEMO_MESSAGES}
          onRetry={() => undefined}
          onSend={() => undefined}
          onTaskLinkClick={(taskId) => {
            document.getElementById(`task-${taskId}`)?.scrollIntoView({ behavior: "smooth", block: "center" });
          }}
          retryText={null}
          submitting={false}
        />
        <div className="grid min-w-0 content-start gap-4">
          <TaskProgressArea tasks={DEMO_TASKS} />
          <div id="verdict-card-area" className="min-w-0">
            <VerdictCardMount verdict={DEMO_VERDICT} />
            <p className="mt-1 break-all font-mono text-[11px] leading-5 text-slate-400">
              结论任务 demo-task-succeeded（演示样例）
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
