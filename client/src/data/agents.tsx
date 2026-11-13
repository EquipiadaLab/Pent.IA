import type {
  AgentParticipation,
  Campaign,
  CampaignMove,
} from "@/components/campanha/types";
import { CombIcon, type CombIconProps } from "@/components/comb-icon";
import {
  ArrowUpNarrowWide,
  Bomb,
  DoorOpen,
  FolderSearch,
  KeyRound,
  Radar,
  ScanSearch,
  ShieldHalf,
  SquareTerminal,
  type LucideIcon,
} from "lucide-react";

/**
 * Registro dos agentes especialistas.
 *
 * Para adicionar um novo agente, basta acrescentar um objeto a `AGENTS` — toda
 * a interface (constelação, cards, trilha) é gerada a partir desta lista.
 * `matchKey` é o valor que o backend manda em `move.recommended_by`.
 */

export type AgentAccent =
  | "rose"
  | "sky"
  | "violet"
  | "emerald"
  | "amber"
  | "teal"
  | "orange"
  | "indigo"
  | "fuchsia"
  | "lime";

export interface AgentDef {
  id: string;
  name: string;
  role: string;
  tacticId?: string;
  tacticName?: string;
  icon: LucideIcon | React.FC<CombIconProps>;
  accent: AgentAccent;
  description: string;
  /** O que o agente faz individualmente — exibido no card ao selecioná-lo. */
  does: string[];
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
    does: [
      "Escolhe qual especialista joga o próximo lance.",
      "Valida cada sugestão contra o catálogo fechado antes de executar.",
      "Pede aprovação humana nos testes sensíveis do final.",
    ],
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
    does: [
      "Lê respostas públicas e cabeçalhos sem tocar o alvo de forma intrusiva.",
      "Identifica domínios, rotas e pistas de tecnologia.",
      "Entrega o mapa inicial para os demais agentes.",
    ],
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
    does: [
      "Correlaciona cabeçalhos Server/X-Powered-By com tecnologias conhecidas.",
      "Procura arquivos e caminhos sensíveis expostos.",
      "Alimenta a correlação de CVEs com a tecnologia observada.",
    ],
  },
  {
    id: "initial-access",
    name: "InitialAccess",
    role: "Acesso inicial",
    tacticId: "TA0001",
    tacticName: "Initial Access",
    icon: DoorOpen,
    accent: "orange",
    matchKey: "InitialAccess",
    description:
      "Testa portas de entrada expostas que permitiriam um primeiro pé-dentro.",
    does: [
      "Avalia pontos de entrada acessíveis ao público.",
      "Verifica configurações que facilitariam o acesso inicial.",
      "Sinaliza superfícies que abririam a porta para um atacante.",
    ],
  },
  {
    id: "collection",
    name: "Collection",
    role: "Coleta",
    tacticId: "TA0009",
    tacticName: "Collection",
    icon: FolderSearch,
    accent: "teal",
    matchKey: "Collection",
    description:
      "Procura dados sensíveis que poderiam ser reunidos a partir do que está exposto.",
    does: [
      "Relaciona informações públicas a contas ou recursos específicos.",
      "Identifica repositórios de informação acessíveis.",
      "Mede o que um atacante conseguiria coletar sem credenciais.",
    ],
  },
  {
    id: "privilege-escalation",
    name: "PrivilegeEscalation",
    role: "Elevação de privilégio",
    tacticId: "TA0004",
    tacticName: "Privilege Escalation",
    icon: ArrowUpNarrowWide,
    accent: "amber",
    matchKey: "PrivilegeEscalation",
    description:
      "Investiga caminhos que elevariam o nível de acesso dentro do alvo.",
    does: [
      "Procura falhas de controle de acesso entre papéis.",
      "Avalia se um usuário comum alcançaria funções privilegiadas.",
      "Prioriza riscos que ampliam o impacto de um acesso já obtido.",
    ],
  },
  {
    id: "execution",
    name: "Execution",
    role: "Execução",
    tacticId: "TA0002",
    tacticName: "Execution",
    icon: SquareTerminal,
    accent: "indigo",
    matchKey: "Execution",
    description:
      "Verifica se o alvo poderia ser levado a executar entradas controladas.",
    does: [
      "Testa pontos onde a entrada do usuário influencia o comportamento.",
      "Avalia o tratamento de dados antes de processá-los.",
      "Confirma achados com uma segunda observação.",
    ],
  },
  {
    id: "impact",
    name: "Impact",
    role: "Impacto",
    tacticId: "TA0040",
    tacticName: "Impact",
    icon: Bomb,
    accent: "fuchsia",
    matchKey: "Impact",
    description:
      "Estima o dano real de cada falha para o negócio e para os dados.",
    does: [
      "Traduz falhas técnicas em consequências para o negócio.",
      "Classifica a severidade observada de cada achado.",
      "Ajuda o resumo executivo a priorizar o que corrigir primeiro.",
    ],
  },
  {
    id: "credential-access",
    name: "CredentialAccess",
    role: "Acesso a credenciais",
    tacticId: "TA0006",
    tacticName: "Credential Access",
    icon: KeyRound,
    accent: "lime",
    matchKey: "CredentialAccess",
    description:
      "Procura por credenciais, segredos e cookies tratados de forma insegura.",
    does: [
      "Verifica transporte e atributos de cookies de sessão.",
      "Procura segredos expostos em respostas ou arquivos.",
      "Sinaliza riscos de roubo de credenciais.",
    ],
  },
];

