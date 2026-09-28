"use client";

/**
 * 历史与证据页控制器（P17）。按 URL 查询参数切换三种视图：
 * - 无参数：列表视图。注意：后端当前没有「历史结论列表」接口
 *   （GET /api/conversations 只支持按 id 读取；列表属 M2/P18 范围），
 *   因此列表视图提供「从对话进入 / 粘贴 run_id / 内置演示」三条路径。
 * - ?run_id=<id> 或 ?demo=<key>：结论详情（复用 VerdictCard）。
 * - ?a=<ref>&b=<ref>：同快照比较（demo:valid-observe 这类引用亦可）。
 */

import { useRouter } from "next/navigation";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";

import { CompareView, parseVerdictRef } from "@/components/history/compare-view";
import { VerdictDetailView } from "@/components/history/verdict-detail-view";
import { CARD_FIXTURE_KEYS } from "@/components/verdict-card/card-fixtures";

const DEMO_STATE_DESCRIPTIONS: Record<string, string> = {
  "valid-observe": "有效 × 观察",
  "limited-redesign": "受限 × 改造（含保留集已暴露）",
  "insufficient-zero-trades": "证据不足 × 拒判（零交易）",
  invalid: "无效 × 拒判（快照失败）",
  "param-not-activated": "参数未生效（伪稳健提示）",
};

function RunIdForm() {
  const router = useRouter();
  const [runId, setRunId] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = runId.trim();
    if (trimmed !== "") {
      router.push(`/history?run_id=${encodeURIComponent(trimmed)}`);
    }
  }

  return (
    <form className="flex flex-wrap items-center gap-2" onSubmit={submit}>
      <input
        className="h-10 min-w-0 flex-1 rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-900 outline-none focus:border-teal-600"
        onChange={(event) => setRunId(event.target.value)}
        placeholder="粘贴结论 run_id（如任务里的结论任务 id）"
        type="text"
        value={runId}
      />
      <button
        className="h-10 rounded bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
        disabled={runId.trim() === ""}
        type="submit"
      >
        查看结论卡
      </button>
    </form>
  );
}

function CompareForm() {
  const router = useRouter();
  const [refA, setRefA] = useState("");
  const [refB, setRefB] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (parseVerdictRef(refA) !== null && parseVerdictRef(refB) !== null) {
      router.push(
        `/history?a=${encodeURIComponent(refA.trim())}&b=${encodeURIComponent(refB.trim())}`,
      );
    }
  }

  return (
    <form className="grid gap-2" onSubmit={submit}>
      <div className="flex flex-wrap items-center gap-2">
        <input
          className="h-10 min-w-0 flex-1 rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-900 outline-none focus:border-teal-600"
          onChange={(event) => setRefA(event.target.value)}
          placeholder="结论 A：run_id 或 demo:valid-observe"
          type="text"
          value={refA}
        />
        <input
          className="h-10 min-w-0 flex-1 rounded border border-slate-300 bg-white px-3 font-mono text-sm text-slate-900 outline-none focus:border-teal-600"
          onChange={(event) => setRefB(event.target.value)}
          placeholder="结论 B：run_id 或 demo:limited-redesign"
          type="text"
          value={refB}
        />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <button
          className="h-10 rounded bg-slate-900 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:opacity-50"
          disabled={parseVerdictRef(refA) === null || parseVerdictRef(refB) === null}
          type="submit"
        >
          比较两个结论
        </button>
        <button
          className="h-10 rounded border border-slate-300 bg-white px-4 text-sm font-semibold text-slate-700 transition hover:bg-slate-50"
          onClick={() => {
            setRefA("demo:valid-observe");
            setRefB("demo:limited-redesign");
          }}
          type="button"
        >
          用示例比较
        </button>
      </div>
    </form>
  );
}

function ListView() {
  return (
    <div className="grid min-w-0 gap-4">
      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-8">
        <p className="text-base font-semibold text-slate-700">还没有可列出的历史结论</p>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-500">
          后端目前只提供按 run_id 读取单个结论（GET /api/verdicts/&#123;run_id&#125;），
          「历史结论列表」接口尚未实现（属 M2/P18 范围）。在列表能力就绪前，请从以下入口进入：
        </p>
        <ul className="mt-3 list-inside list-decimal space-y-1 text-sm leading-6 text-slate-600">
          <li>从对话进入：在策略对话里生成结论后，用结论卡上提供的链接跳转到这里。</li>
          <li>直接访问：/history?run_id=&lt;结论 run_id&gt;。</li>
          <li>内置演示：用 ?demo=&lt;状态&gt; 走查结论卡的全部状态。</li>
        </ul>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-950">按 run_id 打开结论</h3>
        <p className="mt-1 text-xs text-slate-500">
          结论在对话的评估任务成功发布后才存在；失败或未完成的 run 没有结论。
        </p>
        <div className="mt-3">
          <RunIdForm />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-950">同快照比较</h3>
        <p className="mt-1 text-xs text-slate-500">
          输入两个结论引用并排比较关键指标与参数差异（spec_hash）。
        </p>
        <div className="mt-3">
          <CompareForm />
        </div>
      </section>

      <section className="rounded-lg border border-slate-200 bg-white p-4">
        <h3 className="text-sm font-semibold text-slate-950">内置演示状态（?demo=）</h3>
        <p className="mt-1 text-xs text-slate-500">
          与真实接口字段结构一致的演示 verdict，用于走查卡片全部状态。
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {CARD_FIXTURE_KEYS.map((key) => (
            <a
              className="inline-flex h-9 items-center rounded border border-teal-100 bg-teal-50 px-3 text-xs font-semibold text-teal-800 transition hover:bg-teal-100"
              href={`/history?demo=${encodeURIComponent(key)}`}
              key={key}
            >
              {DEMO_STATE_DESCRIPTIONS[key] ?? key}
            </a>
          ))}
          <a
            className="inline-flex h-9 items-center rounded border border-slate-300 bg-white px-3 text-xs font-semibold text-slate-700 transition hover:bg-slate-50"
            href="/history?a=demo%3Avalid-observe&b=demo%3Alimited-redesign"
          >
            示例比较：有效观察 vs 受限改造
          </a>
        </div>
      </section>
    </div>
  );
}

export function HistoryClient() {
  const searchParams = useSearchParams();
  const refA = searchParams.get("a");
  const refB = searchParams.get("b");
  const runId = searchParams.get("run_id");
  const demoKey = searchParams.get("demo");

  if (refA !== null || refB !== null) {
    return <CompareView refA={refA ?? ""} refB={refB ?? ""} />;
  }
  if (demoKey !== null) {
    return <VerdictDetailView demoKey={demoKey} />;
  }
  if (runId !== null) {
    return <VerdictDetailView runId={runId} />;
  }
  return <ListView />;
}
