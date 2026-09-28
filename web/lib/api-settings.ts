/**
 * 设置页 API 层（P18）。
 *
 * 复用 lib/api.ts 的 API_BASE 与类型，补充设置页专用的三个数据源：
 * - GLM provider 掩码状态 / Key 保存 / 连通性测试（探测会消耗一次真实调用）；
 * - 本地系统路径（只读，无任何密钥）；
 * - 预算默认值（来自 kronos/runtime/budget.py 的 BudgetLimits 常量，
 *   用量接线接口尚未提供，前端只展示默认值，不构造假数据）。
 */
import {
  API_BASE,
  kronosApi,
  type LLMSettings,
  type ProviderReadiness,
  type ProviderSecretStatus,
} from "@/lib/api";

export type { LLMSettings, ProviderReadiness, ProviderSecretStatus };

export type ProviderProbe = {
  provider: string;
  configured: boolean;
  masked_api_key: string | null;
  base_url: string;
  model_name: string;
  reachable: boolean;
  latency_ms: number | null;
  message_zh: string;
};

export type SystemPaths = {
  state_dir: string;
  data_dir: string;
  snapshots_dir: string;
  freqtrade_venv: string;
};

/** 预算默认值，与 kronos/runtime/budget.py 的 BudgetLimits 保持一致。 */
export type BudgetLimitRow = {
  key: string;
  label_zh: string;
  value: string;
};

export const BUDGET_DEFAULT_ROWS: BudgetLimitRow[] = [
  { key: "llm_calls", label_zh: "LLM 调用次数", value: "每轮 3 次" },
  { key: "tokens_round", label_zh: "Token（每轮）", value: "16,000" },
  { key: "tokens_day", label_zh: "Token（近24小时滚动）", value: "100,000" },
  { key: "tokens_week", label_zh: "Token（近7天滚动）", value: "500,000" },
  { key: "backtests", label_zh: "回测次数", value: "每轮 40 次" },
  { key: "wall_clock", label_zh: "墙钟时间（每轮）", value: "1,800 秒" },
];

async function settingsFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Kronos settings request failed: ${response.status}`);
  }

  return (await response.json()) as T;
}

export const settingsApi = {
  llmSettings: kronosApi.llmSettings,
  providerStatus: kronosApi.providerStatus,
  updateProviderSecret: kronosApi.updateProviderSecret,
  probeProvider: (provider: string) =>
    settingsFetch<ProviderProbe>(
      `/settings/llm/providers/${encodeURIComponent(provider)}/probe`,
    ),
  systemPaths: () => settingsFetch<SystemPaths>("/settings/system"),
};
