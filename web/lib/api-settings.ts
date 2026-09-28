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
import { withLocalToken } from "@/lib/api-headers";

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
  // P19 本地安全边界：写请求需携带本地会话令牌；连通性测试虽是 GET，
  // 但有付费副作用，后端要求令牌头，因此 safeMethods 也附加。
  const secured = await withLocalToken(API_BASE, init, { safeMethods: true });
  const response = await fetch(`${API_BASE}${path}`, {
    ...secured,
    headers: {
      "Content-Type": "application/json",
      ...(secured?.headers ?? {}),
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
  // P19：Key 保存是写请求，改走 settingsFetch 以携带本地会话令牌头
  // （原 kronosApi.updateProviderSecret 不经过共享令牌助手）。
  updateProviderSecret: (provider: string, apiKey: string) =>
    settingsFetch<ProviderSecretStatus>(
      `/settings/llm/providers/${encodeURIComponent(provider)}/secret`,
      {
        method: "PUT",
        body: JSON.stringify({ api_key: apiKey }),
      },
    ),
  probeProvider: (provider: string) =>
    settingsFetch<ProviderProbe>(
      `/settings/llm/providers/${encodeURIComponent(provider)}/probe`,
    ),
  systemPaths: () => settingsFetch<SystemPaths>("/settings/system"),
};
