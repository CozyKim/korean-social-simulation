"use client";

import { useMemo } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { useSSE } from "@/lib/sse";
import type { SseEvent } from "@/lib/types";
import { PersonaCard } from "./persona-card";
import { StatsRail } from "./stats-rail";

interface LiveFeedProps {
  runId: string;
  maxCards?: number;
}

interface PersonaItem {
  id: number;
  persona: { sex: string; age: number; province: string };
  avatarKey: string | null;
  reaction: Extract<SseEvent, { type: "persona_done" }>["reaction"];
}

export function LiveFeed({ runId, maxCards = 50 }: LiveFeedProps) {
  const { events, connected, error } = useSSE(`/api/runs/${runId}/events`);

  const errEvent = events.find((e) => e.type === "error") as
    | (Extract<SseEvent, { type: "error" }>)
    | undefined;
  const completed = events.some((e) => e.type === "completed");

  const { items, stats, total, progress } = useMemo(() => {
    let total = 0;
    let progress = 0;
    let positiveCount = 0;
    let intensitySum = 0;
    let intensityCount = 0;
    let failCount = 0;
    const items: PersonaItem[] = [];
    for (const e of events) {
      if (e.type === "persona_done") {
        items.push({
          id: e.event_id,
          persona: e.persona,
          avatarKey: e.avatar_key ?? null,
          reaction: e.reaction,
        });
        total = e.total;
        progress += 1;
        const r = e.reaction as typeof e.reaction & { error?: string | null };
        const failed = !!r.error || (!r.stance && !r.quote);
        if (failed) {
          failCount += 1;
        } else {
          if (r.stance === "positive") positiveCount += 1;
          if (typeof r.intensity === "number") {
            intensitySum += r.intensity;
            intensityCount += 1;
          }
        }
      } else if (e.type === "started" && typeof e.total === "number") {
        total = e.total;
      }
    }
    // 클라이언트 누적 계산 — 성공 카운트 분모로 stance 비율, fail 카운트로 fail_rate.
    const successCount = progress - failCount;
    const stats = {
      positive_pct: successCount > 0 ? positiveCount / successCount : 0,
      avg_intensity: intensityCount > 0 ? intensitySum / intensityCount : 0,
      fail_rate: progress > 0 ? failCount / progress : 0,
    };
    return { items: items.slice(-maxCards).reverse(), stats, total, progress };
  }, [events, maxCards]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_240px]">
      <div className="space-y-2">
        {error && !errEvent && !completed && (
          <div className="text-sm text-amber-400">{error}</div>
        )}
        {errEvent && (
          <div className="rounded border border-red-700 bg-red-900/30 p-3 text-sm text-red-300">
            오류: {errEvent.error}
          </div>
        )}
        {!connected && items.length === 0 && !errEvent && !completed && (
          <div className="text-sm text-zinc-500">연결 중…</div>
        )}
        {completed && items.length === 0 && !errEvent && (
          <div className="text-sm text-zinc-500">완료됐지만 표시할 데이터가 없습니다.</div>
        )}
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.div
              key={item.id}
              layout
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
              transition={{ type: "spring", stiffness: 300, damping: 30 }}
            >
              <PersonaCard
                persona={item.persona}
                avatarKey={item.avatarKey}
                reaction={item.reaction}
              />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
      <aside className="lg:sticky lg:top-4 lg:self-start">
        <StatsRail
          progress={progress}
          total={total}
          positivePct={stats.positive_pct}
          avgIntensity={stats.avg_intensity}
          failRate={stats.fail_rate}
        />
      </aside>
    </div>
  );
}
