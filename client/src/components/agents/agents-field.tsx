import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ChevronLeft, ChevronRight, Crown } from "lucide-react";
import { useMemo, useState } from "react";
import {
  ACCENT,
  FIELD_AGENTS,
  deriveAgentActivity,
  movesForAgent,
  participationForAgent,
  type AgentDef,
} from "@/data/agents";
import { safeHttpUrl } from "@/components/campanha/helpers";
import type {
  AgentParticipation,
  Campaign,
} from "@/components/campanha/types";
import { AgentsConstellation } from "./agents-constellation";

interface AgentsFieldProps {
  campaign: Campaign | null;
  participation: AgentParticipation[] | null;
}

interface AgentStats {
  movesRecommended: number;
  findings: number;
  techniques: string[];
}

function statsFor(
  agent: AgentDef,
  campaign: Campaign | null,
  participation: AgentParticipation[] | null,
): AgentStats {
  const part = participationForAgent(agent, participation);
  const moves = movesForAgent(agent, campaign);

  // Achados confirmados (fail/warning não descartados), derivados dos lances.
  const derivedFindings = moves.filter(
    (m) =>
      (m.status === "fail" || m.status === "warning") &&
      m.verdict !== "discarded" &&
      m.approval !== "denied",
  ).length;
  const derivedTechniques = Array.from(
    new Set(
      moves
        .map((m) => m.attack_technique_id)
        .filter((id): id is string => Boolean(id)),
    ),
  );

  if (agent.master) {
    return {
      movesRecommended: moves.length,
      findings: derivedFindings,
      techniques: derivedTechniques,
    };
  }

  return {
    movesRecommended: part?.moves_recommended ?? moves.length,
    findings: part?.findings ?? derivedFindings,
    techniques:
      part?.techniques_used && part.techniques_used.length > 0
        ? part.techniques_used
        : derivedTechniques,
  };
}

export function AgentsField({ campaign, participation }: AgentsFieldProps) {
  const [index, setIndex] = useState(0);
  const agents = FIELD_AGENTS;
  const selected = agents[index] ?? agents[0];

  const selectAgent = (agent: AgentDef) => {
    const next = agents.findIndex((a) => a.id === agent.id);
    if (next >= 0) setIndex(next);
  };

  const go = (dir: 1 | -1) =>
    setIndex((i) => (i + dir + agents.length) % agents.length);

  return (
    <div className="flex flex-col gap-4">
      <AgentsConstellation
        campaign={campaign}
        selectedId={selected.id}
        onSelect={selectAgent}
      />

      <AgentSlide
        agent={selected}
        campaign={campaign}
        participation={participation}
        onPrev={() => go(-1)}
        onNext={() => go(1)}
      />

      {/* indicadores do slider */}
      <div className="flex items-center justify-center gap-1.5">
        {agents.map((agent, i) => {
          const accent = ACCENT[agent.accent];
          const active = i === index;
          return (
            <button
              key={agent.id}
              type="button"
              aria-label={`Ver ${agent.name}`}
              aria-current={active}
              onClick={() => setIndex(i)}
              className={`h-1.5 rounded-full transition-all ${
                active ? `w-5 ${accent.dot}` : "w-1.5 bg-border hover:bg-foreground/30"
              }`}
            />
          );
        })}
      </div>
    </div>
  );
}

