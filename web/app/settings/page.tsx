import { Settings } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { SettingsView } from "@/components/settings/settings-view";

/**
 * 设置页：模型 / 预算 / 数据路径三个分区（P18）。
 *
 * 页面本身是服务端外壳；交互逻辑在 `components/settings/SettingsView`：
 * - 模型：GLM Key 经后端 SecretStore 保存，界面只显示掩码；连通性测试消耗一次调用。
 * - 预算：展示 BudgetLimits 默认上限（用量接口待接线，不构造假数据）。
 * - 数据路径：从 `GET /api/settings/system` 读取的只读本地路径。
 * Key 未配置时顶部出现首启横幅；对话页的确定性路径不依赖 Key，不会因此受阻。
 */
export default function SettingsPage() {
  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600">
            <Settings className="h-3.5 w-3.5" />
            设置
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">设置</h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            模型、预算与本地数据路径集中在这里管理。
          </p>
        </header>

        <SettingsView />
      </div>
    </AppShell>
  );
}
