"use client";

import * as Tabs from "@radix-ui/react-tabs";
import * as Tooltip from "@radix-ui/react-tooltip";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  CircleAlert,
  ClipboardList,
  Clock3,
  Database,
  FilePlus2,
  FileText,
  Gauge,
  GitBranch,
  KeyRound,
  ListChecks,
  PlayCircle,
  RefreshCw,
  ShieldAlert,
  SlidersHorizontal,
  Target,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { AgentMemoryPanel } from "@/components/agent-memory-panel";
import { AgentTimeline } from "@/components/agent-timeline";
import { ApprovalCenter } from "@/components/approval-center";
import { CandidateDetailPanel } from "@/components/candidate-detail-panel";
import { CandidateTable } from "@/components/candidate-table";
import { MaterialsPanel } from "@/components/materials-panel";
import { PaperStatusPanel } from "@/components/paper-status-panel";
import { ReportReaderPanel } from "@/components/report-reader";
import { RunBriefPanel } from "@/components/run-brief-panel";
import { SettingsPanel } from "@/components/settings-panel";
import { LifecycleChart } from "@/components/lifecycle-chart";
import { StatusChart } from "@/components/status-chart";
import {
  DEFAULT_RUN_ID,
  kronosApi,
  type AgentMemoryDashboard,
  type CandidateListItem,
  type PaperStatus,
} from "@/lib/api";
import { cn } from "@/lib/utils";

type WorkbenchView = "dashboard" | "memory" | "candidates" | "reports" | "timeline" | "operations";
type ReportMode = "agent" | "paper";
type OperationTab = "settings" | "materials" | "approvals";

