"use client";

import { Suspense, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type { CreateRunRequest, CreateRunResponse } from "@/lib/types";
import { ScenarioForm, type ScenarioFormInitialValues } from "@/components/scenario/scenario-form";

const MODELS = ["vllm-qwen", "vllm-exaone", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"];

interface ScenarioDetail {
  title?: string;
  stimulus?: string;
  context?: string;
  question?: string;
  scenario_type?: string;
}

function NewScenarioInner() {
  const router = useRouter();
  const params = useSearchParams();
  const template = params.get("template");
  const [error, setError] = useState<string | null>(null);

  const detail = useQuery({
    queryKey: ["scenario-detail", template],
    queryFn: () => apiFetch<ScenarioDetail>(`/api/scenarios/${encodeURIComponent(template!)}`),
    enabled: !!template,
  });

  const create = useMutation({
    mutationFn: (req: CreateRunRequest) =>
      apiFetch<CreateRunResponse>("/api/runs", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (res) => router.push(`/app/runs/${res.run_id}`),
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });

  if (template && detail.isLoading) {
    return (
      <main className="mx-auto max-w-2xl p-6">
        <h1 className="mb-4 text-2xl font-bold">새 시뮬</h1>
        <div className="text-sm text-zinc-500">템플릿 불러오는 중…</div>
      </main>
    );
  }

  const initialValues: ScenarioFormInitialValues | undefined = detail.data
    ? {
        scenario_title: detail.data.title,
        scenario_stimulus: detail.data.stimulus,
        scenario_context: detail.data.context ?? null,
        scenario_question: detail.data.question ?? null,
        scenario_type: detail.data.scenario_type,
      }
    : undefined;

  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-bold">새 시뮬</h1>
      {template && (
        <div className="mb-3 text-xs text-zinc-500">
          템플릿: <code className="text-zinc-300">{template}</code>
        </div>
      )}
      {error && <div className="mb-3 text-sm text-red-400">{error}</div>}
      <ScenarioForm
        key={template ?? "blank"}
        models={MODELS}
        maxN={500}
        defaultModel="vllm-qwen"
        initialValues={initialValues}
        onSubmit={(req) => create.mutate(req)}
        submitting={create.isPending}
      />
    </main>
  );
}

export default function NewScenarioPage() {
  return (
    <Suspense fallback={null}>
      <NewScenarioInner />
    </Suspense>
  );
}
