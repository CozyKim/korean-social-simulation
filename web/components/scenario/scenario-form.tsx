"use client";

import { useState, FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CreateRunRequest } from "@/lib/types";

interface ScenarioFormProps {
  models: string[];
  maxN: number;
  defaultModel?: string;
  onSubmit: (req: CreateRunRequest) => void;
  submitting?: boolean;
}

export function ScenarioForm({ models, maxN, defaultModel, onSubmit, submitting }: ScenarioFormProps) {
  const [title, setTitle] = useState("");
  const [stimulus, setStimulus] = useState("");
  const [context, setContext] = useState("");
  const [question, setQuestion] = useState("");
  const [type, setType] = useState("other");
  const [n, setN] = useState(50);
  const [model, setModel] = useState(defaultModel ?? models[0] ?? "");
  const [seed, setSeed] = useState(42);
  const [err, setErr] = useState<string | null>(null);

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (n > maxN) {
      setErr(`n 은 최대 ${maxN} 까지 허용됩니다.`);
      return;
    }
    if (!title.trim() || !stimulus.trim()) {
      setErr("제목과 자극은 필수입니다.");
      return;
    }
    setErr(null);
    onSubmit({
      scenario_title: title,
      scenario_stimulus: stimulus,
      scenario_context: context || null,
      scenario_question: question || null,
      scenario_type: type,
      n,
      model,
      seed,
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>새 시뮬</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <Field label="제목" required>
            <input
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              maxLength={200}
            />
          </Field>
          <Field label="자극" required>
            <textarea
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              rows={4}
              value={stimulus}
              onChange={(e) => setStimulus(e.target.value)}
              maxLength={4096}
            />
          </Field>
          <Field label="배경(선택)">
            <textarea
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              rows={2}
              value={context}
              onChange={(e) => setContext(e.target.value)}
              maxLength={2048}
            />
          </Field>
          <Field label="질문(선택)">
            <input
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              maxLength={1024}
            />
          </Field>
          <div className="grid grid-cols-3 gap-3">
            <Field label="유형">
              <select
                className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                value={type}
                onChange={(e) => setType(e.target.value)}
              >
                {["marketing", "social", "product", "policy", "other"].map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="n (페르소나 수)">
              <input
                type="number"
                min={1}
                max={maxN}
                className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                value={n}
                onChange={(e) => setN(Number(e.target.value))}
              />
            </Field>
            <Field label="seed">
              <input
                type="number"
                className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
                value={seed}
                onChange={(e) => setSeed(Number(e.target.value))}
              />
            </Field>
          </div>
          <Field label="모델">
            <select
              className="w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm"
              value={model}
              onChange={(e) => setModel(e.target.value)}
            >
              {models.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </Field>
          {err && <div className="text-sm text-red-400">{err}</div>}
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? "시작 중…" : "시뮬 시작"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

function Field({
  label,
  required,
  children,
}: {
  label: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="block text-xs text-zinc-400">
        {label}
        {required && " *"}
      </span>
      <div className="mt-1">{children}</div>
    </label>
  );
}
