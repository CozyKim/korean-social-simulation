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

  it("computes stats from persona_done events even when stats field is absent", async () => {
    // 백엔드가 stats 필드를 포함하지 않아도 (현재 emission 동작) 클라이언트 누적으로 정확한
    // positive_pct / avg_intensity 가 표시돼야 한다.
    render(<LiveFeed runId="r-stats" />);
    await act(async () => {
      MockEventSource.last.emit({
        type: "persona_done",
        event_id: 1,
        index: 0,
        total: 2,
        persona: { sex: "female", age: 28, province: "서울특별시" },
        avatar_key: null,
        reaction: {
          stance: "positive",
          intensity: 4,
          action_intent: "purchase",
          quote: "긍정 인용",
          key_drivers: [],
          concerns: [],
        },
      });
      MockEventSource.last.emit(
        {
          type: "persona_done",
          event_id: 2,
          index: 1,
          total: 2,
          persona: { sex: "male", age: 35, province: "부산광역시" },
          avatar_key: null,
          reaction: {
            stance: "negative",
            intensity: 2,
            action_intent: "ignore",
            quote: "부정 인용",
            key_drivers: [],
            concerns: [],
          },
        },
        "2",
      );
    });
    // positive_pct = 1/2 = 50%
    expect(screen.getByText("50%")).toBeInTheDocument();
    // avg_intensity = (4 + 2) / 2 = 3
    // formatNumber(3) -> "3" (Intl maximumFractionDigits drops trailing zeros)
    const avgLabel = screen.getByText("평균 강도");
    const avgValue = avgLabel.parentElement?.querySelector(".tabular-nums");
    expect(avgValue?.textContent).toBe("3");
  });
});
