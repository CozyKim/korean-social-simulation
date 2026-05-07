"use client";

import { useEffect, useRef, useState } from "react";

const CATEGORY_ICON: Record<string, string> = {
  marketing: "/illustrations/category-marketing.webp",
  social: "/illustrations/category-social.webp",
  product: "/illustrations/category-product.webp",
  policy: "/illustrations/category-policy.webp",
  other: "/illustrations/category-other.webp",
};

const CATEGORY_FALLBACK: Record<string, { emoji: string; gradient: string }> = {
  marketing: { emoji: "📢", gradient: "from-amber-700 to-orange-500" },
  social: { emoji: "💬", gradient: "from-violet-700 to-purple-500" },
  product: { emoji: "🛒", gradient: "from-emerald-700 to-teal-500" },
  policy: { emoji: "🏛️", gradient: "from-slate-700 to-zinc-500" },
  other: { emoji: "❓", gradient: "from-zinc-700 to-zinc-500" },
};

interface ScenarioCategoryIconProps {
  scenarioType: string;
}

/**
 * 시나리오 카테고리 아이콘. 자산 누락 시 카테고리별 이모지 + gradient placeholder 로 fallback.
 *
 * 견고한 fail 감지 — 다음 세 신호 중 어느 하나라도 잡히면 fallback:
 * - ``onError`` (네트워크 fail)
 * - ``onLoad`` 시 ``naturalWidth === 0`` (404 응답이지만 브라우저가 onError 안 부른 경우)
 * - mount 시점에 이미 ``complete === true && naturalWidth === 0`` (hydration 직후 fail 상태)
 */
export function ScenarioCategoryIcon({ scenarioType }: ScenarioCategoryIconProps) {
  const [failed, setFailed] = useState(false);
  const imgRef = useRef<HTMLImageElement | null>(null);
  const fallback = CATEGORY_FALLBACK[scenarioType] ?? CATEGORY_FALLBACK.other;

  useEffect(() => {
    const img = imgRef.current;
    if (img && img.complete && img.naturalWidth === 0) {
      setFailed(true);
    }
  }, []);

  if (failed) {
    return (
      <div
        className={`flex h-12 w-12 items-center justify-center rounded-md bg-gradient-to-br text-2xl ${fallback.gradient}`}
        aria-label={scenarioType}
      >
        {fallback.emoji}
      </div>
    );
  }

  return (
    <img
      ref={imgRef}
      src={CATEGORY_ICON[scenarioType] ?? CATEGORY_ICON.other}
      alt=""
      className="h-12 w-12"
      onError={() => setFailed(true)}
      onLoad={(e) => {
        if (e.currentTarget.naturalWidth === 0) setFailed(true);
      }}
    />
  );
}
