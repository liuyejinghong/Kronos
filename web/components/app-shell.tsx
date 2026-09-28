"use client";

import { BrainCircuit, History, MessagesSquare, Settings, Wrench } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

type NavItem = {
  href: string;
  label: string;
  icon: ReactNode;
};

const PRIMARY_NAV: NavItem[] = [
  { href: "/", label: "策略对话", icon: <MessagesSquare className="h-4 w-4" /> },
  { href: "/history", label: "历史与证据", icon: <History className="h-4 w-4" /> },
  { href: "/settings", label: "设置", icon: <Settings className="h-4 w-4" /> },
];

function isNavItemActive(pathname: string, href: string): boolean {
  if (href === "/") {
    return pathname === "/";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

/**
 * 应用外壳：三主入口（策略对话 / 历史与证据 / 设置）+ 降级的「高级（只读）」入口。
 * 窄屏时侧栏退化为顶部横向导航（与旧工作台同一模式），保证小屏可用。
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <div className="grid min-h-screen grid-cols-1 lg:grid-cols-[240px_minmax(0,1fr)]">
        <aside className="border-b border-slate-200 bg-white px-4 py-3 lg:sticky lg:top-0 lg:h-screen lg:border-b-0 lg:border-r lg:py-4">
          <Link className="flex items-start gap-3" href="/">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded bg-slate-900 text-white">
              <BrainCircuit className="h-5 w-5" />
            </div>
            <div className="min-w-0">
              <div className="font-semibold text-slate-950">Kronos Agent</div>
              <div className="mt-1 text-xs leading-5 text-slate-500">本地策略研究对话系统</div>
            </div>
          </Link>

          <nav
            aria-label="主导航"
            className="mt-3 grid grid-cols-3 gap-2 text-sm lg:mt-5 lg:grid-cols-1"
          >
            {PRIMARY_NAV.map((item) => {
              const active = isNavItemActive(pathname, item.href);
              return (
                <Link
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center justify-center gap-1.5 rounded border px-2 py-2 text-slate-600 transition lg:justify-start lg:gap-2 lg:px-3",
                    active
                      ? "border-teal-100 bg-teal-50 font-semibold text-teal-800"
                      : "border-transparent hover:border-slate-200 hover:bg-slate-50",
                  )}
                  href={item.href}
                  key={item.href}
                >
                  {item.icon}
                  {item.label}
                </Link>
              );
            })}
          </nav>

          <div className="mt-3 lg:mt-6 lg:border-t lg:border-slate-200 lg:pt-4">
            <div className="hidden pb-1 text-xs uppercase tracking-wide text-slate-400 lg:block">
              高级
            </div>
            <Link
              className="flex items-center justify-center gap-1.5 rounded border border-slate-200 bg-slate-50 px-2 py-2 text-xs text-slate-500 transition hover:bg-slate-100 lg:justify-start lg:gap-2 lg:px-3"
              href="/advanced"
            >
              <Wrench className="h-3.5 w-3.5" />
              高级（只读）
            </Link>
          </div>
        </aside>

        <main className="min-w-0 overflow-x-hidden px-4 py-4 sm:px-6 sm:py-6 lg:px-8">
          <div className="mx-auto max-w-6xl">{children}</div>
        </main>
      </div>
    </div>
  );
}
