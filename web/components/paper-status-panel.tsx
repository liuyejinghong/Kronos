"use client";

import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ExternalLink,
  FileText,
  ReceiptText,
  ShieldCheck,
  XCircle,
} from "lucide-react";
import type { ReactNode } from "react";

import type { PaperError, PaperFill, PaperOrder, PaperStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

type PaperStatusPanelProps = {
  isLoading: boolean;
  paper?: PaperStatus;
  onOpenReport: () => void;
};

export function PaperStatusPanel({ isLoading, paper, onOpenReport }: PaperStatusPanelProps) {
  if (isLoading) {
    return (
      <section className="grid gap-3 rounded-lg border border-slate-200 bg-white p-4 sm:grid-cols-3">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="h-24 animate-pulse rounded border border-slate-200 bg-slate-100" />
        ))}
      </section>
    );
  }

  if (!paper) {
    return (
      <section className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">
        测试网状态暂时读不到。请确认本地后端已启动；这里不会触发 testnet 或 mainnet 交易。
      </section>
    );
  }

  const canOpenReport = Boolean(paper.run_id && paper.report_available);

  return (
    <section className="grid min-w-0 gap-4 rounded-lg border border-slate-200 bg-white p-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="min-w-0">
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <StatusBadge status={paper.status} />
          <span className="inline-flex items-center gap-1.5 rounded border border-sky-100 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-800">
            <ShieldCheck className="h-3.5 w-3.5" />
            {paper.environment}
          </span>
          <span className="rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs text-slate-600">
            只读展示
          </span>
        </div>

        <h2 className="text-base font-semibold text-slate-950">测试网模拟盘</h2>
        <p className="mt-2 break-words text-sm leading-6 text-slate-600">{paper.message_zh}</p>

        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          <InfoTile label="最近 run" value={paper.run_id ?? "暂无"} />
          <InfoTile label="更新时间" value={paper.updated_at ?? "暂无"} />
        </div>

        <div className="mt-4 rounded border border-amber-200 bg-amber-50 p-3 text-sm leading-6 text-amber-950">
          {paper.next_action_zh}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          <button
            className="inline-flex h-9 items-center justify-center gap-2 rounded bg-slate-900 px-3 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:bg-slate-300"
            type="button"
            disabled={!canOpenReport}
            onClick={canOpenReport ? onOpenReport : undefined}
          >
            <FileText className="h-4 w-4" />
            读取报告
          </button>
          {paper.truncated ? (
            <span className="inline-flex min-h-9 items-center rounded border border-slate-200 bg-slate-50 px-3 text-xs text-slate-600">
              仅展示最近 5 条
            </span>
          ) : null}
        </div>
      </div>

      <div className="grid min-w-0 gap-3">
        <EvidenceBlock
          emptyText="暂无 testnet 订单记录。"
          icon={<ReceiptText className="h-3.5 w-3.5" />}
          title="最近订单"
        >
          {paper.latest_orders.map((order) => (
            <OrderRow key={order.order_id ?? order.client_order_id ?? `${order.symbol}-${order.status}`} order={order} />
          ))}
        </EvidenceBlock>
        <EvidenceBlock
          emptyText="暂无 testnet 成交记录。"
          icon={<CheckCircle2 className="h-3.5 w-3.5" />}
          title="最近成交"
        >
          {paper.latest_fills.map((fill) => (
            <FillRow key={fill.trade_id ?? fill.order_id ?? `${fill.symbol}-${fill.fill_time}`} fill={fill} />
          ))}
        </EvidenceBlock>
        <EvidenceBlock
          emptyText="暂无错误记录。"
          icon={<AlertTriangle className="h-3.5 w-3.5" />}
          title="最近错误"
        >
          {paper.latest_errors.map((error, index) => (
            <ErrorRow key={`${error.run_id ?? "paper-error"}-${error.created_at ?? index}`} error={error} />
          ))}
        </EvidenceBlock>
        <details className="rounded border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
          <summary className="cursor-pointer font-semibold text-slate-700">本地证据路径</summary>
          <PathLine label="报告" value={paper.report_path} />
          <PathLine label="目录" value={paper.run_dir} />
        </details>
      </div>
    </section>
  );
}

function StatusBadge({ status }: { status: string }) {
  const tone = statusTone(status);
  const icon = statusIcon(status);
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded border px-2.5 py-1 text-xs font-semibold", tone)}>
      {icon}
      {statusLabel(status)}
    </span>
  );
}