export function WorkbenchApp() {
  const [activeView, setActiveView] = useState<WorkbenchView>("dashboard");
  const [reportMode, setReportMode] = useState<ReportMode>("agent");
  const [paperReportRunId, setPaperReportRunId] = useState<string | null>(null);
  const [activeOperationTab, setActiveOperationTab] = useState<OperationTab>("settings");
  const [selectedCandidateId, setSelectedCandidateId] = useState<string | null>(null);

  const healthQuery = useQuery({ queryKey: ["health"], queryFn: kronosApi.health });
  const statusQuery = useQuery({ queryKey: ["agent-status"], queryFn: kronosApi.agentStatus });
  const candidateQuery = useQuery({ queryKey: ["candidates"], queryFn: kronosApi.candidates });
  const settingsQuery = useQuery({ queryKey: ["llm-settings"], queryFn: kronosApi.llmSettings });
  const approvalsQuery = useQuery({ queryKey: ["approvals"], queryFn: kronosApi.approvals });
  const paperQuery = useQuery({ queryKey: ["paper-status"], queryFn: kronosApi.paperStatus });
  const memoryQuery = useQuery({ queryKey: ["agent-memory"], queryFn: kronosApi.agentMemory });

  const candidates = useMemo(() => candidateQuery.data ?? [], [candidateQuery.data]);
  const provider = settingsQuery.data?.providers[0];
  const providerConfigured = Boolean(provider?.configured);
  const currentRunId = statusQuery.data?.current_run?.run_id ?? DEFAULT_RUN_ID;
  const currentTaskId =
    statusQuery.data?.current_task?.task_id ??
    statusQuery.data?.current_run?.current_task_id ??
    "agent-cycle";
  const apiProblem =
    healthQuery.isError ||
    statusQuery.isError ||
    candidateQuery.isError ||
    settingsQuery.isError ||
    approvalsQuery.isError ||
    paperQuery.isError ||
    memoryQuery.isError;

  const visibleSelectedCandidateId =
    selectedCandidateId && candidates.some((candidate) => candidate.candidate_id === selectedCandidateId)
      ? selectedCandidateId
      : (candidates[0]?.candidate_id ?? null);

  const familyCount = useMemo(
    () => new Set(candidates.map((candidate) => candidate.family)).size,
    [candidates],
  );
  const pendingApprovalCount = approvalsQuery.data?.items.length ?? 0;

  useEffect(() => {
    window.scrollTo(0, 0);
  }, [activeView]);

  const openOperations = (tab: OperationTab) => {
    setActiveOperationTab(tab);
    setActiveView("operations");
  };

  const openAgentReport = () => {
    setReportMode("agent");
    setActiveView("reports");
  };

  const openPaperReport = () => {
    setReportMode("paper");
    setPaperReportRunId(paperQuery.data?.run_id ?? null);
    setActiveView("reports");
  };

  return (
    <Tooltip.Provider delayDuration={160}>
      <div className="min-h-screen bg-[var(--background)]">
        <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[260px_minmax(0,1fr)]">
          <Sidebar
            active={Boolean(statusQuery.data?.active)}
            activeView={activeView}
            apiHealthy={healthQuery.data?.status === "ok"}
            onSelectView={setActiveView}
          />
          <main className="min-w-0 overflow-x-hidden px-4 py-3 sm:px-6 sm:py-4 lg:px-8">
            <div className="mx-auto grid max-w-[1600px] gap-4 sm:gap-5">
              <header className="rounded-lg border border-slate-200 bg-white px-4 py-3 sm:px-5 sm:py-4">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div className="min-w-0">
                    <div className="mb-2 flex flex-wrap items-center gap-2">
                      <span className="rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
                        本地研究 Agent
                      </span>
                      {statusQuery.data?.current_run?.run_id ? (
                        <span className="max-w-full break-all rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
                          批次 {currentRunId}
                        </span>
                      ) : null}
                    </div>
                    <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">
                      Kronos Agent
                    </h1>
                    <p className="mt-2 max-w-4xl break-words text-sm leading-6 text-slate-600">
                      加密货币策略研究助手——定义策略、回测验证、发现问题、迭代优化。
                    </p>
                  </div>
                  <button
                    className="inline-flex h-10 items-center justify-center gap-2 rounded border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
                    type="button"
                    onClick={() => {
                      void healthQuery.refetch();
                      void statusQuery.refetch();
                      void candidateQuery.refetch();
                      void settingsQuery.refetch();
                      void approvalsQuery.refetch();
                      void paperQuery.refetch();
                      void memoryQuery.refetch();
                    }}
                  >
                    <RefreshCw className="h-4 w-4" />
                    刷新状态
                  </button>
                </div>
              </header>

              {apiProblem ? (
                <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm leading-6 text-amber-900">
                  <CircleAlert className="mt-0.5 h-4 w-4 shrink-0" />
                  <span>
                    部分本地 API 读取失败。请确认 FastAPI 后端已启动；界面会保留可读结构，恢复连接后自动显示真实数据。
                  </span>
                </div>
              ) : null}

              {activeView === "dashboard" ? (
                <DashboardView
                  active={Boolean(statusQuery.data?.active)}
                  apiHealthy={healthQuery.data?.status === "ok"}
                  candidates={candidates}
                  candidateLoading={candidateQuery.isLoading}
                  currentRunId={currentRunId}
                  familyCount={familyCount}
                  pendingApprovalCount={pendingApprovalCount}
                  paperStatus={paperQuery.data}
                  paperStatusLoading={paperQuery.isLoading}
                  memory={memoryQuery.data}
                  providerConfigured={providerConfigured}
                  providerHint={provider?.masked_value ?? "DeepSeek 本地密钥"}
                  statusHint={
                    statusQuery.data?.current_task?.title_zh ??
                    "无挂起任务，等待材料或下一轮启动"
                  }
                  onOpenCandidates={() => setActiveView("candidates")}
                  onOpenPaperReport={openPaperReport}
                  onOpenReports={openAgentReport}
                  onOpenMaterials={() => openOperations("materials")}
                  onOpenSettings={() => openOperations("settings")}
                  onSelectCandidate={(candidateId) => {
                    setSelectedCandidateId(candidateId);
                    setActiveView("candidates");
                  }}
                />
              ) : null}

              {activeView === "memory" ? (
                <AgentMemoryPanel isLoading={memoryQuery.isLoading} memory={memoryQuery.data} />
              ) : null}

              {activeView === "candidates" ? (
                <CandidateWorkspace
                  candidates={candidates}
                  isLoading={candidateQuery.isLoading}
                  selectedCandidateId={visibleSelectedCandidateId}
                  onAddMaterial={() => openOperations("materials")}
                  onSelectCandidate={setSelectedCandidateId}
                />
              ) : null}

              {activeView === "reports" ? (
                <ReportReaderPanel
                  mode={reportMode}
                  runId={reportMode === "paper" ? (paperReportRunId ?? "latest") : currentRunId}
                  onClose={() => setActiveView("dashboard")}
                />
              ) : null}

              {activeView === "timeline" ? <AgentTimeline runId={currentRunId} /> : null}

              {activeView === "operations" ? (
                <OperationalTabs
                  activeTab={activeOperationTab}
                  candidates={candidates}
                  runId={currentRunId}
                  taskId={currentTaskId}
                  onTabChange={setActiveOperationTab}
                />
              ) : null}
            </div>
          </main>
        </div>
      </div>
    </Tooltip.Provider>
  );
}

