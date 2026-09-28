"use client";

import { VerdictCard } from "@/components/verdict-card/verdict-card";

import {
  type VerdictCardAreaProps,
  type VerdictCardPreview,
} from "@/components/conversation/verdict-card-area";

/**
 * 结论卡挂载位：渲染 P17 的 verdict-card（接受 VerdictJson 或
 * VerdictCardPreview，结构探测），数据获取由 conversation-home 完成。
 */
export function VerdictCardMount({ verdict }: VerdictCardAreaProps) {
  return <VerdictCard verdict={verdict} />;
}

export type { VerdictCardPreview };
