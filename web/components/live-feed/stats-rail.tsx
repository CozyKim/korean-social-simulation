import { Card } from "@/components/ui/card";
import { formatPercent, formatNumber } from "@/lib/format";

interface StatsRailProps {
  progress: number;
  total: number;
  positivePct: number;
  avgIntensity: number;
  failRate: number;
}

export function StatsRail({ progress, total, positivePct, avgIntensity, failRate }: StatsRailProps) {
  const ratio = total > 0 ? progress / total : 0;
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-1">
      <Card className="p-3">
        <div className="text-xs text-zinc-400">진행</div>
        <div className="text-2xl font-bold tabular-nums">
          {progress}<span className="text-zinc-500">/{total}</span>
        </div>
        <div className="mt-1 h-1 overflow-hidden rounded bg-zinc-800">
          <div className="h-full bg-red-500 transition-[width] duration-200" style={{ width: `${ratio * 100}%` }} />
        </div>
      </Card>
      <Card className="p-3">
        <div className="text-xs text-zinc-400">긍정 비율</div>
        <div className="text-2xl font-bold tabular-nums">{formatPercent(positivePct)}</div>
      </Card>
      <Card className="p-3">
        <div className="text-xs text-zinc-400">평균 강도</div>
        <div className="text-2xl font-bold tabular-nums">{formatNumber(avgIntensity)}</div>
      </Card>
      <Card className="p-3">
        <div className="text-xs text-zinc-400">실패율</div>
        <div className="text-2xl font-bold tabular-nums">{formatPercent(failRate)}</div>
      </Card>
    </div>
  );
}
