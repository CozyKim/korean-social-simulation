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

  const { items, stats, total, progress } = useMemo(() => {
    let stats = { positive_pct: 0, avg_intensity: 0, fail_rate: 0 };
    let total = 0;
    let progress = 0;
    const items: PersonaItem[] = [];
    for (const e of events) {
      if (e.type === "persona_done") {
        items.push({
          id: e.event_id,
          persona: e.persona,
          avatarKey: e.avatar_key ?? null,
          reaction: e.reaction,
        });
        if (e.stats) stats = e.stats;
        total = e.total;
        progress += 1;
      } else if (e.type === "started" && typeof e.total === "number") {
        total = e.total;
      }
    }
    return { items: items.slice(-maxCards).reverse(), stats, total, progress };
  }, [events, maxCards]);

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_240px]">
      <div className="space-y-2">
        {error && <div className="text-sm text-amber-400">{error}</div>}
        {!connected && items.length === 0 && (
          <div className="text-sm text-zinc-500">연결 중…</div>
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
