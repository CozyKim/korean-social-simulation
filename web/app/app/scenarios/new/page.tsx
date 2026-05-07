"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { apiFetch, ApiError } from "@/lib/api";
import type { CreateRunRequest, CreateRunResponse } from "@/lib/types";
import { ScenarioForm } from "@/components/scenario/scenario-form";

const MODELS = ["vllm-qwen", "vllm-exaone", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"];

export default function NewScenarioPage() {
  const router = useRouter();
  const [error, setError] = useState<string | null>(null);
  const create = useMutation({
    mutationFn: (req: CreateRunRequest) =>
      apiFetch<CreateRunResponse>("/api/runs", {
        method: "POST",
        body: JSON.stringify(req),
      }),
    onSuccess: (res) => router.push(`/app/runs/${res.run_id}`),
    onError: (e) => setError(e instanceof ApiError ? e.detail : String(e)),
  });
  return (
    <main className="mx-auto max-w-2xl p-6">
      <h1 className="mb-4 text-2xl font-bold">새 시뮬</h1>
      {error && <div className="mb-3 text-sm text-red-400">{error}</div>}
      <ScenarioForm
        models={MODELS}
        maxN={500}
        defaultModel="vllm-qwen"
        onSubmit={(req) => create.mutate(req)}
        submitting={create.isPending}
      />
    </main>
  );
}
