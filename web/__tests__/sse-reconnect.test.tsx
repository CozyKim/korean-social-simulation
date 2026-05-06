import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { useSSE } from "@/lib/sse";

class MockEventSource {
  static instances: MockEventSource[] = [];
  onopen: ((e: Event) => void) | null = null;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  readyState = 0;

  constructor(public url: string, public init?: EventSourceInit) {
    MockEventSource.instances.push(this);
  }
  close() {
    this.readyState = 2;
  }
  emit(data: unknown, lastEventId?: string) {
    this.onmessage?.(
      new MessageEvent("message", {
        data: JSON.stringify(data),
        lastEventId: lastEventId ?? "",
      }),
    );
  }
  fail() {
    this.onerror?.(new Event("error"));
  }
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  sessionStorage.clear();
});

afterEach(() => vi.unstubAllGlobals());

describe("useSSE", () => {
  it("collects messages and stores last event id", async () => {
    const { result } = renderHook(() => useSSE("/api/runs/r1/events"));
    const es = MockEventSource.instances[0];
    act(() => es.emit({ type: "persona_done", event_id: 5 }, "5"));
    await waitFor(() => expect(result.current.events.length).toBe(1));
    expect(sessionStorage.getItem("sse:lastId:/api/runs/r1/events")).toBe("5");
  });

  it("reconnects with Last-Event-ID after error", async () => {
    renderHook(() => useSSE("/api/runs/r1/events"));
    const first = MockEventSource.instances[0];
    act(() => first.emit({ type: "persona_done", event_id: 7 }, "7"));
    act(() => first.fail());
    await waitFor(() => expect(MockEventSource.instances.length).toBeGreaterThan(1), { timeout: 3000 });
    const second = MockEventSource.instances[1];
    expect(second.url).toContain("last_event_id=7");
  });

  it("does not reconnect after terminal completed event even if onerror fires", async () => {
    renderHook(() => useSSE("/api/runs/r1/events"));
    const first = MockEventSource.instances[0];
    act(() => first.emit({ type: "completed" }, "9"));
    // 서버가 stream 종료하면 브라우저 EventSource가 onerror로 보고 — terminal 이후 재연결 금지.
    act(() => first.fail());
    await new Promise((r) => setTimeout(r, 1500));
    expect(MockEventSource.instances.length).toBe(1);
  });

  it("does not reconnect after terminal error event even if onerror fires", async () => {
    renderHook(() => useSSE("/api/runs/r1/events"));
    const first = MockEventSource.instances[0];
    act(() => first.emit({ type: "error", message: "boom" }, "3"));
    act(() => first.fail());
    await new Promise((r) => setTimeout(r, 1500));
    expect(MockEventSource.instances.length).toBe(1);
  });

  it("ignores synthetic id=0 after a higher id is already stored", async () => {
    renderHook(() => useSSE("/api/runs/r1/events"));
    const first = MockEventSource.instances[0];
    act(() => first.emit({ type: "persona_done", event_id: 7 }, "7"));
    // 서버가 재연결 시 id=0의 synthetic started 이벤트를 흘려보내도 stored lastId는 유지.
    act(() => first.emit({ type: "started" }, "0"));
    expect(sessionStorage.getItem("sse:lastId:/api/runs/r1/events")).toBe("7");
  });

  it("prepends NEXT_PUBLIC_API_BASE_URL when set (cross-origin deploy)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com");
    renderHook(() => useSSE("/api/runs/r1/events"));
    const es = MockEventSource.instances[0];
    // BASE 가 설정된 경우 EventSource URL 이 절대 URL 로 시작해야 한다.
    // apiFetch 와 동일 패턴 — 그렇지 않으면 cross-origin 배포에서 Next origin 으로 붙어
    // 쿠키 미포함 + 권한 거부.
    expect(es.url).toMatch(/^https:\/\/api\.example\.com\/api\/runs\/r1\/events/);
  });

  it("uses raw path when NEXT_PUBLIC_API_BASE_URL is empty (dev with rewrites)", async () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    renderHook(() => useSSE("/api/runs/r1/events"));
    const es = MockEventSource.instances[0];
    // BASE 가 빈 문자열이면 raw path 그대로 — Next dev rewrites 가 처리.
    expect(es.url).toMatch(/^\/api\/runs\/r1\/events/);
  });
});
