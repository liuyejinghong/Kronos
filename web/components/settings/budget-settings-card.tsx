"use client";

import { BUDGET_DEFAULT_ROWS } from "@/lib/api-settings";

/**
 * 预算卡：目前只有后端 BudgetLimits 的默认值可展示；
 * 用量查询接口尚未提供（待接线），因此不渲染任何用量/进度数据。
 */
export function BudgetSettingsCard() {
  return (
    <div className="grid gap-3">
      <div className="overflow-x-auto rounded border border-slate-200">
        <table className="min-w-[420px] w-full table-fixed text-left text-sm">
          <tbody>
            {BUDGET_DEFAULT_ROWS.map((row) => (
              <tr key={row.key} className="border-t border-slate-200 first:border-t-0">
                <td className="w-1/2 px-3 py-2 text-slate-600">{row.label_zh}</td>
                <td className="px-3 py-2 font-medium text-slate-900">{row.value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs leading-5 text-slate-500">
        以上为系统默认预算上限（来源 kronos/runtime/budget.py 的 BudgetLimits）。
        实际用量统计接口尚未接线，此处暂不展示已用/剩余数据。
      </p>
    </div>
  );
}