function statusTone(status: string) {
  if (status === "completed") {
    return "border-teal-100 bg-teal-50 text-teal-800";
  }
  if (status === "failed") {
    return "border-rose-100 bg-rose-50 text-rose-800";
  }
  if (status === "stopped") {
    return "border-amber-200 bg-amber-50 text-amber-800";
  }
  return "border-slate-200 bg-slate-50 text-slate-700";
}

function statusIcon(status: string) {
  if (status === "completed") {
    return <CheckCircle2 className="h-3.5 w-3.5" />;
  }
  if (status === "failed") {
    return <XCircle className="h-3.5 w-3.5" />;
  }
  if (status === "stopped") {
    return <Clock3 className="h-3.5 w-3.5" />;
  }
  return <ShieldCheck className="h-3.5 w-3.5" />;
}

function statusLabel(status: string) {
  if (status === "completed") {
    return "已完成";
  }
  if (status === "failed") {
    return "失败";
  }
  if (status === "stopped") {
    return "已停止";
  }
  if (status === "running") {
    return "运行中";
  }
  return status;
}

function InfoTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="text-xs font-semibold text-slate-500">{label}</div>
      <div className="mt-1 truncate text-sm font-medium text-slate-900">{value}</div>
    </div>
  );
}

function EvidenceBlock({
  children,
  emptyText,
  icon,
  title,
}: {
  children: ReactNode;
  emptyText: string;
  icon: ReactNode;
  title: string;
}) {
  const items = Array.isArray(children) ? children.filter(Boolean) : children;
  const empty = Array.isArray(items) ? items.length === 0 : !items;
  return (
    <div className="min-w-0 rounded border border-slate-200 bg-slate-50 p-3">
      <div className="flex items-center gap-2 text-xs font-semibold text-slate-500">
        {icon}
        {title}
      </div>
      <div className="mt-2 grid gap-2">
        {empty ? <div className="rounded border border-dashed border-slate-300 bg-white p-3 text-sm text-slate-500">{emptyText}</div> : items}
      </div>
    </div>
  );
}

function OrderRow({ order }: { order: PaperOrder }) {
  return (
    <div className="grid gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-slate-950">{order.symbol}</span>
        <span className="rounded border border-slate-200 bg-slate-50 px-2 py-0.5 text-xs text-slate-600">
          {order.side} · {order.status}
        </span>
      </div>
      <MetaGrid
        items={[
          ["数量", formatNumber(order.quantity)],
          ["类型", order.order_type ?? "未知"],
          ["订单", order.order_id ?? "暂无"],
        ]}
      />
    </div>
  );
}

function FillRow({ fill }: { fill: PaperFill }) {
  return (
    <div className="grid gap-2 rounded border border-slate-200 bg-white p-3 text-sm">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-semibold text-slate-950">{fill.symbol}</span>
        <span className="rounded border border-teal-100 bg-teal-50 px-2 py-0.5 text-xs text-teal-800">
          trade {fill.trade_id ?? "未知"}
        </span>
      </div>
      <MetaGrid
        items={[
          ["价格", formatNumber(fill.price)],
          ["数量", formatNumber(fill.quantity)],
          ["手续费", `${formatNumber(fill.commission)} ${fill.commission_asset ?? ""}`.trim()],
          ["时间", fill.fill_time ?? "暂无"],
        ]}
      />
    </div>
  );
}

function ErrorRow({ error }: { error: PaperError }) {
  return (
    <div className="grid gap-1 rounded border border-amber-200 bg-white p-3 text-sm leading-6 text-amber-950">
      <div className="break-words">{error.reason}</div>
      {error.created_at ? <div className="text-xs text-amber-800">{error.created_at}</div> : null}
    </div>
  );
}

function MetaGrid({ items }: { items: Array<[string, string]> }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-2">
      {items.map(([label, value]) => (
        <div key={`${label}-${value}`} className="min-w-0">
          <div className="text-[11px] font-semibold text-slate-400">{label}</div>
          <div className="truncate text-xs text-slate-700">{value}</div>
        </div>
      ))}
    </div>
  );
}

function PathLine({ label, value }: { label: string; value: string | null }) {
  if (!value) {
    return null;
  }
  return (
    <div className="mt-2 flex min-w-0 items-center gap-2 rounded bg-white p-2">
      <ExternalLink className="h-3.5 w-3.5 shrink-0 text-slate-400" />
      <span className="shrink-0 text-slate-500">{label}</span>
      <code className="truncate text-slate-700">{value}</code>
    </div>
  );
}

function formatNumber(value: number | null) {
  if (value === null) {
    return "暂无";
  }
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: 8,
  }).format(value);
}