/** Agente genérico para lances sem `recommended_by` conhecido. */
export const FALLBACK_AGENT: AgentDef = {
  id: "engine",
  name: "Motor (regras)",
  role: "Motor determinístico",
  icon: ShieldHalf,
  accent: "emerald",
  matchKey: "-",
  description: "Executa e confirma os testes seguindo as regras do catálogo.",
  does: [
    "Joga os lances de base (cabeçalhos, cookies, CORS) sem agente dedicado.",
    "Executa e confirma cada teste de forma determinística.",
    "Garante que todo lance passe pelas regras do árbitro.",
  ],
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
  teal: {
    text: "text-teal-300",
    ring: "ring-teal-500/40",
    border: "border-teal-500/40",
    soft: "bg-teal-500/10",
    dot: "bg-teal-400",
    glow: "shadow-[0_0_28px_-6px_rgba(45,212,191,0.7)]",
    gradient: "from-teal-500/25 to-teal-500/0",
  },
  orange: {
    text: "text-orange-300",
    ring: "ring-orange-500/40",
    border: "border-orange-500/40",
    soft: "bg-orange-500/10",
    dot: "bg-orange-400",
    glow: "shadow-[0_0_28px_-6px_rgba(251,146,60,0.7)]",
    gradient: "from-orange-500/25 to-orange-500/0",
  },
  indigo: {
    text: "text-indigo-300",
    ring: "ring-indigo-500/40",
    border: "border-indigo-500/40",
    soft: "bg-indigo-500/10",
    dot: "bg-indigo-400",
    glow: "shadow-[0_0_28px_-6px_rgba(129,140,248,0.7)]",
    gradient: "from-indigo-500/25 to-indigo-500/0",
  },
  fuchsia: {
    text: "text-fuchsia-300",
    ring: "ring-fuchsia-500/40",
    border: "border-fuchsia-500/40",
    soft: "bg-fuchsia-500/10",
    dot: "bg-fuchsia-400",
    glow: "shadow-[0_0_28px_-6px_rgba(232,121,249,0.7)]",
    gradient: "from-fuchsia-500/25 to-fuchsia-500/0",
  },
  lime: {
    text: "text-lime-300",
    ring: "ring-lime-500/40",
    border: "border-lime-500/40",
    soft: "bg-lime-500/10",
    dot: "bg-lime-400",
    glow: "shadow-[0_0_28px_-6px_rgba(163,230,53,0.7)]",
    gradient: "from-lime-500/25 to-lime-500/0",
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

/** Lances atribuídos a um agente (o mestre recebe todos). */
export function movesForAgent(
  agent: AgentDef,
  campaign: Campaign | null,
): CampaignMove[] {
  return (campaign?.moves ?? []).filter((move) => matchesAgent(move, agent));
}

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

/**
 * Ordem de exibição no card "Agentes em campo": o mestre primeiro (destacado),
 * depois os especialistas e, por fim, o motor de regras.
 */
export const FIELD_AGENTS: AgentDef[] = [...AGENTS, FALLBACK_AGENT];

/**
 * Participação agregada vinda de `GET /campaigns/{id}/agents` (seção 0B da API).
 * O mestre Pent não aparece nessa lista (ele coordena); o motor vem como `"-"`.
 */
export function participationForAgent(
  agent: AgentDef,
  participation: AgentParticipation[] | null | undefined,
): AgentParticipation | null {
  if (!participation || agent.master) return null;
  const key = (agent.matchKey ?? "").toLowerCase();
  if (!key) return null;
  return (
    participation.find((item) => (item.agent ?? "").toLowerCase() === key) ??
    null
  );
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
