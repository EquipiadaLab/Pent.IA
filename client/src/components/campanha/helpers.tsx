import {
  AlertTriangle,
  Check,
  Circle,
  LockKeyhole,
  X,
} from "lucide-react";
import type { CampaignMove, CampaignState, MoveGrade } from "./types";

export const DEFAULT_LOCAL_TARGET = "http://127.0.0.1:8080";

export const ACTIVE_STATES: CampaignState[] = [
  "created",
  "running",
  "waiting_approval",
];

export function isLoopbackOrigin(value: string) {
  try {
    const url = new URL(value);
    return (
      (url.protocol === "http:" || url.protocol === "https:") &&
      ["localhost", "127.0.0.1", "[::1]", "::1"].includes(url.hostname)
    );
  } catch {
    return false;
  }
}

export function formatTime(value: string | null | undefined) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export function durationLabel(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(remainingSeconds).padStart(2, "0")}`;
}

export function stateLabel(state: CampaignState) {
  return {
    created: "Preparando",
    running: "Em execução",
    waiting_approval: "Aguardando aprovação",
    stopped: "Interrompida",
    finished: "Concluída",
    failed: "Recusada / falhou",
  }[state];
}

export function phaseLabel(phase: CampaignMove["phase"]) {
  return {
    opening: "Abertura",
    middlegame: "Meio-jogo",
    endgame: "Final",
  }[phase];
}

export function gradeLabel(grade: MoveGrade | null) {
  if (!grade) return "Aguardando resultado";
  return {
    brilliant: "Brilhante",
    great: "Ótimo",
    best: "Melhor lance",
    good: "Bom",
    inaccuracy: "Imprecisão",
    mistake: "Erro",
    miss: "Não executado",
    blunder: "Erro grave",
    inconclusive: "Inconclusivo",
  }[grade];
}

export function gradeTone(grade: MoveGrade | null) {
  if (!grade) return "border-white/10 text-zinc-400";
  if (["brilliant", "great", "best", "good"].includes(grade))
    return "border-emerald-400/30 bg-emerald-400/10 text-emerald-300";
  if (["inaccuracy", "mistake"].includes(grade))
    return "border-amber-400/30 bg-amber-400/10 text-amber-200";
  if (["miss", "blunder"].includes(grade))
    return "border-rose-400/30 bg-rose-400/10 text-rose-300";
  return "border-white/10 bg-white/[0.04] text-zinc-400";
}

export function statusTag(move: CampaignMove): {
  label: string;
  className: string;
} {
  if (move.approval === "pending")
    return {
      label: "Pendente",
      className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    };
  if (move.approval === "denied")
    return {
      label: "Bloqueado",
      className: "border-white/10 bg-white/[0.04] text-zinc-400",
    };
  if (move.status === "fail")
    return {
      label: "Falha",
      className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    };
  if (move.status === "warning")
    return {
      label: "Atenção",
      className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    };
  if (move.status === "pass")
    return {
      label: "Validado",
      className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    };
  return {
    label: "Inconclusivo",
    className: "border-white/10 bg-white/[0.04] text-zinc-400",
  };
}

export function moveTone(move: CampaignMove) {
  if (move.approval === "pending") return "border-amber-400/40 bg-amber-400/5";
  if (move.approval === "denied") return "border-white/10 bg-white/[0.02]";
  if (move.status === "fail") return "border-rose-400/30 bg-rose-400/[0.04]";
  if (move.status === "warning") return "border-amber-400/30 bg-amber-400/[0.04]";
  if (move.status === "pass") return "border-emerald-400/20 bg-emerald-400/[0.03]";
  return "border-white/10 bg-white/[0.02]";
}

export function MoveIcon({ move }: { move: CampaignMove }) {
  if (move.approval === "pending")
    return <LockKeyhole className="size-3.5 text-amber-300" />;
  if (move.approval === "denied")
    return <X className="size-3.5 text-zinc-500" />;
  if (move.status === "fail")
    return <AlertTriangle className="size-3.5 text-rose-400" />;
  if (move.status === "warning")
    return <AlertTriangle className="size-3.5 text-amber-300" />;
  if (move.status === "pass")
    return <Check className="size-3.5 text-emerald-400" />;
  return <Circle className="size-3.5 text-zinc-500" />;
}
