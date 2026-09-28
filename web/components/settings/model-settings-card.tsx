"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { EyeOff, KeyRound, RefreshCw, Save, ShieldCheck } from "lucide-react";
import { useState } from "react";

import { settingsApi } from "@/lib/api-settings";

/** GLM（智谱）模型配置卡：掩码状态 + Key 保存 + 连通性测试。 */
export function ModelSettingsCard() {
  const queryClient = useQueryClient();
  const [apiKey, setApiKey] = useState("");
  const [saveNote, setSaveNote] = useState<string | null>(null);

  const providerName = "glm";
  const statusQuery = useQuery({
    queryKey: ["settings-provider-status", providerName],
    queryFn: () => settingsApi.providerStatus(providerName),
  });
  const probeQuery = useQuery({
    queryKey: ["settings-provider-probe", providerName],
    queryFn: () => settingsApi.probeProvider(providerName),
    enabled: false,
  });

  const secretMutation = useMutation({
    mutationFn: () => settingsApi.updateProviderSecret(providerName, apiKey),
    onSuccess: async () => {
      setApiKey("");
      setSaveNote("Key 已保存到本地 SecretStore，界面只显示脱敏结果。");
      await queryClient.invalidateQueries({
        queryKey: ["settings-provider-status", providerName],
      });
    },
  });

  const readiness = statusQuery.data;
  const configured = Boolean(readiness?.configured);
  const probe = probeQuery.data;

  return (
    <div className="grid gap-3">
      <div className="flex flex-wrap items-center gap-2 text-xs">
        <span
          className={`inline-flex items-center gap-1 rounded border px-2.5 py-1 ${
            configured
              ? "border-teal-100 bg-teal-50 text-teal-800"
              : "border-amber-200 bg-amber-50 text-amber-800"
          }`}
        >
          <EyeOff className="h-3.5 w-3.5" />
          {readiness?.masked_api_key ?? "尚未配置"}
        </span>
        {readiness?.base_url ? (
          <span className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
            {readiness.base_url}
          </span>
        ) : null}
        {readiness?.model_name ? (
          <span className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-slate-600">
            {readiness.model_name}
          </span>
        ) : null}
        <button
          type="button"
          className="inline-flex h-7 w-7 items-center justify-center rounded border border-slate-200 bg-white text-slate-600 transition hover:border-teal-200 hover:text-teal-700 disabled:opacity-50"
          title="刷新状态"
          disabled={statusQuery.isFetching}
          onClick={() => void statusQuery.refetch()}
        >
          <RefreshCw className="h-3.5 w-3.5" />
        </button>
        {statusQuery.isLoading ? (
          <span className="text-slate-500">读取状态中…</span>
        ) : statusQuery.isError ? (
          <span className="text-red-700">无法读取模型状态，请确认本地后端已启动。</span>
        ) : (
          <span className="text-slate-600">{readiness?.message_zh}</span>
        )}
      </div>

      <form
        className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_auto]"
        onSubmit={(event) => {
          event.preventDefault();
          secretMutation.mutate();
        }}
      >
        <label className="min-w-0">
          <span className="mb-1 block text-xs font-medium text-slate-600">
            GLM API Key（保存后不会回显）
          </span>
          <input
            className="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none transition focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            type="password"
            autoComplete="new-password"
            value={apiKey}
            placeholder="粘贴智谱 API Key"
            onChange={(event) => setApiKey(event.target.value)}
          />
        </label>
        <button
          className="inline-flex h-10 items-center justify-center gap-2 self-end rounded bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:bg-slate-300"
          type="submit"
          disabled={!apiKey || secretMutation.isPending}
        >
          <Save className="h-4 w-4" />
          保存 Key
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-2 text-xs">
        <button
          type="button"
          className="inline-flex h-8 items-center justify-center gap-1.5 rounded border border-slate-300 bg-white px-3 font-medium text-slate-700 transition hover:border-teal-300 hover:text-teal-800 disabled:opacity-50"
          disabled={!configured || probeQuery.isFetching}
          onClick={() => void probeQuery.refetch()}
        >
          <ShieldCheck className="h-4 w-4" />
          连通性测试（消耗一次调用）
        </button>
        {probeQuery.isFetching ? <span className="text-slate-500">测试中…</span> : null}
        {probe ? (
          <span
            className={
              probe.reachable ? "text-teal-800" : "text-red-700"
            }
          >
            {probe.message_zh}
            {probe.latency_ms !== null ? `（${probe.latency_ms} ms）` : ""}
          </span>
        ) : null}
        {probeQuery.isError ? (
          <span className="text-red-700">连通性测试请求失败，请确认本地后端已启动。</span>
        ) : null}
        {saveNote ? <span className="text-teal-700">{saveNote}</span> : null}
        {secretMutation.isError ? (
          <span className="text-red-700">保存失败，请确认本地后端已启动。</span>
        ) : null}
      </div>

      <p className="flex items-start gap-1.5 text-xs leading-5 text-slate-500">
        <KeyRound className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        Key 只保存在本机 SecretStore，对话与回测请求从本地后端读取；页面与日志永远只显示掩码（末四位）。
      </p>
    </div>
  );
}