function DashboardView({
  active,
  apiHealthy,
  candidates,
  candidateLoading,
  currentRunId,
  familyCount,
  pendingApprovalCount,
  paperStatus,
  paperStatusLoading,
  memory,
  providerConfigured,
  providerHint,
  statusHint,
  onOpenCandidates,
  onOpenPaperReport,
  onOpenReports,
  onOpenMaterials,
  onOpenSettings,
  onSelectCandidate,
}: {
  active: boolean;
  apiHealthy: boolean;
  candidates: CandidateListItem[];
  candidateLoading: boolean;
  currentRunId: string;
  familyCount: number;
  pendingApprovalCount: number;
  paperStatus?: PaperStatus;
  paperStatusLoading: boolean;
  memory?: AgentMemoryDashboard;
  providerConfigured: boolean;
  providerHint: string;
  statusHint: string;
  onOpenCandidates: () => void;
  onOpenPaperReport: () => void;
  onOpenReports: () => void;
  onOpenMaterials: () => void;
  onOpenSettings: () => void;
  onSelectCandidate: (candidateId: string) => void;
}) {
  return (
    <div className="grid min-w-0 gap-5">
      <PaperStatusPanel
        isLoading={paperStatusLoading}
        paper={paperStatus}
        onOpenReport={onOpenPaperReport}
      />

      <MemorySnapshotCard memory={memory} />

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <SummaryCard
          icon={<Activity className="h-4 w-4" />}
          label="Agent 状态"
          value={active ? "运行中" : "待命"}
          hint={statusHint}
          tone={active ? "teal" : "slate"}
        />
        <SummaryCard
          icon={<Boxes className="h-4 w-4" />}
          label="候选资产"
          value={`${candidates.length}`}
          hint={`${familyCount} 个研究族群，点击进入候选池查看推荐理由`}
          tone="sky"
        />
        <SummaryCard
          icon={<ShieldAlert className="h-4 w-4" />}
          label="人工闸口"
          value={`${pendingApprovalCount}`}
          hint={pendingApprovalCount > 0 ? "有事项等待确认" : "当前没有待审批项，审批项由 Agent 自动生成"}
          tone={pendingApprovalCount > 0 ? "amber" : "slate"}
        />
        <SummaryCard
          icon={<KeyRound className="h-4 w-4" />}
          label="模型配置"
          value={providerConfigured ? "已配置" : "未配置"}
          hint={providerConfigured ? providerHint : "未配置时不能启动新的 LLM 多角色研究"}
          tone={providerConfigured ? "teal" : "amber"}
        />
        <SummaryCard
          icon={<Gauge className="h-4 w-4" />}
          label="本地 API"
          value={apiHealthy ? "正常" : "待连接"}
          hint="kronos-web-api"
          tone={apiHealthy ? "teal" : "amber"}
        />
      </section>

      <SourceNotice providerConfigured={providerConfigured} runId={currentRunId} />

      <ActionBoard
        providerConfigured={providerConfigured}
        onOpenCandidates={onOpenCandidates}
        onOpenMaterials={onOpenMaterials}
        onOpenReports={onOpenReports}
        onOpenSettings={onOpenSettings}
      />

      <LifecycleChart candidates={candidates} />

      <section className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,1.2fr)_minmax(360px,0.8fr)]">
        <RunBriefPanel
          modelConfigured={providerConfigured}
          runId={currentRunId}
          onOpenReport={onOpenReports}
        />
        <TopCandidatesPanel
          candidates={candidates}
          isLoading={candidateLoading}
          onOpenCandidates={onOpenCandidates}
          onSelectCandidate={onSelectCandidate}
        />
      </section>
    </div>
  );
}

