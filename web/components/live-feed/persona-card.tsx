"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { avatarUrlForKey } from "@/lib/avatar";
import { useState } from "react";
import { ChevronDown, ChevronUp } from "lucide-react";

const SEX_GRADIENT: Record<string, string> = {
  female: "from-pink-700 to-rose-500",
  male: "from-sky-700 to-cyan-500",
  여: "from-pink-700 to-rose-500",
  남: "from-sky-700 to-cyan-500",
  여자: "from-pink-700 to-rose-500",
  남자: "from-sky-700 to-cyan-500",
};

interface PersonaCardProps {
  persona: { sex: string; age: number; province: string };
  avatarKey: string | null;
  reaction: {
    stance?: "positive" | "negative" | "neutral" | "mixed" | null;
    intensity?: number | null;
    action_intent?: string | null;
    quote?: string | null;
    key_drivers?: string[];
    concerns?: string[];
    error?: string | null;
  };
}

const SEX_KO: Record<string, string> = {
  female: "여",
  male: "남",
  여: "여",
  남: "남",
  여자: "여",
  남자: "남",
};

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
  const [avatarFailed, setAvatarFailed] = useState(false);
  const provinceShort = persona.province.replace(/(특별시|광역시|특별자치시|특별자치도|도)$/, "");
  const drivers = reaction.key_drivers ?? [];
  const concerns = reaction.concerns ?? [];
  const failed = !!reaction.error || (!reaction.stance && !reaction.quote);
  const sexKo = SEX_KO[persona.sex] ?? "?";
  const gradient = SEX_GRADIENT[persona.sex] ?? "from-zinc-700 to-zinc-500";
  return (
    <Card className={`flex gap-3 p-3 ${failed ? "opacity-50" : ""}`}>
      <div className="h-10 w-10 shrink-0 overflow-hidden rounded-full bg-zinc-800">
        {avatarKey && !avatarFailed ? (
          <img
            src={avatarUrlForKey(avatarKey)}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
            onError={() => setAvatarFailed(true)}
          />
        ) : (
          <div
            className={`flex h-full w-full items-center justify-center bg-gradient-to-br text-sm font-bold text-white ${gradient}`}
            aria-label={`${sexKo} ${persona.age}`}
          >
            {sexKo}
          </div>
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-xs text-zinc-400">
          <span>{`${SEX_KO[persona.sex] ?? persona.sex} ${persona.age} ${provinceShort}`}</span>
          {failed ? (
            <Badge variant="negative" aria-label="실패">실패</Badge>
          ) : reaction.stance ? (
            <Badge
              variant={STANCE_VARIANT[reaction.stance]}
              aria-label={`${STANCE_KO[reaction.stance]} ${reaction.intensity ?? ""}`}
            >
              {STANCE_KO[reaction.stance]}
              {reaction.intensity != null ? ` · ${reaction.intensity}` : ""}
            </Badge>
          ) : null}
          {reaction.action_intent && <span className="text-zinc-500">{reaction.action_intent}</span>}
        </div>
        {failed ? (
          <p className="mt-1 text-sm leading-relaxed text-zinc-500">
            {reaction.error ?? "(LLM 응답 실패)"}
          </p>
        ) : (
          <p className="mt-1 text-sm leading-relaxed text-zinc-100">{reaction.quote}</p>
        )}
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
