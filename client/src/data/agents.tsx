import type { Campaign, CampaignMove } from "@/components/campanha/types";
import { CombIcon, type CombIconProps } from "@/components/comb-icon";
import {
  Radar,
  ScanSearch,
  ShieldHalf,
  type LucideIcon
} from "lucide-react";

/**
 * Registro dos agentes especialistas.
 *
 * Para adicionar um novo agente, basta acrescentar um objeto a `AGENTS` — toda
 * a interface (constelação, cards, trilha) é gerada a partir desta lista.
 * `matchKey` é o valor que o backend manda em `move.recommended_by`.
 */

export type AgentAccent = "rose" | "sky" | "violet" | "emerald" | "amber";

export interface AgentDef {
  id: string;
  name: string;
  role: string;
  tacticId?: string;
  tacticName?: string;
  icon: LucideIcon | React.FC<CombIconProps>;
  accent: AgentAccent;
  description: string;
  /** Agente orquestrador (fica no centro da constelação). */
  master?: boolean;
  /** Valor esperado em move.recommended_by para contabilizar os lances. */
  matchKey?: string;
}

export const AGENTS: AgentDef[] = [
  {
    id: "pent",
    name: "Pent",
    role: "Mestre · orquestra a partida",
    icon: CombIcon,
    accent: "rose",
    master: true,
    description:
      "Coordena os especialistas, decide a ordem dos lances e fala com o árbitro.",
  },
  {
    id: "recon",
    name: "Recon",
    role: "Reconhecimento",
    tacticId: "TA0043",
    tacticName: "Reconnaissance",
    icon: Radar,
    accent: "sky",
    matchKey: "Recon",
    description:
      "Observa o alvo e levanta a superfície exposta antes de qualquer teste ativo.",
  },
  {
    id: "discovery",
    name: "Discovery",
    role: "Descoberta",
    tacticId: "TA0007",
    tacticName: "Discovery",
    icon: ScanSearch,
    accent: "violet",
    matchKey: "Discovery",
    description:
      "Mapeia tecnologias, arquivos e caminhos sensíveis a partir das pistas do Recon.",
  },
];

/** Agente genérico para lances sem `recommended_by` conhecido. */
export const FALLBACK_AGENT: AgentDef = {
  id: "engine",
  name: "Árbitro",
  role: "Motor determinístico",
  icon: ShieldHalf,
  accent: "emerald",
  description: "Executa e confirma os testes seguindo as regras do catálogo.",
};

export const ACCENT: Record<
  AgentAccent,
  {
    text: string;
    ring: string;
    border: string;
    soft: string;
    dot: string;
    glow: string;
    gradient: string;
  }
> = {
  rose: {
    text: "text-rose-300",
    ring: "ring-rose-500/40",
    border: "border-rose-500/40",
    soft: "bg-rose-500/10",
    dot: "bg-rose-400",
    glow: "shadow-[0_0_28px_-6px_rgba(244,63,94,0.7)]",
    gradient: "from-rose-500/25 to-rose-500/0",
  },
  sky: {
    text: "text-sky-300",
    ring: "ring-sky-500/40",
    border: "border-sky-500/40",
    soft: "bg-sky-500/10",
    dot: "bg-sky-400",
    glow: "shadow-[0_0_28px_-6px_rgba(56,189,248,0.7)]",
    gradient: "from-sky-500/25 to-sky-500/0",
  },
  violet: {
    text: "text-violet-300",
    ring: "ring-violet-500/40",
    border: "border-violet-500/40",
    soft: "bg-violet-500/10",
    dot: "bg-violet-400",
    glow: "shadow-[0_0_28px_-6px_rgba(167,139,250,0.7)]",
    gradient: "from-violet-500/25 to-violet-500/0",
  },
  emerald: {
    text: "text-emerald-300",
    ring: "ring-emerald-500/40",
    border: "border-emerald-500/40",
    soft: "bg-emerald-500/10",
    dot: "bg-emerald-400",
    glow: "shadow-[0_0_28px_-6px_rgba(52,211,153,0.7)]",
    gradient: "from-emerald-500/25 to-emerald-500/0",
  },
  amber: {
    text: "text-amber-300",
    ring: "ring-amber-500/40",
    border: "border-amber-500/40",
    soft: "bg-amber-500/10",
    dot: "bg-amber-400",
    glow: "shadow-[0_0_28px_-6px_rgba(251,191,36,0.7)]",
    gradient: "from-amber-500/25 to-amber-500/0",
  },
};

export interface AgentActivity {
  agent: AgentDef;
  handled: number;
  lastMove: CampaignMove | null;
  lastTechnique: string | null;
  /** O agente está trabalhando agora (lance em execução/planejado dele). */
  working: boolean;
  /** A campanha terminou e ele participou. */
  done: boolean;
}

function matchesAgent(move: CampaignMove, agent: AgentDef): boolean {
  if (agent.master) return true;
  if (!agent.matchKey) return false;
  return (move.recommended_by ?? "").toLowerCase() === agent.matchKey.toLowerCase();
}

const ACTIVE_STATES = new Set(["created", "running", "waiting_approval"]);

export function deriveAgentActivity(
  agent: AgentDef,
  campaign: Campaign | null,
): AgentActivity {
  const moves = campaign?.moves ?? [];
  const handledMoves = moves.filter((move) => matchesAgent(move, agent));
  const lastMove = handledMoves[handledMoves.length - 1] ?? null;
  const campaignActive = campaign ? ACTIVE_STATES.has(campaign.state) : false;

  // "Trabalhando" = existe um lance dele ainda sem resultado, ou (mestre) a
  // campanha está ativa.
  const hasPendingWork = handledMoves.some(
    (move) => !move.finished_at && move.status === null,
  );
  const working = campaignActive && (agent.master ? true : hasPendingWork);

  return {
    agent,
    handled: handledMoves.length,
    lastMove,
    lastTechnique: lastMove?.attack_technique_name ?? null,
    working,
    done: !campaignActive && handledMoves.length > 0,
  };
}

/** Resolve o agente responsável por um lance (para selos nos achados). */
export function agentForMove(move: CampaignMove): AgentDef {
  const found = AGENTS.find(
    (agent) =>
      !agent.master &&
      agent.matchKey &&
      (move.recommended_by ?? "").toLowerCase() === agent.matchKey.toLowerCase(),
  );
  return found ?? FALLBACK_AGENT;
}
