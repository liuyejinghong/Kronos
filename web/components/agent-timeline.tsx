"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, CheckCircle2, CircleAlert, Clock3, FileText, Radio } from "lucide-react";
import { useEffect, useState } from "react";

import {
  agentEventStreamUrl,
  kronosApi,
  type AgentEvent,
  type ArtifactRef,
} from "@/lib/api";
import { cn, compactLabel } from "@/lib/utils";

const eventTypes = [
  "run_created",
  "run_started",
  "run_completed",
  "run_failed",
  "task_queued",
  "task_started",
  "task_completed",
  "task_failed",
  "material_intake",
  "hypothesis_generated",
  "experiment_planned",
  "tool_execution_started",
  "tool_execution_completed",
  "tool_execution_failed",
  "agent_analysis_completed",
  "committee_scoring_completed",
  "candidate_state_changed",
  "approval_requested",
  "approval_resolved",
  "error_reported",
];

type AgentTimelineProps = {
  runId: string;
};

export function AgentTimeline({ runId }: AgentTimelineProps) {
  const eventsQuery = useQuery({
    queryKey: ["agent-events", runId],
    queryFn: () => kronosApi.agentEvents(runId),
  });
  const [streamState, setStreamState] = useState<{ runId: string; events: AgentEvent[]; closed: boolean }>({
    runId,
    events: [],
    closed: false,
  });

  useEffect(() => {
    if (!runId || typeof window === "undefined") {
      return undefined;
    }
    const source = new EventSource(agentEventStreamUrl(runId));
    const handleEvent = (event: MessageEvent<string>) => {
      const nextEvent = JSON.parse(event.data) as AgentEvent;
      setStreamState((current) => {
        const currentEvents = current.runId === runId ? current.events : [];
        const byId = new Map(currentEvents.map((item) => [item.event_id, item]));
        byId.set(nextEvent.event_id, nextEvent);
        return { runId, events: Array.from(byId.values()), closed: false };
      });
    };
    for (const eventType of eventTypes) {
      source.addEventListener(eventType, handleEvent);
    }
    source.onerror = () => {
      source.close();
      setStreamState((current) => ({ ...current, closed: true }));
    };
    return () => {
      for (const eventType of eventTypes) {
        source.removeEventListener(eventType, handleEvent);
      }
      source.close();
    };
  }, [runId]);

  const streamEvents = streamState.runId === runId ? streamState.events : [];
  const displayedEvents = mergeEvents(eventsQuery.data ?? [], streamEvents);

  return (
    <section id="timeline" className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-950">Agent 时间线</h2>
          <p className="mt-1 break-words text-xs text-slate-500">批次：{runId}</p>
        </div>
        <div className="inline-flex items-center gap-2 rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
          <Radio className="h-3.5 w-3.5 text-teal-700" />
          {streamState.closed ? "使用最近事件" : "事件通道已连接"}
        </div>
      </div>

      <div className="max-h-[520px] overflow-y-auto p-4">
        {eventsQuery.isLoading ? (
          <TimelineSkeleton />
        ) : eventsQuery.isError ? (
          <div className="rounded border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            没有找到这个运行批次的事件流。请确认后端运行目录里已有 Agent 事件。
          </div>
        ) : displayedEvents.length === 0 ? (
          <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm leading-6 text-slate-500">
            Agent 暂无事件。导入材料或启动一次研究闭环后，这里会显示每一步动作和产物。
          </div>
        ) : (
          <ol className="grid gap-3">
            {displayedEvents.map((event) => (
              <TimelineItem key={event.event_id} event={event} />
            ))}
          </ol>
        )}
      </div>
    </section>
  );
}

function mergeEvents(baseEvents: AgentEvent[], streamEvents: AgentEvent[]) {
  const byId = new Map(baseEvents.map((event) => [event.event_id, event]));
  for (const event of streamEvents) {
    byId.set(event.event_id, event);
  }
  return Array.from(byId.values());
}

