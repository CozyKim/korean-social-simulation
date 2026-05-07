"use client";

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LiveFeed } from "@/components/live-feed/live-feed";

const CHART_NAMES = ["stance.png", "intensity.png", "intent.png", "seg_sex.png", "seg_province.png"];

interface RunTabsProps {
  runId: string;
  reportMd: string | null;
  apiBase: string;
}

export function RunTabs({ runId, reportMd, apiBase }: RunTabsProps) {
  return (
    <Tabs defaultValue="live" className="w-full">
      <TabsList>
        <TabsTrigger value="live">Live</TabsTrigger>
        <TabsTrigger value="charts">Charts</TabsTrigger>
        <TabsTrigger value="quotes">Quotes</TabsTrigger>
        <TabsTrigger value="report">Report</TabsTrigger>
        <TabsTrigger value="raw">Raw</TabsTrigger>
      </TabsList>
      <TabsContent value="live"><LiveFeed runId={runId} maxCards={50} /></TabsContent>
      <TabsContent value="charts">
        <div className="grid gap-3 sm:grid-cols-2">
          {CHART_NAMES.map((c) => (
            <img
              key={c}
              src={`${apiBase}/api/runs/${runId}/charts/${c}`}
              alt={c}
              className="rounded border border-zinc-800"
              onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = "none"; }}
            />
          ))}
        </div>
      </TabsContent>
      <TabsContent value="quotes">
        <div className="text-sm text-zinc-400">
          상위 인용은 Report 탭의 마크다운에 포함됩니다.
        </div>
      </TabsContent>
      <TabsContent value="report">
        <pre className="whitespace-pre-wrap rounded border border-zinc-800 bg-zinc-900/40 p-4 text-sm">
          {reportMd ?? "리포트가 아직 생성되지 않았습니다."}
        </pre>
      </TabsContent>
      <TabsContent value="raw">
        <a
          href={`${apiBase}/api/runs/${runId}/reactions`}
          className="text-sm text-blue-400 hover:underline"
          download={`${runId}-reactions.parquet`}
        >
          reactions.parquet 다운로드
        </a>
      </TabsContent>
    </Tabs>
  );
}
