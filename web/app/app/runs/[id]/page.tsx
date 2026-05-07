import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { apiFetchServer, ApiError } from "@/lib/api";
import { RunTabs } from "@/components/run-tabs";
import type { RunSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

interface RunDetail extends RunSummary {
  scenario: { title: string; stimulus: string };
  report_url: string | null;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";

async function fetchReport(id: string, cookieHeader: string): Promise<string | null> {
  try {
    const res = await fetch(`${API_BASE}/api/runs/${id}/report`, {
      headers: { Cookie: cookieHeader },
      cache: "no-store",
    });
    if (!res.ok) return null;
    return await res.text();
  } catch {
    return null;
  }
}

export default async function AppRunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookieHeader = (await cookies()).toString();
  let detail: RunDetail;
  try {
    detail = await apiFetchServer<RunDetail>(`/api/runs/${id}`, cookieHeader);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 401)) notFound();
    throw e;
  }
  const reportMd = detail.report_url ? await fetchReport(id, cookieHeader) : null;
  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">{detail.title}</h1>
        <div className="text-xs text-zinc-500">
          {detail.model} · n={detail.n} · status={detail.status} · public={String(detail.public)}
        </div>
        {detail.scenario.stimulus && (
          <p className="mt-3 text-sm text-zinc-300">{detail.scenario.stimulus}</p>
        )}
      </header>
      <RunTabs runId={id} reportMd={reportMd} apiBase={API_BASE} />
    </main>
  );
}
