"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText } from "lucide-react";
import type { ReactNode } from "react";

import { kronosApi } from "@/lib/api";

type ReportReaderPanelProps = {
  mode?: "agent" | "paper";
  runId: string;
  onClose?: () => void;
};

export function ReportReaderPanel({ mode = "agent", runId, onClose }: ReportReaderPanelProps) {
  const reportQuery = useQuery({
    queryKey: [mode === "paper" ? "paper-run-report" : "agent-run-report", runId],
    queryFn: () => (mode === "paper" ? kronosApi.paperRunReport(runId) : kronosApi.agentRunReport(runId)),
    retry: 1,
    enabled: mode === "agent" || runId !== "latest",
  });
  const readableReport = reportQuery.data ? makeReadableReport(reportQuery.data.content_md) : null;
  const isPaper = mode === "paper";

  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-4 sm:px-5">
        <div className="min-w-0">
          <div className="mb-2 inline-flex items-center gap-2 rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            <FileText className="h-3.5 w-3.5" />
            {isPaper ? "测试网模拟盘报告" : "本轮研究报告"}
          </div>
          <h2 className="break-words text-xl font-semibold text-slate-950">
            {reportQuery.data?.title_zh ?? (isPaper ? "测试网模拟盘报告" : "Agent 研究报告")}
          </h2>
          <p className="mt-1 break-all text-xs text-slate-500">
            {isPaper ? "paper run" : "批次"}：{runId}
          </p>
        </div>
        {onClose ? (
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
            type="button"
            onClick={onClose}
          >
            <ArrowLeft className="h-4 w-4" />
            关闭报告
          </button>
        ) : null}
      </div>

      <div className="p-4 sm:p-5">
        {reportQuery.isLoading ? (
          <div className="grid gap-3">
            <div className="h-8 animate-pulse rounded bg-slate-100" />
            <div className="h-32 animate-pulse rounded bg-slate-100" />
            <div className="h-20 animate-pulse rounded bg-slate-100" />
          </div>
        ) : reportQuery.isError || !reportQuery.data ? (
          <div className="rounded border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
            {isPaper
              ? "当前还没有可阅读的测试网模拟盘报告。完成一次 paper run 后，这里会显示订单、成交和边界说明。"
              : "当前批次还没有可阅读报告。完成一轮 Agent 研究后，这里会直接显示报告正文，而不是只显示文件路径。"}
          </div>
        ) : (
          <div className="grid gap-4">
            <ReportHighlights content={reportQuery.data.content_md} />
            <MarkdownLite content={readableReport?.contentMd ?? ""} />
            <details className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
              <summary className="cursor-pointer font-semibold text-slate-700">技术路径</summary>
              <code className="mt-2 block break-all rounded bg-white p-2">
                {reportQuery.data.report_path}
              </code>
              {readableReport && readableReport.technicalLines.length > 0 ? (
                <div className="mt-2 grid gap-1 rounded bg-white p-2">
                  {readableReport.technicalLines.map((line, index) => (
                    <code key={`${line}-${index}`} className="break-all">
                      {line.replace(/^- /, "")}
                    </code>
                  ))}
                </div>
              ) : null}
            </details>
          </div>
        )}
      </div>
    </section>
  );
}

function ReportHighlights({ content }: { content: string }) {
  const highlights = extractHighlights(content);
  if (highlights.length === 0) {
    return null;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {highlights.map((item) => (
        <div key={item.label} className="rounded border border-slate-200 bg-slate-50 p-3">
          <div className="text-xs font-semibold text-slate-500">{item.label}</div>
          <div className="mt-1 text-sm leading-6 text-slate-900">{item.value}</div>
        </div>
      ))}
    </div>
  );
}

function extractHighlights(content: string) {
  const labels = new Map([
    ["当前研究目标", "正在研究"],
    ["当前结论", "本轮结论"],
    ["下一步动作", "建议动作"],
    ["是否需要审批", "人工审批"],
  ]);
  const result: Array<{ label: string; value: string }> = [];

  content.split(/\r?\n/).forEach((line) => {
    const match = /^-\s*([^：:]+)[：:]\s*(.+)$/.exec(line.trim());
    if (!match) {
      return;
    }
    const label = labels.get(match[1]);
    if (label) {
      result.push({ label, value: match[2] });
    }
  });

  return result;
}

function makeReadableReport(content: string) {
  const readableLines: string[] = [];
  const technicalLines: string[] = [];
  let skippingArtifacts = false;

  content.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("# ")) {
      return;
    }
    if (trimmed.startsWith("## 产物")) {
      skippingArtifacts = true;
      technicalLines.push(trimmed);
      return;
    }
    if (skippingArtifacts && trimmed.startsWith("## ")) {
      skippingArtifacts = false;
    }
    if (skippingArtifacts) {
      if (trimmed) {
        technicalLines.push(trimmed);
      }
      return;
    }
    if (trimmed.startsWith("- 关键证据：") || trimmed.startsWith("- 关键证据:")) {
      technicalLines.push(trimmed);
      return;
    }
    readableLines.push(line);
  });

  return { contentMd: readableLines.join("\n").trim(), technicalLines };
}

function MarkdownLite({ content }: { content: string }) {
  const nodes: ReactNode[] = [];
  const codeBuffer: string[] = [];
  let inCode = false;
  let codeIndex = 0;

  const flushCode = () => {
    if (codeBuffer.length === 0) {
      return;
    }
    nodes.push(
      <pre
        key={`code-${codeIndex}`}
        className="overflow-x-auto rounded border border-slate-200 bg-slate-950 p-3 text-xs leading-6 text-slate-100"
      >
        {codeBuffer.join("\n")}
      </pre>,
    );
    codeIndex += 1;
    codeBuffer.length = 0;
  };

  content.split(/\r?\n/).forEach((line, index) => {
    if (line.trim().startsWith("```")) {
      if (inCode) {
        flushCode();
      }
      inCode = !inCode;
      return;
    }
    if (inCode) {
      codeBuffer.push(line);
      return;
    }

    const trimmed = line.trim();
    if (!trimmed) {
      nodes.push(<div key={`space-${index}`} className="h-2" />);
      return;
    }
    if (trimmed.startsWith("### ")) {
      nodes.push(
        <h4 key={index} className="pt-3 text-base font-semibold text-slate-900">
          {trimmed.slice(4)}
        </h4>,
      );
      return;
    }
    if (trimmed.startsWith("## ")) {
      nodes.push(
        <h3 key={index} className="pt-4 text-lg font-semibold text-slate-950">
          {trimmed.slice(3)}
        </h3>,
      );
      return;
    }
    if (trimmed.startsWith("# ")) {
      nodes.push(
        <h2 key={index} className="text-xl font-semibold text-slate-950">
          {trimmed.slice(2)}
        </h2>,
      );
      return;
    }
    if (trimmed.startsWith("- ")) {
      nodes.push(
        <div key={index} className="grid grid-cols-[18px_minmax(0,1fr)] gap-2 text-sm leading-7 text-slate-700">
          <span className="pt-0.5 text-teal-700">•</span>
          <p className="break-words">{trimmed.slice(2)}</p>
        </div>,
      );
      return;
    }
    nodes.push(
      <p key={index} className="break-words text-sm leading-7 text-slate-700">
        {trimmed}
      </p>,
    );
  });

  flushCode();

  return <article className="grid max-w-4xl gap-1">{nodes}</article>;
}
