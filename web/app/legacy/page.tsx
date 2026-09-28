import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { WorkbenchApp } from "@/components/workbench-app";

/**
 * 旧版工作台：完整保留原面板功能（paper 状态、记忆、候选池、报告、
 * 时间线、操作台），仅从主导航降级到「高级（只读）」入口。
 */
export default function LegacyPage() {
  return (
    <div className="min-h-screen bg-[var(--background)]">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-2 sm:px-6">
        <Link
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-600 transition hover:text-slate-950"
          href="/"
        >
          <ArrowLeft className="h-4 w-4" />
          返回策略对话
        </Link>
        <span className="text-xs text-slate-500">高级（只读）旧版工作台 · 面板功能保持不变</span>
      </div>
      <WorkbenchApp />
    </div>
  );
}
