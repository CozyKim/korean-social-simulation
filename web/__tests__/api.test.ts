import { describe, it, expect, beforeEach, vi } from "vitest";
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
});
