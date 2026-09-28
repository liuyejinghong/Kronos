import { ClipboardList } from "lucide-react";

/** 结论卡首屏四件事：结论 / 最重要证据 / 最大限制 / 下一步。P17 接入 verdict 后填充。 */
export type VerdictCardPreview = {
  conclusionZh: string;
  keyEvidenceZh: string;
  mainLimitationZh: string;
  nextStepZh: string;
};

export type VerdictCardAreaProps = {
  verdict: VerdictCardPreview | null;
};

/**
 * 结论卡位。verdict 为空时展示空状态提示，不发任何请求。
 */
export function VerdictCardArea({ verdict }: VerdictCardAreaProps) {
  if (!verdict) {
    return (
      <section className="rounded-lg border border-dashed border-slate-300 bg-slate-50 p-4">
        <div className="flex items-center gap-2 text-sm font-semibold text-slate-600">
          <ClipboardList className="h-4 w-4" />
          研究结论
        </div>
        <p className="mt-2 text-sm leading-6 text-slate-500">
          还没有研究结论。启动一次研究后，结论卡会显示结论、最重要证据、最大限制和下一步。
        </p>
      </section>
    );
  }

  const rows: Array<{ label: string; value: string }> = [
    { label: "结论", value: verdict.conclusionZh },
    { label: "最重要证据", value: verdict.keyEvidenceZh },
    { label: "最大限制", value: verdict.mainLimitationZh },
    { label: "下一步", value: verdict.nextStepZh },
  ];

  return (
    <section className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="flex items-center gap-2 text-sm font-semibold text-slate-950">
        <ClipboardList className="h-4 w-4 text-teal-700" />
        研究结论
      </div>
      <dl className="mt-3 grid gap-3">
        {rows.map((row) => (
          <div key={row.label}>
            <dt className="text-xs font-medium text-slate-500">{row.label}</dt>
            <dd className="mt-1 break-words text-sm leading-6 text-slate-800">{row.value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
