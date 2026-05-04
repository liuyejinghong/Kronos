"use client";

import { useMutation } from "@tanstack/react-query";
import { FilePlus2, SendHorizontal } from "lucide-react";
import { useState } from "react";

import { kronosApi, type CandidateListItem, type MaterialSourceType } from "@/lib/api";

const sourceOptions: Array<{ value: MaterialSourceType; label: string }> = [
  { value: "legacy_strategy", label: "旧 A 股 / 期货策略" },
  { value: "candidate_note", label: "候选策略笔记" },
  { value: "failure_record", label: "失败记录" },
  { value: "simulation_log", label: "模拟盘日志" },
  { value: "user_note", label: "人工补充" },
];

type MaterialsPanelProps = {
  candidates: CandidateListItem[];
};

export function MaterialsPanel({ candidates }: MaterialsPanelProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [sourceType, setSourceType] = useState<MaterialSourceType>("user_note");
  const [candidateId, setCandidateId] = useState("");
  const [tags, setTags] = useState("");

  const importMutation = useMutation({
    mutationFn: () =>
      kronosApi.importMaterial({
        title_zh: title,
        content,
        source_type: sourceType,
        candidate_id: candidateId || null,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
      }),
    onSuccess: () => {
      setTitle("");
      setContent("");
      setCandidateId("");
      setTags("");
    },
  });

  return (
    <div className="grid gap-4">
      <div className="rounded border border-slate-200 bg-slate-50 p-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-900">
          <FilePlus2 className="h-4 w-4 text-teal-700" />
          投喂研究材料
        </div>
        <p className="mt-1 text-xs leading-5 text-slate-500">
          这里用于把旧策略、失败案例、人工观察和模拟盘日志放进 Agent 的材料池。
        </p>
      </div>

      <form
        className="grid gap-3"
        onSubmit={(event) => {
          event.preventDefault();
          importMutation.mutate();
        }}
      >
        <label>
          <span className="mb-1 block text-xs font-medium text-slate-600">标题</span>
          <input
            className="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            value={title}
            placeholder="例如：RB 趋势回踩策略迁移说明"
            onChange={(event) => setTitle(event.target.value)}
          />
        </label>

        <div className="grid gap-3 sm:grid-cols-2">
          <label>
            <span className="mb-1 block text-xs font-medium text-slate-600">材料类型</span>
            <select
              className="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              value={sourceType}
              onChange={(event) => setSourceType(event.target.value as MaterialSourceType)}
            >
              {sourceOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            <span className="mb-1 block text-xs font-medium text-slate-600">关联候选</span>
            <select
              className="h-10 w-full rounded border border-slate-300 bg-white px-3 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
              value={candidateId}
              onChange={(event) => setCandidateId(event.target.value)}
            >
              <option value="">不绑定候选项</option>
              {candidates.map((candidate) => (
                <option key={candidate.candidate_id} value={candidate.candidate_id}>
                  {candidate.title_zh}
                </option>
              ))}
            </select>
          </label>
        </div>

        <label>
          <span className="mb-1 block text-xs font-medium text-slate-600">标签</span>
          <input
            className="h-10 w-full rounded border border-slate-300 px-3 text-sm outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            value={tags}
            placeholder="用英文逗号分隔，例如 trend, rb, migration"
            onChange={(event) => setTags(event.target.value)}
          />
        </label>

        <label>
          <span className="mb-1 block text-xs font-medium text-slate-600">内容</span>
          <textarea
            className="min-h-32 w-full rounded border border-slate-300 px-3 py-2 text-sm leading-6 outline-none focus:border-teal-600 focus:ring-2 focus:ring-teal-100"
            value={content}
            placeholder="粘贴策略说明、研究观察、失败原因、模拟盘记录等。"
            onChange={(event) => setContent(event.target.value)}
          />
        </label>

        <div className="flex flex-wrap items-center gap-3">
          <button
            className="inline-flex h-10 items-center justify-center gap-2 rounded bg-teal-700 px-4 text-sm font-semibold text-white transition hover:bg-teal-800 disabled:bg-slate-300"
            type="submit"
            disabled={!title || !content || importMutation.isPending}
          >
            <SendHorizontal className="h-4 w-4" />
            导入
          </button>
          {importMutation.isSuccess ? (
            <span className="text-sm text-teal-700">
              已写入材料池：{importMutation.data.title_zh}
            </span>
          ) : null}
          {!title || !content ? (
            <span className="text-sm text-slate-500">填写标题和内容后即可导入。</span>
          ) : null}
          {importMutation.isError ? (
            <span className="text-sm text-red-700">导入失败，请确认本地 API 正常运行。</span>
          ) : null}
        </div>
      </form>
    </div>
  );
}