function SourceNotice({ providerConfigured, runId }: { providerConfigured: boolean; runId: string }) {
  return (
    <section
      className={cn(
        "flex flex-wrap items-start justify-between gap-3 rounded-lg border px-4 py-3 text-sm leading-6",
        providerConfigured
          ? "border-teal-100 bg-teal-50 text-teal-900"
          : "border-amber-200 bg-amber-50 text-amber-950",
      )}
    >
      <div className="min-w-0">
        <div className="font-semibold">本轮结论来源</div>
        <p className="mt-1 break-words">
          {providerConfigured
            ? `当前批次 ${runId} 可继续接入已配置模型；页面展示的是本地报告和事件流的可审计结果。`
            : `当前批次 ${runId} 来自本地确定性验收和历史报告读取，不是 DeepSeek 实时生成。配置模型后才能启动新的多角色 LLM 研究。`}
        </p>
      </div>
    </section>
  );
}

function MemorySnapshotCard({ memory }: { memory?: AgentMemoryDashboard }) {
  if (!memory) {
    return null;
  }
  return (
    <section className="grid min-w-0 gap-3 rounded-lg border border-slate-200 bg-white p-4 lg:grid-cols-[minmax(0,1fr)_auto]">
      <div className="min-w-0">
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <span className="rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            v{memory.state.current_version}
          </span>
          <span className="rounded border border-sky-100 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-800">
            验收对象：Agent 记忆控制台
          </span>
        </div>
        <h2 className="text-base font-semibold text-slate-950">v0.4.10 首屏验收状态</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">
          最新证据：{memory.state.latest_successful_run_zh}
        </p>
        <p className="mt-1 text-sm leading-6 text-slate-600">
          下一步：{memory.state.next_action_zh}
        </p>
      </div>
      <div className="grid content-start gap-2 text-sm">
        <span className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
          {memory.check.warning_count} 警告 / {memory.check.blocking_count} 阻塞
        </span>
      </div>
    </section>
  );
}

function ActionBoard({
  providerConfigured,
  onOpenCandidates,
  onOpenMaterials,
  onOpenReports,
  onOpenSettings,
}: {
  providerConfigured: boolean;
  onOpenCandidates: () => void;
  onOpenMaterials: () => void;
  onOpenReports: () => void;
  onOpenSettings: () => void;
}) {
  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-slate-950">下一步可以做什么</h2>
          <p className="mt-1 text-sm leading-6 text-slate-500">
            当前 Agent 待命时，先读报告、看候选、补材料或配置模型；真钱实盘不会自动触发。
          </p>
        </div>
      </div>
      <div className="mt-4 grid gap-3 md:grid-cols-2 2xl:grid-cols-5">
        <ActionCard
          icon={<FileText className="h-4 w-4" />}
          title="阅读本轮报告"
          text="直接查看结论、证据、反方意见和下一步。"
          buttonLabel="打开报告"
          tone="teal"
          onClick={onOpenReports}
        />
        <ActionCard
          icon={<Target className="h-4 w-4" />}
          title="查看候选改造"
          text="进入候选池，优先看推荐理由和证据缺口。"
          buttonLabel="查看候选"
          tone="sky"
          onClick={onOpenCandidates}
        />
        <ActionCard
          icon={<FilePlus2 className="h-4 w-4" />}
          title="导入研究材料"
          text="补充旧策略说明、失败记录或模拟盘复盘。"
          buttonLabel="导入材料"
          tone="slate"
          onClick={onOpenMaterials}
        />
        <ActionCard
          icon={<KeyRound className="h-4 w-4" />}
          title={providerConfigured ? "模型已可用" : "配置 DeepSeek"}
          text={providerConfigured ? "可用于后续多角色研究。" : "未配置时不能启动新的 LLM Agent。"}
          buttonLabel={providerConfigured ? "查看配置" : "去配置"}
          tone={providerConfigured ? "teal" : "amber"}
          onClick={onOpenSettings}
        />
        <ActionCard
          disabled={!providerConfigured}
          icon={<PlayCircle className="h-4 w-4" />}
          title="开始下一轮研究"
          text={providerConfigured
            ? "配置已就绪，启动新的多角色 LLM 研究循环。"
            : "请先在「操作台 → 模型配置」中保存 DeepSeek API Key，再启动研究。"}
          buttonLabel={providerConfigured ? "启动研究" : "配置模型后可用"}
          tone={providerConfigured ? "teal" : "slate"}
          onClick={providerConfigured ? onOpenSettings : undefined}
          tooltip={providerConfigured ? undefined : "请先在「操作台 → 模型配置」中保存 DeepSeek API Key"}
        />
      </div>
    </section>
  );
}

