"use client";

import { useQuery } from "@tanstack/react-query";
import { Coins, Database, KeyRound } from "lucide-react";
import type { ReactNode } from "react";

import { BudgetSettingsCard } from "@/components/settings/budget-settings-card";
import { DataPathsCard } from "@/components/settings/data-paths-card";
import { FirstRunBanner } from "@/components/settings/first-run-banner";
import { ModelSettingsCard } from "@/components/settings/model-settings-card";
import { settingsApi } from "@/lib/api-settings";

/** 设置页主体：首启横幅 + 模型 / 预算 / 数据路径三个分区。 */
export function SettingsView() {
  const settingsQuery = useQuery({
    queryKey: ["settings-llm"],
    queryFn: settingsApi.llmSettings,
  });
  const glmProvider = settingsQuery.data?.providers.find(
    (provider) => provider.provider === "glm",
  );
  const keyConfigured = Boolean(glmProvider?.configured);

  return (
    <div className="grid min-w-0 gap-4">
      <FirstRunBanner visible={!keyConfigured} />
      <section
        aria-labelledby="settings-model-title"
        className="rounded-lg border border-slate-200 bg-white p-4"
        id="model"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-2 text-base font-semibold text-slate-950" id="settings-model-title">
            <KeyRound className="h-4 w-4 text-teal-700" />
            模型
          </h2>
          <span
            className={`rounded border px-2 py-0.5 text-xs ${
              keyConfigured
                ? "border-teal-100 bg-teal-50 text-teal-800"
                : "border-amber-200 bg-amber-50 text-amber-800"
            }`}
          >
            {keyConfigured ? "已配置" : "待配置"}
          </span>
        </div>
        <p className="mb-3 mt-2 max-w-3xl break-words text-sm leading-6 text-slate-500">
          对话与研究使用 GLM（智谱）模型；保存 Key 后即可开始对话，对话页的确定性路径不依赖模型 Key。
        </p>
        <ModelSettingsCard />
      </section>

      <SettingsSection
        badge="默认值（用量待接线）"
        description="LLM 调用、Token、回测与墙钟预算采用预留制且不可绕过；当前展示系统默认上限，用量统计接口将在后续版本接入。"
        icon={<Coins className="h-4 w-4 text-teal-700" />}
        id="budget"
        title="预算"
      >
        <BudgetSettingsCard />
      </SettingsSection>

      <SettingsSection
        badge="只读"
        description="本地行情数据与运行状态目录一览，均从本地后端读取，不包含任何密钥。"
        icon={<Database className="h-4 w-4 text-teal-700" />}
        id="data-paths"
        title="数据路径"
      >
        <DataPathsCard />
      </SettingsSection>
    </div>
  );
}

function SettingsSection({
  id,
  title,
  badge,
  description,
  icon,
  children,
}: {
  id: string;
  title: string;
  badge: string;
  description: string;
  icon: ReactNode;
  children: ReactNode;
}) {
  return (
    <section aria-labelledby={`settings-${id}-title`} className="rounded-lg border border-slate-200 bg-white p-4" id={id}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="flex items-center gap-2 text-base font-semibold text-slate-950" id={`settings-${id}-title`}>
          {icon}
          {title}
        </h2>
        <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
          {badge}
        </span>
      </div>
      <p className="mb-3 mt-2 max-w-3xl break-words text-sm leading-6 text-slate-500">{description}</p>
      {children}
    </section>
  );
}
