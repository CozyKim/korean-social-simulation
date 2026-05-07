export interface MeResponse {
  authenticated: boolean;
}

export interface HealthResponse {
  status: string;
  vllm: "up" | "down" | "unknown";
  active_jobs: number;
}

export interface RunSummary {
  run_id: string;
  title: string;
  model: string;
  n: number;
  status: string;
  public: boolean;
  created_at: string;
}

export interface CreateRunRequest {
  scenario_title: string;
  scenario_stimulus: string;
  scenario_context?: string | null;
  scenario_question?: string | null;
  scenario_type?: string;
  n: number;
  model: string;
  seed?: number;
  concurrency?: number | null;
  filters?: Record<string, unknown> | null;
  insights_model?: string | null;
}

export interface CreateRunResponse {
  run_id: string;
  status: string;
}

export interface TryRunRequest {
  scenario_title: string;
  scenario_stimulus: string;
  scenario_type?: string;
  n: number;
}

export type SseEvent =
  | { type: "started"; event_id: number; run_id?: string; total?: number }
  | {
      type: "persona_done";
      event_id: number;
      index: number;
      total: number;
      persona: { sex: string; age: number; province: string };
      avatar_key: string | null;
      reaction: {
        stance?: "positive" | "negative" | "neutral" | "mixed" | null;
        intensity?: number | null;
        action_intent?: string | null;
        quote?: string | null;
        key_drivers?: string[];
        concerns?: string[];
        error?: string | null;
      };
      stats?: { positive_pct: number; avg_intensity: number; fail_rate: number };
    }
  | { type: "completed"; event_id: number; report_url?: string; public?: boolean }
  | { type: "error"; event_id: number; error: string }
  | { type: "heartbeat"; event_id?: number };
