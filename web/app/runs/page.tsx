import Link from "next/link";
import { cookies } from "next/headers";
import { apiFetchServer } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRelativeKo } from "@/lib/format";
import type { RunSummary } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 60;

export default async function RunsPage() {
  const cookieHeader = (await cookies()).toString();
  const runs = await apiFetchServer<RunSummary[]>("/api/runs", cookieHeader);
  return (
    <main className="mx-auto max-w-5xl p-6">
      <h1 className="mb-6 text-2xl font-bold">결과</h1>
      {runs.length === 0 ? (
        <div className="text-sm text-zinc-500">아직 공개된 run이 없습니다.</div>
      ) : (
        <div className="grid gap-3">
          {runs.map((r) => (
            <Link key={r.run_id} href={`/runs/${r.run_id}`}>
              <Card className="flex items-center gap-3 p-4 hover:border-zinc-700">
                <div className="min-w-0 flex-1">
                  <div className="truncate font-semibold">{r.title}</div>
                  <div className="text-xs text-zinc-500">
                    {r.model} · n={r.n} · {formatRelativeKo(r.created_at)}
                  </div>
                </div>
                <Badge variant={r.status === "completed" ? "positive" : "neutral"}>{r.status}</Badge>
                {r.public ? <Badge variant="outline">공개</Badge> : <Badge>비공개</Badge>}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </main>
  );
}
