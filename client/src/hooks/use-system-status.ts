import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

export type ComponentState =
  | "ok"
  | "degraded"
  | "error"
  | "disabled"
  | "unchecked";

export interface ComponentStatus {
  status: ComponentState;
  detail: string | null;
  latency_ms: number | null;
}

export interface SystemStatus {
  status: "ok" | "degraded";
  version: string;
  time: string;
  uptime_s: number;
  engine_mode: "real" | "sample";
  planner: "ai" | "rules";
  models: { coach_judge_summary: string | null; planner: string | null };
  components: {
    api: ComponentStatus;
    database: ComponentStatus;
    engine: ComponentStatus;
    llm: ComponentStatus;
  };
  campaigns: Record<string, number>;
}

/** Saúde detalhada do sistema (API, banco, motor e IA). */
export function useSystemStatus(checkLlm = false) {
  return useQuery({
    queryKey: ["system-status", checkLlm],
    queryFn: async () =>
      (
        await api.get<SystemStatus>("/status", {
          params: checkLlm ? { check_llm: true } : undefined,
          timeout: checkLlm ? 30_000 : 10_000,
        })
      ).data,
    refetchInterval: 30_000,
  });
}
