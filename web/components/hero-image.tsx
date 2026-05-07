"use client";

/**
 * Landing 히어로 배경 이미지. ``public/illustrations/hero.webp`` 가 없는
 * 깨끗한 체크아웃에서 깨진 이미지가 노출되지 않도록 ``onError`` 로 숨긴다.
 */
export function HeroImage() {
  return (
    <img
      src="/illustrations/hero.webp"
      alt=""
      className="absolute inset-0 -z-10 h-full w-full object-cover opacity-30"
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.display = "none";
      }}
    />
  );
}