function TimelineItem({ event }: { event: AgentEvent }) {
  return (
    <li className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
      <div className="pt-1">{iconForEvent(event)}</div>
      <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className={cn("rounded px-2 py-0.5 text-xs font-semibold", levelClass(event.level))}>
            {levelLabel(event.level)}
          </span>
          <span className="rounded bg-white px-2 py-0.5 text-xs text-slate-500">
            {eventTypeLabel(event.event_type)}
          </span>
          <span className="text-xs text-slate-500">{compactLabel(event.status)}</span>
        </div>
        <p className="mt-2 break-words text-sm leading-6 text-slate-800">{event.message_zh}</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
          {event.role_id ? <span>角色：{event.role_id}</span> : null}
          {event.prompt_version ? <span>Prompt：{event.prompt_version}</span> : null}
          {event.model_provider ? <span>模型：{event.model_provider}/{event.model_name}</span> : null}
        </div>
        {event.artifact_paths.length > 0 ? (
          <ArtifactList artifacts={event.artifact_paths} />
        ) : null}
      </div>
    </li>
  );
}

function ArtifactList({ artifacts }: { artifacts: ArtifactRef[] }) {
  return (
    <div className="mt-3 grid gap-2">
      {artifacts.map((artifact) => (
        <details
          key={artifact.path}
          className="min-w-0 rounded border border-slate-200 bg-white px-2.5 py-2 text-xs text-slate-600"
        >
          <summary className="flex cursor-pointer items-center gap-2">
            <FileText className="h-3.5 w-3.5 shrink-0 text-slate-500" />
            <span className="shrink-0 rounded bg-slate-100 px-1.5 py-0.5 text-slate-500">
              {artifact.artifact_type}
            </span>
            <span className="min-w-0 truncate text-slate-700">
              {artifact.summary_zh ?? artifact.name}
            </span>
          </summary>
          <code className="mt-2 block break-all rounded bg-slate-50 p-2 text-slate-600">
            {artifact.path}
          </code>
        </details>
      ))}
    </div>
  );
}

function iconForEvent(event: AgentEvent) {
  if (event.level === "error") {
    return <CircleAlert className="h-5 w-5 text-red-700" />;
  }
  if (event.level === "warning" || event.level === "approval_required") {
    return <Clock3 className="h-5 w-5 text-amber-700" />;
  }
  if (event.status === "completed") {
    return <CheckCircle2 className="h-5 w-5 text-teal-700" />;
  }
  return <Activity className="h-5 w-5 text-sky-700" />;
}

function levelLabel(level: string) {
  const labels: Record<string, string> = {
    info: "信息",
    decision: "决策",
    warning: "警告",
    approval_required: "待审批",
    error: "错误",
  };
  return labels[level] ?? level;
}

function eventTypeLabel(eventType: string) {
  const labels: Record<string, string> = {
    run_created: "创建研究批次",
    run_started: "启动研究",
    run_completed: "完成研究",
    run_failed: "研究失败",
    task_queued: "加入队列",
    task_started: "开始任务",
    task_completed: "完成任务",
    task_failed: "任务失败",
    material_intake: "读取材料",
    hypothesis_generated: "提出假设",
    experiment_planned: "生成实验计划",
    tool_execution_started: "开始执行工具",
    tool_execution_completed: "完成工具执行",
    tool_execution_failed: "工具执行失败",
    agent_analysis_completed: "完成 Agent 分析",
    committee_scoring_completed: "完成投委会评分",
    candidate_state_changed: "候选状态变化",
    approval_requested: "请求人工审批",
    approval_resolved: "完成人工审批",
    error_reported: "记录错误报告",
  };
  return labels[eventType] ?? compactLabel(eventType);
}

function levelClass(level: string) {
  if (level === "error") {
    return "bg-red-100 text-red-800";
  }
  if (level === "warning" || level === "approval_required") {
    return "bg-amber-100 text-amber-800";
  }
  if (level === "decision") {
    return "bg-teal-100 text-teal-800";
  }
  return "bg-sky-100 text-sky-800";
}

function TimelineSkeleton() {
  return (
    <div className="grid gap-3">
      {Array.from({ length: 4 }).map((_, index) => (
        <div key={index} className="grid grid-cols-[28px_minmax(0,1fr)] gap-3">
          <div className="h-5 w-5 animate-pulse rounded-full bg-slate-200" />
          <div className="h-24 animate-pulse rounded border border-slate-200 bg-slate-100" />
        </div>
      ))}
    </div>
  );
}
