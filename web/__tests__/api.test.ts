import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiFetch, ApiError } from "@/lib/api";

describe("apiFetch", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
    );
  });

  it("forwards credentials by default", async () => {
    await apiFetch("/api/me");
    const call = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls[0];
    expect(call[1]).toMatchObject({ credentials: "include" });
  });

  it("parses JSON response", async () => {
    const data = await apiFetch<{ ok: number }>("/api/me");
    expect(data.ok).toBe(1);
  });

  it("throws ApiError on non-2xx", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ detail: "nope" }), { status: 401 }))
    );
    await expect(apiFetch("/api/me")).rejects.toBeInstanceOf(ApiError);
  });

  it("returns undefined for 204 No Content without throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 }))
    );
    const result = await apiFetch<undefined>("/api/runs/abc", { method: "DELETE" });
    expect(result).toBeUndefined();
  });

  it("returns undefined when content-length is 0", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(
        async () =>
          new Response(null, {
            status: 200,
            headers: { "content-length": "0" },
          })
      )
    );
    const result = await apiFetch<undefined>("/api/empty");
    expect(result).toBeUndefined();
  });
});

describe("apiFetchServer", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(JSON.stringify({ ok: 1 }), { status: 200 }))
    );
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  it("uses server-only API_BASE_URL with absolute origin", async () => {
    // 운영 환경: 클라이언트는 NEXT_PUBLIC_API_BASE_URL="" 로 Vercel rewrite 사용,
    // 서버 SSR/Route Handler 는 API_BASE_URL 로 절대 URL 직접 호출.
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    vi.stubEnv("API_BASE_URL", "https://api.example.com");

    const { apiFetchServer } = await import("@/lib/api");
    await apiFetchServer("/api/me", "kss_owner=abc");

    const call = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls[0];
    expect(call[0]).toBe("https://api.example.com/api/me");
    expect(call[1]).toMatchObject({
      headers: { Cookie: "kss_owner=abc" },
      cache: "no-store",
    });
  });

  it("falls back to NEXT_PUBLIC_API_BASE_URL when API_BASE_URL is unset", async () => {
    vi.stubEnv("API_BASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://public.example.com");

    const { apiFetchServer } = await import("@/lib/api");
    await apiFetchServer("/api/me", "");

    const call = (globalThis.fetch as unknown as { mock: { calls: unknown[][] } }).mock.calls[0];
    expect(call[0]).toBe("https://public.example.com/api/me");
  });

  it("throws when neither env is configured (would yield relative URL)", async () => {
    vi.stubEnv("API_BASE_URL", "");
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");

    const { apiFetchServer, ApiError: ApiErrorReloaded } = await import("@/lib/api");
    await expect(apiFetchServer("/api/me", "")).rejects.toBeInstanceOf(ApiErrorReloaded);
  });

  it("returns undefined for 204 No Content", async () => {
    vi.stubEnv("API_BASE_URL", "https://api.example.com");
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));

    const { apiFetchServer } = await import("@/lib/api");
    const result = await apiFetchServer<undefined>("/api/runs/abc", "");
    expect(result).toBeUndefined();
  });
});
