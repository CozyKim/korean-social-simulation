"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type { HealthResponse, CreateRunResponse, TryRunRequest } from "@/lib/types";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { LiveFeed } from "@/components/live-feed/live-feed";

export default function TryPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => apiFetch<HealthResponse>("/api/health"),
  });
  const [title, setTitle] = useState("");
  const [stimulus, setStimulus] = useState("");
  const [n, setN] = useState(10);
  const [runId, setRunId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (health.data && health.data.vllm !== "up") {
    return (
      <main className="mx-auto max-w-xl p-6">
        <Card>
          <CardHeader>
            <CardTitle>체험 불가</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-zinc-400">
            현재 vLLM 백엔드가 응답하지 않아 게스트 모드를 일시 중단합니다.
          </CardContent>
        </Card>
      </main>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim() || !stimulus.trim()) {
      setError("제목과 자극은 필수입니다.");
      return;
    }
    if (n < 1 || n > 20) {
      setError("n 은 1 이상 20 이하여야 합니다.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const body: TryRunRequest = { scenario_title: title, scenario_stimulus: stimulus, n };
      const res = await apiFetch<CreateRunResponse>("/api/try", {
        method: "POST",
        body: JSON.stringify(body),
      });
      setRunId(res.run_id);
    } catch (e) {
      if (e instanceof ApiError) {
        if (e.status === 422) setError("n 은 최대 20입니다.");
        else if (e.status === 429) setError("일일 1회 한도를 초과했습니다.");
        else if (e.status === 503) setError("동시 실행 한도(2개)에 도달. 잠시 후 다시 시도하세요.");
        else setError(e.detail);
      } else setError(String(e));
    } finally {
      setSubmitting(false);
    }
  };

  if (runId) {
    return (
      <main className="mx-auto max-w-5xl p-6">
        <h1 className="mb-4 text-xl font-bold">체험 결과</h1>
        <LiveFeed runId={runId} maxCards={20} />
      </main>
    );
  }
  return (
    <main className="mx-auto max-w-xl p-6">
      <Card>
        <CardHeader>
          <CardTitle>게스트 체험 (n ≤ 20, IP 1회/일)</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={submit} className="space-y-3" noValidate>
            <label className="block">
              <span className="block text-xs text-zinc-400">제목 *</span>
              <input
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={200}
                required
              />
            </label>
            <label className="block">
              <span className="block text-xs text-zinc-400">자극 *</span>
              <textarea
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                rows={4}
                value={stimulus}
                onChange={(e) => setStimulus(e.target.value)}
                maxLength={4096}
                required
              />
            </label>
            <label className="block">
              <span className="block text-xs text-zinc-400">n (최대 20)</span>
              <input
                type="number"
                min={1}
                max={20}
                className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                value={n}
                onChange={(e) => setN(Number(e.target.value))}
              />
            </label>
            {error && <div className="text-sm text-red-400">{error}</div>}
            <Button type="submit" variant="primary" disabled={submitting}>
              {submitting ? "시작 중…" : "체험 시작"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </main>
  );
}