function AgentSlide({
  agent,
  campaign,
  participation,
  onPrev,
  onNext,
}: {
  agent: AgentDef;
  campaign: Campaign | null;
  participation: AgentParticipation[] | null;
  onPrev: () => void;
  onNext: () => void;
}) {
  const reduce = useReducedMotion();
  const accent = ACCENT[agent.accent];
  const Icon = agent.icon;
  const activity = useMemo(
    () => deriveAgentActivity(agent, campaign),
    [agent, campaign],
  );
  const stats = useMemo(
    () => statsFor(agent, campaign, participation),
    [agent, campaign, participation],
  );

  const statusText = activity.working
    ? "Trabalhando agora"
    : activity.done
      ? "Concluiu sua parte"
      : "Em espera";

  return (
    <div
      className={`relative overflow-hidden rounded-2xl border p-4 backdrop-blur-sm ${accent.border} bg-card/60`}
    >
      {!reduce && (
        <motion.span
          aria-hidden
          className={`pointer-events-none absolute inset-0 -z-10 bg-gradient-to-br ${accent.gradient}`}
          animate={{ opacity: activity.working ? [0.35, 0.7, 0.35] : 0.3 }}
          transition={{ duration: 2.6, repeat: Infinity, ease: "easeInOut" }}
        />
      )}

      {/* navegação */}
      <button
        type="button"
        aria-label="Agente anterior"
        onClick={onPrev}
        className="absolute left-2 top-1/2 z-10 grid size-7 -translate-y-1/2 place-items-center rounded-full border border-border/60 bg-background/70 text-muted-foreground backdrop-blur transition-colors hover:text-foreground"
      >
        <ChevronLeft className="size-4" />
      </button>
      <button
        type="button"
        aria-label="Próximo agente"
        onClick={onNext}
        className="absolute right-2 top-1/2 z-10 grid size-7 -translate-y-1/2 place-items-center rounded-full border border-border/60 bg-background/70 text-muted-foreground backdrop-blur transition-colors hover:text-foreground"
      >
        <ChevronRight className="size-4" />
      </button>

      <AnimatePresence mode="wait">
        <motion.div
          key={agent.id}
          initial={{ opacity: 0, x: 12 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: -12 }}
          transition={{ duration: 0.22 }}
          className="px-6"
        >
          <div className="flex items-center gap-3">
            <span
              className={`grid size-12 shrink-0 place-items-center rounded-xl border ${accent.border} ${accent.soft}`}
            >
              <Icon className={`size-6 ${accent.text}`} />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <p className="truncate text-sm font-semibold text-foreground">
                  {agent.name}
                </p>
                {agent.master && (
                  <span className="inline-flex items-center gap-1 rounded border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-primary">
                    <Crown className="size-3" />
                    Principal
                  </span>
                )}
              </div>
              <p className="truncate text-[11px] text-muted-foreground">
                {agent.role}
              </p>
            </div>
            <span
              className={`shrink-0 text-[10px] font-medium ${
                activity.working
                  ? accent.text
                  : activity.done
                    ? "text-sky-300"
                    : "text-muted-foreground"
              }`}
            >
              {statusText}
            </span>
          </div>

          {agent.tacticId && (
            <div className="mt-3">
              <span
                className={`inline-block rounded-md border px-1.5 py-0.5 text-[10px] ${accent.border} ${accent.text}`}
              >
                {agent.tacticId} · {agent.tacticName}
              </span>
            </div>
          )}

          <p className="mt-3 text-xs leading-relaxed text-foreground/90">
            {agent.description}
          </p>

          <ul className="mt-3 space-y-1.5">
            {agent.does.map((item) => (
              <li
                key={item}
                className="flex items-start gap-2 text-[11px] leading-relaxed text-muted-foreground"
              >
                <span
                  className={`mt-1.5 size-1.5 shrink-0 rounded-full ${accent.dot}`}
                />
                {item}
              </li>
            ))}
          </ul>

          {/* métricas */}
          <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border/50 pt-3">
            <Metric
              value={stats.movesRecommended}
              label={agent.master ? "lances" : "recomendou"}
            />
            <Metric value={stats.findings} label="achados" accent={accent.text} />
            <Metric value={stats.techniques.length} label="técnicas" />
          </div>

          {stats.techniques.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-1.5">
              {stats.techniques.map((tech) => {
                const href = safeHttpUrl(
                  `https://attack.mitre.org/techniques/${encodeURIComponent(tech)}`,
                );
                const chip = (
                  <span
                    className={`rounded-md border px-1.5 py-0.5 font-mono text-[10px] ${accent.border} ${accent.text}`}
                  >
                    {tech}
                  </span>
                );
                return href ? (
                  <a
                    key={tech}
                    href={href}
                    target="_blank"
                    rel="noreferrer noopener"
                    className="inline-flex transition-opacity hover:opacity-80"
                  >
                    {chip}
                  </a>
                ) : (
                  <span key={tech} className="inline-flex">
                    {chip}
                  </span>
                );
              })}
            </div>
          )}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

function Metric({
  value,
  label,
  accent = "text-foreground",
}: {
  value: number;
  label: string;
  accent?: string;
}) {
  return (
    <div className="text-center">
      <p className={`text-lg font-bold tabular-nums ${accent}`}>{value}</p>
      <p className="text-[10px] text-muted-foreground">{label}</p>
    </div>
  );
}
