export const API_BASE = process.env.NEXT_PUBLIC_KRONOS_API_BASE_URL ?? "/api/kronos";
export const DEFAULT_RUN_ID =
  process.env.NEXT_PUBLIC_KRONOS_DEFAULT_RUN_ID ?? "20260430-agent-mvp-delivery-v1";

export type HealthResponse = {
  status: string;
  service: string;
};

export type ArtifactRef = {
  name: string;
  path: string;
  artifact_type: string;
  summary_zh: string | null;
};

export type AgentRunStatus = {
  run_id: string;
  status: string;
  goal_zh: string;
  current_task_id: string | null;
  artifact_paths: ArtifactRef[];
};

export type AgentTaskStatus = {
  task_id: string;
  status: string;
  title_zh: string;
  candidate_id: string | null;
  lifecycle_state: string | null;
};

export type AgentEvent = {
  run_id: string;
  task_id: string;
  event_id: string;
  event_type: string;
  level: string;
  status: string;
  message_zh: string;
  candidate_id: string | null;
  role_id: string | null;
  prompt_version: string | null;
  model_provider: string | null;
  model_name: string | null;
  artifact_paths: ArtifactRef[];
};

export type AgentStatus = {
  active: boolean;
  pending_count: number;
  current_run: AgentRunStatus | null;
  current_task: AgentTaskStatus | null;
  last_event: AgentEvent | null;
};

export type AgentRunBrief = {
  run_id: string;
  status: string;
  goal_zh: string;
  conclusion_zh: string;
  next_action_zh: string;
  max_risk_zh: string | null;
  approval_required: boolean;
  support_reasons: string[];
  opposition_reasons: string[];
  evidence_count: number;
  event_count: number;
  artifact_paths: ArtifactRef[];
  report_path: string | null;
};

export type AgentRunReport = {
  run_id: string;
  title_zh: string;
  report_path: string;
  content_md: string;
};

export type CandidateListItem = {
  candidate_id: string;
  title_zh: string;
  family: string;
  origin: string;
  migration_rank: number;
  implementation_name: string | null;
  lifecycle_state: string | null;
  status_label_zh: string;
};

export type CandidateDetail = CandidateListItem & {
  source_strategies: string[];
  artifact_paths: ArtifactRef[];
  next_action_zh: string;
};

export type ProviderSecretStatus = {
  provider: string;
  configured: boolean;
  masked_value: string | null;
  storage_backend: string;
};

export type ProviderReadiness = {
  provider: string;
  status: string;
  configured: boolean;
  masked_api_key: string | null;
  base_url: string;
  model_name: string | null;
  message_zh: string;
};

export type RoleSettings = {
  role_id: string;
  role_kind: string;
  name_zh: string;
  enabled: boolean;
  prompt_version: string;
  model_provider: string;
  model_name: string;
};

export type LLMSettings = {
  providers: ProviderSecretStatus[];
  roles: RoleSettings[];
};

export type MaterialSourceType =
  | "legacy_strategy"
  | "candidate_note"
  | "failure_record"
  | "simulation_log"
  | "user_note";

export type MaterialImportPayload = {
  title_zh: string;
  content: string;
  source_type: MaterialSourceType;
  candidate_id: string | null;
  tags: string[];
};

export type MaterialImportResponse = {
  material_id: string;
  title_zh: string;
  source_type: MaterialSourceType;
  candidate_id: string | null;
  tags: string[];
  stored_at: string;
};

export type ApprovalItem = {
  approval_id: string;
  approval_type: string;
  title_zh: string;
  reason_zh: string;
  candidate_id: string | null;
  blocking: boolean;
  status: string;
};

export type ApprovalList = {
  items: ApprovalItem[];
};

export type ApprovalResolveResponse = {
  approval_id: string;
  approved: boolean;
  event_id: string;
  event_path: string;
};

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Kronos API request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export function agentEventStreamUrl(runId: string) {
  return `${API_BASE}/agent/events/stream?run_id=${encodeURIComponent(runId)}`;
}

export const kronosApi = {
  health: () => apiFetch<HealthResponse>("/health"),
  agentStatus: () => apiFetch<AgentStatus>("/agent/status"),
  candidates: () => apiFetch<CandidateListItem[]>("/candidates"),
  agentRunBrief: (runId: string) =>
    apiFetch<AgentRunBrief>(`/agent/runs/${encodeURIComponent(runId)}/summary`),
  agentRunReport: (runId: string) =>
    apiFetch<AgentRunReport>(`/agent/runs/${encodeURIComponent(runId)}/report`),
  candidateDetail: (candidateId: string) =>
    apiFetch<CandidateDetail>(`/candidates/${encodeURIComponent(candidateId)}`),
  agentEvents: (runId: string) =>
    apiFetch<AgentEvent[]>(`/agent/events?run_id=${encodeURIComponent(runId)}`),
  llmSettings: () => apiFetch<LLMSettings>("/settings/llm"),
  providerStatus: (provider: string) =>
    apiFetch<ProviderReadiness>(`/settings/llm/providers/${provider}/status`),
  updateProviderSecret: (provider: string, apiKey: string) =>
    apiFetch<ProviderSecretStatus>(`/settings/llm/providers/${provider}/secret`, {
      method: "PUT",
      body: JSON.stringify({ api_key: apiKey }),
    }),
  importMaterial: (payload: MaterialImportPayload) =>
    apiFetch<MaterialImportResponse>("/materials", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approvals: () => apiFetch<ApprovalList>("/approvals"),
  resolveApproval: (payload: {
    approvalId: string;
    runId: string;
    taskId: string;
    approved: boolean;
    reasonZh: string;
  }) =>
    apiFetch<ApprovalResolveResponse>(
      `/approvals/${encodeURIComponent(payload.approvalId)}/resolve`,
      {
        method: "POST",
        body: JSON.stringify({
          run_id: payload.runId,
          task_id: payload.taskId,
          approved: payload.approved,
          reason_zh: payload.reasonZh,
        }),
      },
    ),
};
