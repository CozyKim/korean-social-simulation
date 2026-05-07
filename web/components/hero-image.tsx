"use client";

import { useState } from "react";

/**
 * Landing 히어로 배경 이미지. ``public/illustrations/hero.webp`` 가 없는
 * 깨끗한 체크아웃에서는 React state 로 깨진 이미지를 숨긴다 (배경 element 자체 미렌더).
 *
 * SSR hydration 타이밍에 ``onError`` 가 발화 안 되는 경우가 있어 ``onLoad`` 의
 * ``naturalWidth === 0`` 도 함께 검증.
 */
export function HeroImage() {
  const [failed, setFailed] = useState(false);
  if (failed) return null;
  return (
    <img
      src="/illustrations/hero.webp"
      alt=""
      className="absolute inset-0 -z-10 h-full w-full object-cover opacity-30"
      onError={() => setFailed(true)}
      onLoad={(e) => {
        if (e.currentTarget.naturalWidth === 0) setFailed(true);
      }}
    />
  );
}