function ActionCard({
  disabled = false,
  icon,
  title,
  text,
  buttonLabel,
  tone,
  onClick,
  tooltip,
}: {
  disabled?: boolean;
  icon: ReactNode;
  title: string;
  text: string;
  buttonLabel: string;
  tone: "teal" | "sky" | "amber" | "slate";
  onClick?: () => void;
  tooltip?: string;
}) {
  const toneClass = {
    teal: "border-teal-100 bg-teal-50 text-teal-800",
    sky: "border-sky-100 bg-sky-50 text-sky-800",
    amber: "border-amber-100 bg-amber-50 text-amber-800",
    slate: "border-slate-200 bg-slate-50 text-slate-700",
  }[tone];

  return (
    <div className="grid min-h-44 gap-3 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-start gap-2">
        <span className={cn("inline-flex h-8 w-8 shrink-0 items-center justify-center rounded border", toneClass)}>
          {icon}
        </span>
        <div className="min-w-0">
          <div className="font-semibold text-slate-950">{title}</div>
          <p className="mt-1 text-xs leading-5 text-slate-500">{text}</p>
        </div>
      </div>
      <DisabledTooltip tooltip={disabled ? tooltip : undefined}>
        <button
          className="mt-auto inline-flex h-9 items-center justify-center rounded bg-slate-900 px-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:bg-slate-300"
          type="button"
          disabled={disabled}
          onClick={onClick}
        >
          {buttonLabel}
        </button>
      </DisabledTooltip>
    </div>
  );
}

function DisabledTooltip({ tooltip, children }: { tooltip?: string; children: ReactNode }) {
  if (!tooltip) return <>{children}</>;
  return (
    <Tooltip.Root>
      <Tooltip.Trigger asChild>
        <span tabIndex={0}>{children}</span>
      </Tooltip.Trigger>
      <Tooltip.Portal>
        <Tooltip.Content
          className="max-w-xs rounded border border-slate-200 bg-slate-950 px-3 py-2 text-xs leading-5 text-white shadow"
          sideOffset={6}
        >
          {tooltip}
          <Tooltip.Arrow className="fill-slate-950" />
        </Tooltip.Content>
      </Tooltip.Portal>
    </Tooltip.Root>
  );
}

function TopCandidatesPanel({
  candidates,
  isLoading,
  onOpenCandidates,
  onSelectCandidate,
}: {
  candidates: CandidateListItem[];
  isLoading: boolean;
  onOpenCandidates: () => void;
  onSelectCandidate: (candidateId: string) => void;
}) {
  const topCandidates = candidates.slice(0, 3);
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
        <div className="min-w-0">
          <h2 className="text-sm font-semibold text-slate-950">当前最该看的候选</h2>
          <p className="mt-1 text-xs text-slate-500">按迁移优先级排序，点击后进入候选详情</p>
        </div>
        <button
          className="inline-flex h-8 items-center rounded border border-slate-300 bg-white px-2.5 text-xs font-semibold text-slate-700 hover:bg-slate-50"
          type="button"
          onClick={onOpenCandidates}
        >
          全部候选
        </button>
      </div>
      <div className="grid gap-2 p-4">
        {isLoading ? (
          Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-16 animate-pulse rounded border border-slate-200 bg-slate-100" />
          ))
        ) : topCandidates.length === 0 ? (
          <div className="rounded border border-dashed border-slate-300 bg-slate-50 p-4 text-sm text-slate-500">
            暂无候选资产。导入旧策略材料后会在这里出现。
          </div>
        ) : (
          topCandidates.map((candidate) => (
            <button
              key={candidate.candidate_id}
              className="grid gap-1 rounded border border-slate-200 bg-slate-50 p-3 text-left transition hover:border-teal-200 hover:bg-teal-50"
              type="button"
              onClick={() => onSelectCandidate(candidate.candidate_id)}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-semibold text-slate-950">{candidate.title_zh}</span>
                <span className="rounded border border-teal-100 bg-white px-2 py-0.5 text-xs text-teal-800">
                  #{candidate.migration_rank}
                </span>
              </div>
              <p className="text-xs leading-5 text-slate-500">
                当前处于 {candidate.status_label_zh}，下一步应补 crypto 专项证据。
              </p>
            </button>
          ))
        )}
      </div>
    </section>
  );
}

