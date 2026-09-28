"use client";

import { useQuery } from "@tanstack/react-query";

import { settingsApi, type SystemPaths } from "@/lib/api-settings";

const PATH_ROWS: { key: keyof SystemPaths; label_zh: string }[] = [
  { key: "state_dir", label_zh: "运行状态目录（会话 / 任务 / 预算账本）" },
  { key: "data_dir", label_zh: "行情数据目录" },
  { key: "snapshots_dir", label_zh: "数据快照目录" },
  { key: "freqtrade_venv", label_zh: "freqtrade 虚拟环境" },
];

/** 数据路径卡：只读展示本地路径，不包含任何密钥。 */
export function DataPathsCard() {
  const pathsQuery = useQuery({
    queryKey: ["settings-system-paths"],
    queryFn: settingsApi.systemPaths,
  });

  if (pathsQuery.isLoading) {
    return <div className="h-24 animate-pulse rounded border border-slate-200 bg-slate-100" />;
  }
  if (pathsQuery.isError || !pathsQuery.data) {
    return (
      <p className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
        无法读取本地路径，请确认本地后端（kronos web）已启动。
      </p>
    );
  }

  const paths = pathsQuery.data;
  return (
    <div className="grid gap-2">
      <dl className="grid gap-2">
        {PATH_ROWS.map((row) => (
          <div
            className="grid gap-1 rounded border border-slate-200 bg-slate-50 px-3 py-2 sm:grid-cols-[minmax(0,16rem)_minmax(0,1fr)] sm:gap-3"
            key={row.key}
          >
            <dt className="text-xs font-medium text-slate-600">{row.label_zh}</dt>
            <dd className="break-all font-mono text-xs text-slate-800">{paths[row.key]}</dd>
          </div>
        ))}
      </dl>
      <p className="text-xs leading-5 text-slate-500">路径为只读展示；行情数据属于运行时状态，不纳入版本管理。</p>
    </div>
  );
}
