"use client";

const CATEGORY_ICON: Record<string, string> = {
  marketing: "/illustrations/category-marketing.webp",
  social: "/illustrations/category-social.webp",
  product: "/illustrations/category-product.webp",
  policy: "/illustrations/category-policy.webp",
  other: "/illustrations/category-other.webp",
};

interface ScenarioCategoryIconProps {
  scenarioType: string;
}

/**
 * 시나리오 카테고리 아이콘. ``public/illustrations/`` 자산이 없는 환경에서는
 * ``onError`` 로 숨겨 깨진 이미지가 카드에 노출되지 않도록 한다.
 */
export function ScenarioCategoryIcon({ scenarioType }: ScenarioCategoryIconProps) {
  return (
    <img
      src={CATEGORY_ICON[scenarioType] ?? CATEGORY_ICON.other}
      alt=""
      className="h-12 w-12"
      onError={(e) => {
        (e.currentTarget as HTMLImageElement).style.display = "none";
      }}
    />
  );
}