function CandidateWorkspace({
  candidates,
  isLoading,
  selectedCandidateId,
  onAddMaterial,
  onSelectCandidate,
}: {
  candidates: CandidateListItem[];
  isLoading: boolean;
  selectedCandidateId: string | null;
  onAddMaterial: () => void;
  onSelectCandidate: (candidateId: string) => void;
}) {
  return (
    <section className="grid min-w-0 gap-5">
      <div className="min-w-0 rounded-lg border border-slate-200 bg-white">
        <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-200 px-4 py-3">
          <div className="min-w-0">
            <h2 className="text-base font-semibold text-slate-950">候选策略池</h2>
            <p className="mt-1 text-sm leading-6 text-slate-500">
              优先看“当前判断”和“证据缺口”。点击任意候选查看迁移状态和下一步动作。
            </p>
          </div>
          <span className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            {candidates.length} 个候选
          </span>
        </div>
        <CandidateTable
          candidates={candidates}
          isLoading={isLoading}
          selectedCandidateId={selectedCandidateId}
          onSelectCandidate={onSelectCandidate}
        />
      </div>

      <div className="grid min-w-0 gap-5 xl:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)]">
        <StatusChart candidates={candidates} />
        <CandidateDetailPanel candidateId={selectedCandidateId} onAddMaterial={onAddMaterial} />
      </div>
    </section>
  );
}

function Sidebar({
  active,
  activeView,
  apiHealthy,
  onSelectView,
}: {
  active: boolean;
  activeView: WorkbenchView;
  apiHealthy: boolean;
  onSelectView: (view: WorkbenchView) => void;
}) {
  const navItems: Array<{ view: WorkbenchView; label: string; icon: ReactNode }> = [
    { view: "dashboard", label: "今日", icon: <ClipboardList className="h-4 w-4" /> },
    { view: "memory", label: "记忆", icon: <GitBranch className="h-4 w-4" /> },
    { view: "candidates", label: "候选池", icon: <Database className="h-4 w-4" /> },
    { view: "reports", label: "报告", icon: <FileText className="h-4 w-4" /> },
    { view: "timeline", label: "时间线", icon: <ListChecks className="h-4 w-4" /> },
    { view: "operations", label: "操作台", icon: <SlidersHorizontal className="h-4 w-4" /> },
  ];

  return (
    <aside className="border-b border-slate-200 bg-white px-4 py-3 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:py-4">
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-slate-900 text-white">
          <BrainCircuit className="h-5 w-5" />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-slate-950">Kronos Agent</div>
          <div className="mt-1 text-xs leading-5 text-slate-500">本地量化研究系统</div>
        </div>
      </div>

      <div className="mt-3 grid grid-cols-3 gap-2 text-sm sm:grid-cols-5 lg:mt-5 lg:grid-cols-1">
        {navItems.map((item) => {
          const selected = item.view === activeView;
          return (
            <button
              key={item.view}
              className={cn(
                "flex items-center justify-center gap-1.5 rounded border px-2 py-2 text-slate-600 transition lg:justify-start lg:gap-2 lg:px-3",
                selected
                  ? "border-teal-100 bg-teal-50 font-semibold text-teal-800"
                  : "border-transparent hover:border-slate-200 hover:bg-slate-50",
              )}
              type="button"
              onClick={() => onSelectView(item.view)}
            >
              {item.icon}
              {item.label}
            </button>
          );
        })}
      </div>

      <div className="mt-3 grid grid-cols-2 gap-2 rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600 lg:mt-5 lg:grid-cols-1">
        <StatusLine
          icon={<CheckCircle2 className="h-3.5 w-3.5" />}
          label="API"
          value={apiHealthy ? "已连接" : "待连接"}
          ok={apiHealthy}
        />
        <StatusLine
          icon={<Clock3 className="h-3.5 w-3.5" />}
          label="Agent"
          value={active ? "执行中" : "待命"}
          ok={active}
        />
      </div>
    </aside>
  );
}

