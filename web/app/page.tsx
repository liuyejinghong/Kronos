import { MessagesSquare } from "lucide-react";

import { AppShell } from "@/components/app-shell";
import { ConversationHome } from "@/components/conversation/conversation-home";

/**
 * 首页：策略对话（P16）。
 *
 * 服务端组件只读 `?demo=1`（演示模式：渲染静态样例，不请求后端）；
 * 真实会话引导、消息收发、任务轮询与结论获取全部在
 * components/conversation/conversation-home.tsx（client）中完成。
 */
export default async function ConversationHomePage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const params = await searchParams;
  const demoMode = params.demo === "1";

  return (
    <AppShell>
      <div className="grid min-w-0 gap-4">
        <header className="rounded-lg border border-slate-200 bg-white px-4 py-4 sm:px-5">
          <span className="mb-2 inline-flex items-center gap-1.5 rounded border border-teal-100 bg-teal-50 px-2.5 py-1 text-xs font-semibold text-teal-800">
            <MessagesSquare className="h-3.5 w-3.5" />
            策略对话
          </span>
          <h1 className="break-words text-2xl font-semibold text-slate-950 sm:text-3xl">
            和研究助手聊聊你的策略
          </h1>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-slate-600">
            问结论、调参重跑、追问证据——对话是主入口。旧面板仍可在「高级（只读）」中使用。
          </p>
        </header>

        <ConversationHome demoMode={demoMode} />
      </div>
    </AppShell>
  );
}
