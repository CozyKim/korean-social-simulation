import { apiFetchServer } from "@/lib/api";
import { ScenarioCard } from "@/components/scenario/scenario-card";
import { cookies } from "next/headers";

export const dynamic = "force-dynamic";

interface ScenarioListItem {
  filename: string;
  title: string;
  scenario_type: string;
}

async function fetchScenarios(): Promise<ScenarioListItem[]> {
  const cookieHeader = (await cookies()).toString();
  return apiFetchServer<ScenarioListItem[]>("/api/scenarios", cookieHeader);
}

export default async function ScenariosPage() {
  const scenarios = await fetchScenarios();
  return (
    <main className="mx-auto max-w-6xl p-6">
      <h1 className="mb-6 text-2xl font-bold">시나리오</h1>
      {scenarios.length === 0 ? (
        <div className="text-sm text-zinc-500">아직 등록된 시나리오가 없습니다.</div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {scenarios.map((s) => (
            <ScenarioCard
              key={s.filename}
              name={s.filename}
              title={s.title}
              scenarioType={s.scenario_type}
              stimulusPreview=""
              href={`/app/scenarios/new?template=${encodeURIComponent(s.filename)}`}
            />
          ))}
        </div>
      )}
    </main>
  );
}