function StatusLine({
  icon,
  label,
  value,
  ok,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  ok: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="inline-flex items-center gap-1.5">
        <span className={ok ? "text-teal-700" : "text-slate-500"}>{icon}</span>
        {label}
      </span>
      <span className={ok ? "font-semibold text-teal-700" : "text-slate-500"}>{value}</span>
    </div>
  );
}

function SummaryCard({
  icon,
  label,
  value,
  hint,
  tone,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  hint: string;
  tone: "teal" | "sky" | "amber" | "slate";
}) {
  const toneClass = {
    teal: "border-teal-100 bg-teal-50 text-teal-800",
    sky: "border-sky-100 bg-sky-50 text-sky-800",
    amber: "border-amber-100 bg-amber-50 text-amber-800",
    slate: "border-slate-200 bg-slate-50 text-slate-700",
  }[tone];

  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-medium text-slate-500">{label}</span>
        <span className={cn("inline-flex h-8 w-8 items-center justify-center rounded border", toneClass)}>
          {icon}
        </span>
      </div>
      <div className="mt-2 truncate text-2xl font-semibold text-slate-950">{value}</div>
      <Tooltip.Root>
        <Tooltip.Trigger asChild>
          <p className="mt-1 truncate text-xs text-slate-500">{hint}</p>
        </Tooltip.Trigger>
        <Tooltip.Portal>
          <Tooltip.Content
            className="max-w-xs rounded border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700 shadow"
            sideOffset={6}
          >
            {hint}
            <Tooltip.Arrow className="fill-white" />
          </Tooltip.Content>
        </Tooltip.Portal>
      </Tooltip.Root>
    </div>
  );
}

function OperationalTabs({
  activeTab,
  candidates,
  runId,
  taskId,
  onTabChange,
}: {
  activeTab: OperationTab;
  candidates: CandidateListItem[];
  runId: string;
  taskId: string;
  onTabChange: (tab: OperationTab) => void;
}) {
  return (
    <section className="min-w-0 rounded-lg border border-slate-200 bg-white">
      <div className="border-b border-slate-200 px-4 py-3">
        <h2 className="text-base font-semibold text-slate-950">操作台</h2>
        <p className="mt-1 text-sm leading-6 text-slate-500">
          模型配置、材料入口和人工审批集中在这里；实盘相关动作只会在人工许可后继续。
        </p>
      </div>
      <Tabs.Root value={activeTab} onValueChange={(value) => onTabChange(value as OperationTab)}>
        <Tabs.List className="grid grid-cols-3 border-b border-slate-200 bg-slate-50 p-1">
          <Tabs.Trigger
            className="inline-flex h-10 items-center justify-center gap-2 rounded text-sm font-medium text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm"
            value="settings"
          >
            <KeyRound className="h-4 w-4" />
            模型
          </Tabs.Trigger>
          <Tabs.Trigger
            className="inline-flex h-10 items-center justify-center gap-2 rounded text-sm font-medium text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm"
            value="materials"
          >
            <FilePlus2 className="h-4 w-4" />
            材料
          </Tabs.Trigger>
          <Tabs.Trigger
            className="inline-flex h-10 items-center justify-center gap-2 rounded text-sm font-medium text-slate-600 data-[state=active]:bg-white data-[state=active]:text-slate-950 data-[state=active]:shadow-sm"
            value="approvals"
          >
            <ShieldAlert className="h-4 w-4" />
            审批
          </Tabs.Trigger>
        </Tabs.List>
        <Tabs.Content className="p-4" value="settings">
          <SettingsPanel />
        </Tabs.Content>
        <Tabs.Content className="p-4" value="materials">
          <MaterialsPanel candidates={candidates} />
        </Tabs.Content>
        <Tabs.Content className="p-4" value="approvals">
          <ApprovalCenter runId={runId} taskId={taskId} />
        </Tabs.Content>
      </Tabs.Root>
    </section>
  );
}
