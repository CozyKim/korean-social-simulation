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

});
