import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { LiveFeed } from "@/components/live-feed/live-feed";

class MockEventSource {
  static last: MockEventSource;
  onmessage: ((e: MessageEvent) => void) | null = null;
  onopen: ((e: Event) => void) | null = null;
  onerror: ((e: Event) => void) | null = null;
  constructor(public url: string) {
    MockEventSource.last = this;
  }
  close() {}
  emit(data: unknown, id = "1") {
    this.onmessage?.(new MessageEvent("message", { data: JSON.stringify(data), lastEventId: id }));
  }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", MockEventSource);
  sessionStorage.clear();
});
afterEach(() => vi.unstubAllGlobals());

describe("LiveFeed", () => {
  it("renders cards as SSE events stream in", async () => {
    render(<LiveFeed runId="r1" />);
    await act(async () => {
      MockEventSource.last.emit({
        type: "persona_done",
        event_id: 1,
        index: 0,
        total: 10,
        persona: { sex: "female", age: 28, province: "서울특별시" },
        avatar_key: "female_20s_서울특별시",
        reaction: {
          stance: "positive",
          intensity: 4,
          action_intent: "purchase",
          quote: "테스트 인용",
          key_drivers: [],
          concerns: [],
        },
        stats: { positive_pct: 1, avg_intensity: 4, fail_rate: 0 },
      });
    });
    expect(screen.getByText("테스트 인용")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument(); // progress count
  });
});
