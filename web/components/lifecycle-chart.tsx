"use client";

import { BarChart } from "echarts/charts";
import { GridComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import { CanvasRenderer } from "echarts/renderers";
import { useEffect, useMemo, useRef } from "react";

import type { CandidateListItem } from "@/lib/api";

echarts.use([BarChart, GridComponent, TooltipComponent, CanvasRenderer]);

type LifecycleChartProps = {
  candidates: CandidateListItem[];
};

export function LifecycleChart({ candidates }: LifecycleChartProps) {
  const chartRef = useRef<HTMLDivElement | null>(null);

  const lifecycleData = useMemo(() => {
    const counts = new Map<string, number>();
    for (const c of candidates) {
      const label = c.status_label_zh || "未知";
      counts.set(label, (counts.get(label) ?? 0) + 1);
    }
    return Array.from(counts.entries())
      .map(([label, count]) => ({ label, count }))
      .sort((a, b) => b.count - a.count);
  }, [candidates]);

  useEffect(() => {
    if (!chartRef.current || lifecycleData.length === 0) return;

    const chart = echarts.init(chartRef.current);
    chart.setOption({
      color: ["#0f766e", "#2563eb", "#b45309", "#475569", "#dc2626"],
      tooltip: {
        trigger: "axis",
        formatter: (params: unknown) => {
          const rows = Array.isArray(params) ? params : [params];
          return rows
            .map((r) => {
              const row = r as { name?: string; value?: string | number };
              return `${row.name ?? ""}<br/>候选数：${row.value ?? 0}`;
            })
            .join("<br/>");
        },
      },
      grid: { left: 24, right: 12, top: 24, bottom: 52 },
      xAxis: {
        type: "category",
        data: lifecycleData.map((d) => d.label),
        axisLabel: { color: "#64748b", interval: 0, rotate: 22 },
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
          type: "bar",
          data: lifecycleData.map((d) => d.count),
          barMaxWidth: 34,
          itemStyle: { borderRadius: [4, 4, 0, 0] },
        },
      ],
    });

    const onResize = () => chart.resize();
    window.addEventListener("resize", onResize);
    return () => {
      window.removeEventListener("resize", onResize);
      chart.dispose();
    };
  }, [lifecycleData]);

  if (lifecycleData.length === 0) return null;

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-950">候选生命周期分布</h2>
      <p className="mt-1 text-xs text-slate-500">
        {candidates.length} 个候选策略的当前研究阶段分布
      </p>
      <div className="mt-3 h-[200px]">
        <div ref={chartRef} className="h-full w-full" />
      </div>
    </section>
  );
}
