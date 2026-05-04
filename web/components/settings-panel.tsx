"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, KeyRound, RefreshCw, Save, Shield } from "lucide-react";
import { useState } from "react";

import { kronosApi } from "@/lib/api";
import { compactLabel } from "@/lib/utils";

export function SettingsPanel() {
  const queryClient = useQueryClient();
  const settingsQuery = useQuery({
    queryKey: ["llm-settings"],
    queryFn: kronosApi.llmSettings,
  });
  const [apiKey, setApiKey] = useState("");
  const [saveNote, setSaveNote] = useState<string | null>(null);
  const provider = settingsQuery.data?.providers[0];
  const providerName = provider?.provider ?? "deepseek";
  const providerStatusQuery = useQuery({
    queryKey: ["llm-provider-status", providerName],
    queryFn: () => kronosApi.providerStatus(providerName),
  });

  const secretMutation = useMutation({
    mutationFn: () => kronosApi.updateProviderSecret(providerName, apiKey),
    onSuccess: async () => {
      setApiKey("");
      setSaveNote("API Key 已保存为本地密文状态，界面只显示脱敏结果。");
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["llm-settings"] }),
        queryClient.invalidateQueries({ queryKey: ["llm-provider-status", providerName] }),
      ]);
    },
  });
  const readiness = providerStatusQuery.data;
  const providerConfigured = Boolean(readiness?.configured ?? provider?.configured);

  return (
    <div className="grid gap-4">
      <div className="rounded border border-slate-200 bg-slate-50 p-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
              <KeyRound className="h-4 w-4 text-teal-700" />
              DeepSeek 启动配置
            </div>
            <p className="mt-1 break-words text-xs leading-5 text-slate-500">
              角色和 Prompt 模板已经准备好；只有保存 API Key 后，新的多角色 LLM 研究才会真正调用模型。
            </p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`rounded border px-2.5 py-1 text-xs ${
                providerConfigured
                  ? "border-teal-100 bg-teal-50 text-teal-800"
                  : "border-amber-200 bg-amber-50 text-amber-800"
              }`}
            >
              {readiness?.message_zh ?? "读取配置中"}
            </span>
            <button
              type="button"
              className="inline-flex h-8 w-8 items-center justify-center rounded border border-slate-200 bg-white text-slate-600 transition hover:border-teal-200 hover:text-teal-700 disabled:opacity-50"
              title="刷新配置状态"
              disabled={providerStatusQuery.isFetching}
              onClick={() => void providerStatusQuery.refetch()}
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </div>

        <form
          className="mt-3 grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            secretMutation.mutate();
          }}
        >
          <label className="min-w-0">
            <span className="mb-1 block text-xs font-medium text-slate-600">API Key</span>
            <input
              className="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              type="password"
              autoComplete="new-password"
              value={apiKey}
              placeholder={provider?.masked_value ?? "sk-..."}
              onChange={(event) => setApiKey(event.target.value)}
            />
          </label>
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:bg-slate-300"
            type="submit"
            disabled={!apiKey || secretMutation.isPending}
          >
            <Save className="h-4 w-4" />
            保存
          </button>
        </form>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs">
          <span className="inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
            <EyeOff className="h-3.5 w-3.5" />
            {readiness?.masked_api_key ?? provider?.masked_value ?? "尚未配置"}
          </span>
          <span className="rounded border border-slate-200 bg-white px-2.5 py-1 text-slate-600">
            {readiness?.base_url ?? provider?.storage_backend ?? "local"}
          </span>
          {saveNote ? <span className="text-teal-700">{saveNote}</span> : null}
          {secretMutation.isError ? (
            <span className="text-red-700">保存失败，请确认本地 API 正常运行。</span>
          ) : null}
        </div>
      </div>

      <div>
        <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-slate-900">
          <Shield className="h-4 w-4 text-sky-700" />
          Agent 角色与 Prompt 版本
        </div>
        {settingsQuery.isLoading ? (
          <div className="h-36 animate-pulse rounded border border-slate-200 bg-slate-100" />
        ) : settingsQuery.isError ? (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            无法读取角色配置。
          </div>
        ) : (
          <div className="overflow-x-auto rounded border border-slate-200">
            <table className="min-w-[680px] table-fixed text-left text-sm">
              <thead className="bg-slate-50 text-xs font-semibold uppercase text-slate-500">
                <tr>
                  <th className="px-3 py-2">角色</th>
                  <th className="px-3 py-2">定位</th>
                  <th className="px-3 py-2">Prompt 版本</th>
                  <th className="px-3 py-2">模型</th>
                  <th className="px-3 py-2">状态</th>
                </tr>
              </thead>
              <tbody>
                {settingsQuery.data?.roles.map((role) => (
                  <tr key={role.role_id} className="border-t border-slate-200">
                    <td className="px-3 py-2 font-medium text-slate-900">{role.name_zh}</td>
                    <td className="px-3 py-2 text-slate-600">{compactLabel(role.role_kind)}</td>
                    <td className="px-3 py-2">
                      <code className="rounded bg-slate-100 px-2 py-1 text-xs">
                        {role.prompt_version}
                      </code>
                    </td>
                    <td className="px-3 py-2 text-slate-600">
                      {role.model_provider}/
                      {role.model_name === "configured-in-settings" ? "由设置页决定" : role.model_name}
                    </td>
                    <td className="px-3 py-2">
                      <span
                        className={`rounded border px-2 py-1 text-xs ${
                          role.enabled && providerConfigured
                            ? "border-teal-100 bg-teal-50 text-teal-800"
                            : "border-slate-200 bg-slate-50 text-slate-600"
                        }`}
                      >
                        {role.enabled && providerConfigured
                          ? "可调用"
                          : role.enabled
                            ? "模板启用，待模型配置"
                            : "停用"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
