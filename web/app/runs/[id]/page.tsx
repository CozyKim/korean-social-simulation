import { cookies } from "next/headers";
import { notFound } from "next/navigation";
import { apiFetchServer, ApiError } from "@/lib/api";
import { LiveFeed } from "@/components/live-feed/live-feed";
import type { RunSummary } from "@/lib/types";

export const dynamic = "force-dynamic";
export const revalidate = 60;

interface RunDetail extends RunSummary {
  scenario: { title: string; stimulus: string; context?: string; question?: string; scenario_type?: string };
  report_url: string | null;
}

export default async function RunPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const cookieHeader = (await cookies()).toString();
  let detail: RunDetail;
  try {
    detail = await apiFetchServer<RunDetail>(`/api/runs/${id}`, cookieHeader);
  } catch (e) {
    if (e instanceof ApiError && (e.status === 404 || e.status === 403)) notFound();
    throw e;
  }
  return (
    <main className="mx-auto max-w-6xl p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">{detail.title}</h1>
        <div className="text-xs text-zinc-500">
          {detail.model} · n={detail.n} · status={detail.status}
        </div>
        {detail.scenario.stimulus && (
          <p className="mt-3 text-sm text-zinc-300">{detail.scenario.stimulus}</p>
        )}
      </header>
      <LiveFeed runId={id} maxCards={50} />
    </main>
  );
}
