/**
 * Typed client for the conversation + run API (package P16).
 *
 * Backend routes (kronos/web/routes/conversation.py, package P14):
 * - ``POST /api/conversations``                     → 201 ConversationCreated
 * - ``POST /api/conversations/{id}/messages``      → 202 MessageResult
 * - ``GET  /api/conversations/{id}``               → SessionDetail
 * - ``GET  /api/runs/{task_id}``                   → RunStatus
 * - ``GET  /api/runs/{task_id}/events?after_seq=`` → RunEvents
 * - ``POST /api/runs/{task_id}/cancel``            → RunStatus (409 on bad state)
 * - ``GET  /api/verdicts/{run_id}``                → Verdict
 *
 * The browser talks to the SAME-ORIGIN proxy base ``/api/kronos`` (wired in
 * next.config.mjs as ``/api/kronos/:path*`` → ``{backend}/api/:path*``), the
 * same convention as ``lib/api.ts``. Every type below mirrors the Pydantic
 * response models field-for-field (snake_case JSON).
 */

/** Same-origin proxy base; overridable for non-proxy deployments. */
export const CONVERSATION_API_BASE =
  process.env.NEXT_PUBLIC_KRONOS_API_BASE_URL ?? "/api/kronos";

/** Frozen 8-state machine (kronos/research/verdict/contracts.py TaskState). */
export type TaskState =
  | "queued"
  | "running"
  | "cancel_requested"
  | "succeeded"
  | "blocked"
  | "failed"
  | "cancelled"
  | "budget_exhausted";

/** States with no legal outgoing transition; polling stops here. */
export const TERMINAL_TASK_STATES: ReadonlySet<TaskState> = new Set([
  "succeeded",
  "blocked",
  "failed",
  "cancelled",
  "budget_exhausted",
]);

export function isTerminalTaskState(state: string): boolean {
  return TERMINAL_TASK_STATES.has(state as TaskState);
}

// ---------------------------------------------------------------- API models

export type ConversationCreated = {
  session_id: string;
  created_at_ms: number;
  current_revision_id: string;
};

export type RevisionDiffEntry = {
  field: string;
  old: string;
  new: string;
};

export type MessageStatus =
  | "submitted"
  | "answered"
  | "clarification_needed"
  | "refused"
  | "budget_exhausted";

/** 202-shaped result of one conversation turn (service.MessageResult). */
export type MessageResult = {
  message_id: number;
  assistant_message_id: number;
  session_id: string;
  intent_kind: string;
  status: MessageStatus;
  echo_text: string;
  clarification_question: string | null;
  revision_id: string | null;
  parent_revision_id: string | null;
  diff: RevisionDiffEntry[];
  task_id: string | null;
  task_state: string | null;
  verdict_refs: string[];
};

export type SessionInfo = {
  session_id: string;
  created_at_ms: number;
  current_revision_id: string;
};

/** One persisted message row (service.MessageRecord). */
export type ConversationMessage = {
  id: number;
  session_id: string;
  role: "user" | "assistant";
  content: string;
  intent_kind: string | null;
  status: string | null;
  payload: Record<string, unknown>;
  created_at_ms: number;
};

/** strategy.spec.StrategySpec JSON (identity fields derived server-side). */
export type StrategySpecJson = {
  strategy_revision_id: string;
  parent_revision_id: string | null;
  template_version: string;
  variant_label_zh: string;
  symbols: string[];
  signal_timeframe: "15m" | "1h";
  execution_timeframe: string;
  params: {
    atr_period: number;
    volatility_multiplier: number;
  };
  position_policy: {
    equity_fraction: number;
  };
  fill_policy: {
    fill_ref: string;
  };
  cost_policy_id: string;
  spec_hash: string;
  created_at: string;
};

export type SessionDetail = {
  session: SessionInfo;
  current_revision: StrategySpecJson;
  holdout_exposure_count: number;
  messages: ConversationMessage[];
};

/** Task status projection (routes/conversation.py RunStatusResponse). */
export type RunStatus = {
  task_id: string;
  kind: string;
  state: TaskState;
  stage: string;
  attempt: number;
  error_ref: string | null;
  created_at: number;
  updated_at: number;
  result_available: boolean;
};

/** One lifecycle event (research.verdict.contracts TaskEvent). */
export type TaskEvent = {
  seq: number;
  task_id: string;
  ts_ms: number;
  kind: string;
  detail: string | null;
};

export type RunEvents = {
  task_id: string;
  events: TaskEvent[];
};

/** Published verdict artifact (routes/conversation.py VerdictResponse). */
export type Verdict = {
  run_id: string;
  state: string;
  verdict: Record<string, unknown>;
  artifact_refs: Record<string, string>;
};

// ------------------------------------------------------------------- errors

/** Error carrying the HTTP status plus the FastAPI ``detail`` string. */
export class ConversationApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string, message?: string) {
    super(message ?? `Kronos conversation API ${status}: ${detail}`);
    this.name = "ConversationApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseErrorDetail(response: Response): Promise<string> {
  const raw = await response.text().catch(() => "");
  if (!raw) {
    return `HTTP ${response.status}`;
  }
  try {
    const parsed = JSON.parse(raw) as unknown;
    if (parsed && typeof parsed === "object" && "detail" in parsed) {
      const detail = (parsed as { detail: unknown }).detail;
      if (typeof detail === "string") return detail;
      return JSON.stringify(detail);
    }
  } catch {
    // not JSON; fall through to raw text
  }
  return raw.slice(0, 300);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${CONVERSATION_API_BASE}${path}`, {
      cache: "no-store",
      ...init,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (cause) {
    throw new ConversationApiError(
      0,
      "network-error",
      `无法连接 Kronos 服务（网络错误）：${cause instanceof Error ? cause.message : String(cause)}`,
    );
  }
  if (!response.ok) {
    throw new ConversationApiError(response.status, await parseErrorDetail(response));
  }
  return (await response.json()) as T;
}

// ----------------------------------------------------------------- endpoints

export function createConversation(): Promise<ConversationCreated> {
  return request<ConversationCreated>("/conversations", { method: "POST" });
}

/** Submit one user turn; the backend answers 202 with the turn result. */
export function sendMessage(sessionId: string, text: string): Promise<MessageResult> {
  return request<MessageResult>(`/conversations/${encodeURIComponent(sessionId)}/messages`, {
    method: "POST",
    body: JSON.stringify({ text }),
  });
}

export function getConversation(sessionId: string): Promise<SessionDetail> {
  return request<SessionDetail>(`/conversations/${encodeURIComponent(sessionId)}`);
}

export function getRun(taskId: string): Promise<RunStatus> {
  return request<RunStatus>(`/runs/${encodeURIComponent(taskId)}`);
}

/** Incremental event page: only events with ``seq > afterSeq``. */
export function getRunEvents(taskId: string, afterSeq: number): Promise<RunEvents> {
  return request<RunEvents>(
    `/runs/${encodeURIComponent(taskId)}/events?after_seq=${Number.isFinite(afterSeq) ? afterSeq : 0}`,
  );
}

/**
 * First step of the two-step cancel. From ``queued`` the task goes straight
 * to ``cancelled``; from ``running`` it returns ``cancel_requested`` and the
 * worker confirms the stop later. 409 means the state no longer allows it.
 */
export function cancelRun(taskId: string): Promise<RunStatus> {
  return request<RunStatus>(`/runs/${encodeURIComponent(taskId)}/cancel`, { method: "POST" });
}

export function getVerdict(runId: string): Promise<Verdict> {
  return request<Verdict>(`/verdicts/${encodeURIComponent(runId)}`);
}
