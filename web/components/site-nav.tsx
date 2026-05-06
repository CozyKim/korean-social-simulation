"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { MeResponse, HealthResponse } from "@/lib/types";

export function SiteNav() {
  const path = usePathname();
  const me = useQuery({
    queryKey: ["me"],
    queryFn: () => apiFetch<MeResponse>("/api/me"),
  });
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/api/health"),
    refetchInterval: 30_000,
  });
  const tabs = [
    { href: "/", label: "홈" },
    { href: "/scenarios", label: "시나리오" },
    { href: "/runs", label: "결과" },
    ...(health.data?.vllm === "up" ? [{ href: "/try", label: "체험" }] : []),
  ];
  return (
    <nav className="flex items-center gap-4 border-b border-zinc-800 px-6 py-3 text-sm">
      <Link href="/" className="font-bold tracking-tight">KSS</Link>
      <div className="flex gap-3">
        {tabs.map((t) => (
          <Link key={t.href} href={t.href}
                className={path === t.href ? "text-zinc-50" : "text-zinc-400 hover:text-zinc-200"}>
            {t.label}
          </Link>
        ))}
      </div>
      <div className="ml-auto flex items-center gap-3 text-xs text-zinc-500">
        <span>vLLM: <span className={
          health.data?.vllm === "up" ? "text-emerald-400" :
          health.data?.vllm === "down" ? "text-red-400" : "text-zinc-500"
        }>{health.data?.vllm ?? "?"}</span></span>
        {me.data?.authenticated ? (
          <Link href="/app" className="text-zinc-200">대시보드</Link>
        ) : (
          <Link href="/app/login" className="text-zinc-400 hover:text-zinc-200">로그인</Link>
        )}
      </div>
    </nav>
  );
}
