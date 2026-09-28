import { Coins, Database, KeyRound, Settings } from "lucide-react";
import type { ReactNode } from "react";

import { AppShell } from "@/components/app-shell";

/**
 * 设置页外壳（占位骨架）。
 * 只提供「模型 / 预算 / 数据路径」三个分区的标签与说明，不含任何逻辑或请求；
 * 模型 Key 配置走后端 SecretStore，由 P18 接入。
 */
export default function SettingsPage() {
  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600">
            <Settings className="h-3.5 w-3.5" />
            设置
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">设置</h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            模型、预算与本地数据路径集中在这里管理。
          </p>
        </header>

        <div className="grid min-w-0 gap-4">
          {SETTINGS_SECTIONS.map((section) => (
            <section
              className="rounded-lg border border-slate-200 bg-white p-4"
              key={section.key}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h2 className="flex items-center gap-2 text-base font-semibold text-slate-950">
                  {section.icon}
                  {section.title}
                </h2>
                <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-500">
                  {section.badge}
                </span>
              </div>
              <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-500">
                {section.description}
              </p>
            </section>
          ))}
        </div>
      </div>
    </AppShell>
  );
}

type SettingsSection = {
  key: string;
  title: string;
  badge: string;
  description: string;
  icon: ReactNode;
};

const SETTINGS_SECTIONS: SettingsSection[] = [
  {
    key: "model",
    title: "模型",
    badge: "待接入",
    description:
      "模型 API Key 通过本地后端 SecretStore 安全存储，密钥不会进入前端页面或浏览器存储。配置表单将在后续版本提供。",
    icon: <KeyRound className="h-4 w-4 text-teal-700" />,
  },
  {
    key: "budget",
    title: "预算",
    badge: "待接入",
    description: "LLM 调用预算上限与用量统计将在后续版本提供。",
    icon: <Coins className="h-4 w-4 text-teal-700" />,
  },
  {
    key: "data-paths",
    title: "数据路径",
    badge: "待接入",
    description: "本地行情数据目录与回测数据范围配置将在后续版本提供。",
    icon: <Database className="h-4 w-4 text-teal-700" />,
  },
];
