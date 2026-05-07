"use client";

import { useState, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, ApiError } from "@/lib/api";

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const qc = useQueryClient();
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      await apiFetch("/api/auth/login", { method: "POST", body: JSON.stringify({ token }) });
      await qc.invalidateQueries({ queryKey: ["me"] });
      router.replace(params.get("from") ?? "/app");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setError("토큰이 일치하지 않습니다.");
      else if (err instanceof ApiError && err.status === 429) setError("로그인 시도가 너무 많습니다. 잠시 후 다시.");
      else setError(String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>로그인</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-3" noValidate>
          <label className="block">
            <span className="block text-xs text-zinc-400">KSS_OWNER_TOKEN</span>
            <input
              type="password"
              autoFocus
              className="mt-1 w-full rounded border border-zinc-700 bg-zinc-900 px-2 py-1.5 text-sm font-mono"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </label>
          {error && <div className="text-sm text-red-400">{error}</div>}
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? "확인 중…" : "로그인"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}

export default function LoginPage() {
  return (
    <main className="mx-auto max-w-sm p-6">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </main>
  );
}
