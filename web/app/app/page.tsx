"use client";

import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import type { RunSummary } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRelativeKo } from "@/lib/format";

export default function AppHomePage() {
  const qc = useQueryClient();
  const runs = useQuery({
    queryKey: ["runs", "all"],
    queryFn: () => apiFetch<RunSummary[]>("/api/runs"),
  });
  const togglePublic = useMutation({
    mutationFn: ({ id, pub }: { id: string; pub: boolean }) =>
      apiFetch(`/api/runs/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ public: pub }),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
  const remove = useMutation({
    mutationFn: (id: string) => apiFetch(`/api/runs/${id}`, { method: "DELETE" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["runs"] }),
  });
  const logout = useMutation({
    mutationFn: () => apiFetch("/api/auth/logout", { method: "POST" }),
    onSuccess: () => {
      window.location.href = "/";
    },
  });

  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-6 flex items-center gap-3">
        <h1 className="text-2xl font-bold">대시보드</h1>
        <Link href="/app/scenarios/new" className="ml-auto">
          <Button variant="primary">새 시뮬</Button>
        </Link>
        <Button variant="ghost" onClick={() => logout.mutate()}>
          로그아웃
        </Button>
      </header>
      {runs.isLoading && <div className="text-sm text-zinc-500">불러오는 중…</div>}
      {runs.isError && (
        <div className="text-sm text-red-400">불러오기 실패: {String(runs.error)}</div>
      )}
      {runs.data && runs.data.length === 0 && (
        <div className="text-sm text-zinc-500">
          아직 실행한 시뮬이 없습니다. 우상단 &quot;새 시뮬&quot; 클릭.
        </div>
      )}
      <div className="grid gap-3">
        {runs.data?.map((r) => (
          <Card key={r.run_id} className="flex items-center gap-3 p-4">
            <Link href={`/app/runs/${r.run_id}`} className="min-w-0 flex-1">
              <div className="truncate font-semibold">{r.title}</div>
              <div className="text-xs text-zinc-500">
                {r.model} · n={r.n} · {formatRelativeKo(r.created_at)}
              </div>
            </Link>
            <Badge variant={r.status === "completed" ? "positive" : "neutral"}>
              {r.status}
            </Badge>
            <Button
              variant={r.public ? "outline" : "ghost"}
              size="sm"
              onClick={() => togglePublic.mutate({ id: r.run_id, pub: !r.public })}
              disabled={togglePublic.isPending}
            >
              {r.public ? "공개됨" : "비공개"}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={() => {
                if (confirm(`${r.title} 삭제?`)) remove.mutate(r.run_id);
              }}
              disabled={remove.isPending}
            >
              삭제
            </Button>
          </Card>
        ))}
      </div>
    </main>
  );
}
