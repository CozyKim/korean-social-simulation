import { Card } from "@/components/ui/card";

const CATEGORY_ICON: Record<string, string> = {
  marketing: "/illustrations/category-marketing.webp",
  social: "/illustrations/category-social.webp",
  product: "/illustrations/category-product.webp",
  policy: "/illustrations/category-policy.webp",
  other: "/illustrations/category-other.webp",
};

interface ScenarioCardProps {
  name: string;
  title: string;
  scenarioType: string;
  stimulusPreview: string;
  href?: string;
}

export function ScenarioCard({ name, title, scenarioType, stimulusPreview, href }: ScenarioCardProps) {
  const inner = (
    <Card className="flex h-full flex-col gap-2 p-4 hover:border-zinc-700">
      <img
        src={CATEGORY_ICON[scenarioType] ?? CATEGORY_ICON.other}
        alt=""
        className="h-12 w-12"
      />
      <div className="text-sm font-semibold text-zinc-100">{title}</div>
      <div className="text-xs text-zinc-500">{name}</div>
      <p className="line-clamp-3 text-xs text-zinc-400">{stimulusPreview}</p>
    </Card>
  );
  return href ? <a href={href} className="block h-full">{inner}</a> : inner;
}
