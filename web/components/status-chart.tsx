"use client";

import { BarChart, PieChart } from "echarts/charts";
import { GridComponent, LegendComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import type { CandidateListItem } from "@/lib/api";
import { compactLabel } from "@/lib/utils";

echarts.use([BarChart, PieChart, GridComponent, LegendComponent, TooltipComponent, CanvasRenderer]);

type StatusChartProps = {
  candidates: CandidateListItem[];
};

export function StatusChart({ candidates }: StatusChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const familyRows = useMemo(() => {
    const counts = new Map<string, number>();
    for (const candidate of candidates) {
      counts.set(candidate.family, (counts.get(candidate.family) ?? 0) + 1);
    }
    return Array.from(counts.entries()).map(([family, count]) => ({
      family: compactLabel(family),
      count,
    }));
  }, [candidates]);
  const strongestFamily = familyRows
    .slice()
    .sort((left, right) => right.count - left.count)[0];
  const highPriorityCount = candidates.filter((candidate) => candidate.migration_rank <= 3).length;

  useEffect(() => {
    if (!chartRef.current) {
      return undefined;
    }
    const chart = echarts.init(chartRef.current);
    chart.setOption({
      color: ["#0f766e", "#2563eb", "#b45309", "#475569"],
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const rows = Array.isArray(params) ? params : [params];
          return rows
            .map((item) => {
              const row = item as { name?: string; value?: string | number };
              return `${row.name ?? ""}<br/>候选数：${row.value ?? 0}`;
            })
            .join("<br/>");
        },
      },
      grid: {
        left: 24,
        right: 12,
        top: 24,
        bottom: 52,
      },
      xAxis: {
        type: "category",
        data: familyRows.map((row) => row.family),
        axisLabel: {
          color: "#64748b",
          interval: 0,
          rotate: 22,
        },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
        axisTick: { show: false },
      },
      yAxis: {
        type: "value",
        minInterval: 1,
        axisLabel: { color: "#64748b" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      series: [
        {
          name: "候选数",
          type: "bar",
          data: familyRows.map((row) => row.count),
          barMaxWidth: 34,
          itemStyle: {
            borderRadius: [4, 4, 0, 0],
          },
        },
      ],
    });

    const handleResize = () => chart.resize();
    window.addEventListener("resize", handleResize);
    return () => {
      window.removeEventListener("resize", handleResize);
      chart.dispose();
    };
  }, [familyRows]);

  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-sm font-semibold text-slate-950">候选池洞察</h2>
        <p className="mt-1 text-xs text-slate-500">用来判断研究资源应该先放在哪里</p>
      </div>
      <div className="grid gap-3 p-4">
        <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-1 2xl:grid-cols-3">
          <Insight label="优先候选" value={`${highPriorityCount}`} hint="迁移排名前 3，优先补专项证据" />
          <Insight
            label="集中族群"
            value={strongestFamily?.family ?? "暂无"}
            hint={strongestFamily ? `${strongestFamily.count} 个候选集中在这里` : "等待候选导入"}
          />
          <Insight label="共同缺口" value="专项验证" hint="当前候选都需要 crypto 市场证据" />
        </div>
      </div>
      <div className="h-[240px] px-2 pb-3">
        <div ref={chartRef} className="h-full w-full" />
      </div>
    </section>
  );
}

function Insight({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-semibold text-slate-950">{value}</div>
      <p className="mt-1 text-xs leading-5 text-slate-500">{hint}</p>
    </div>
  );
}
