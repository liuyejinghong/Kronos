"use client";

import { Sparkles } from "lucide-react";

/** 首次使用横幅：仅在 GLM Key 尚未配置时出现在设置页顶部（对话页不受阻）。 */
export function FirstRunBanner({ visible }: { visible: boolean }) {
  if (!visible) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <p className="flex items-center gap-2 text-sm font-medium text-amber-900">
        <Sparkles className="h-4 w-4 shrink-0" />
        首次使用：配置模型 Key 后即可开始对话
      </p>
      <a
        className="rounded border border-amber-300 bg-white px-3 py-1.5 text-xs font-semibold text-amber-900 transition hover:border-amber-400"
        href="#model"
      >
        前往配置
      </a>
    </div>
  );
}
