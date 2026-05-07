"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { avatarUrlForKey } from "@/lib/avatar";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

interface PersonaCardProps {
  persona: { sex: string; age: number; province: string };
  avatarKey: string | null;
  reaction: {
    stance: "positive" | "negative" | "neutral" | "mixed";
    intensity: number;
    action_intent?: string;
    quote: string;
    key_drivers?: string[];
    concerns?: string[];
  };
}

const SEX_KO: Record<string, string> = { female: "여", male: "남", 여: "여", 남: "남" };

const STANCE_KO: Record<string, string> = {
  positive: "긍정",
  negative: "부정",
  neutral: "중립",
  mixed: "혼합",
};

const STANCE_VARIANT: Record<string, "positive" | "negative" | "neutral" | "mixed"> = {
  positive: "positive",
  negative: "negative",
  neutral: "neutral",
  mixed: "mixed",
};

export function PersonaCard({ persona, avatarKey, reaction }: PersonaCardProps) {
  const [open, setOpen] = useState(false);
  const provinceShort = persona.province.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, "");
  const drivers = reaction.key_drivers ?? [];
  const concerns = reaction.concerns ?? [];
  return (
    <Card className="flex gap-3 p-3">
      {avatarKey && (
        <img
          src={avatarUrlForKey(avatarKey)}
          alt=""
          loading="lazy"
          className="h-10 w-10 shrink-0 rounded-full bg-zinc-800 object-cover"
          onError={(e) => {
            (e.currentTarget as HTMLImageElement).style.display = "none";
          }}
        />
      )}
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span>{`${SEX_KO[persona.sex] ?? persona.sex} ${persona.age} ${provinceShort}`}</span>
          <Badge
            variant={STANCE_VARIANT[reaction.stance]}
            aria-label={`${STANCE_KO[reaction.stance]} ${reaction.intensity}`}
          >
            {STANCE_KO[reaction.stance]} · {reaction.intensity}
          </Badge>
          {reaction.action_intent && <span className="text-zinc-500">{reaction.action_intent}</span>}
        </div>
        <p className="mt-1 text-sm leading-relaxed text-zinc-100">{reaction.quote}</p>
        {(drivers.length > 0 || concerns.length > 0) && (
          <button
            type="button"
            onClick={() => setOpen((v) => !v)}
            className="mt-1 inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300"
          >
            {open ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            세부 동기
          </button>
        )}
        {open && (
          <div className="mt-2 grid grid-cols-2 gap-2 text-xs text-zinc-400">
            <div>
              <div className="font-semibold text-zinc-300">동기</div>
              <ul className="list-disc pl-4">
                {drivers.map((d) => (
                  <li key={d}>{d}</li>
                ))}
              </ul>
            </div>
            <div>
              <div className="font-semibold text-zinc-300">우려</div>
              <ul className="list-disc pl-4">
                {concerns.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
