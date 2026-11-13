import { motion, useReducedMotion } from "motion/react";
import {
  ACCENT,
  AGENTS,
  deriveAgentActivity,
  type AgentActivity,
} from "@/data/agents";
import { fadeUp, staggerContainer } from "@/lib/motion";
import type { Campaign } from "@/components/campanha/types";

interface AgentRosterProps {
  campaign: Campaign | null;
}

export function AgentRoster({ campaign }: AgentRosterProps) {
  const activities = AGENTS.map((agent) =>
    deriveAgentActivity(agent, campaign),
  );

  return (
    <motion.div
      variants={staggerContainer(0.07)}
      initial="hidden"
      animate="show"
      className="grid gap-2.5"
    >
      {activities.map((activity) => (
        <AgentCard key={activity.agent.id} activity={activity} />
      ))}
    </motion.div>
  );
}

function statusMeta(activity: AgentActivity) {
  if (activity.working)
    return { label: "Trabalhando", className: "text-emerald-300" };
  if (activity.done) return { label: "Concluído", className: "text-sky-300" };
  return { label: "Em espera", className: "text-muted-foreground" };
}

function AgentCard({ activity }: { activity: AgentActivity }) {
  const reduce = useReducedMotion();
  const { agent, handled, lastTechnique, working } = activity;
  const accent = ACCENT[agent.accent];
  const Icon = agent.icon;
  const status = statusMeta(activity);

  return (
    <motion.div
      variants={fadeUp}
      className={`relative overflow-hidden rounded-2xl border p-3.5 backdrop-blur-sm transition-colors ${
        working
          ? `${accent.border} bg-card/70`
          : "border-border/60 bg-card/40"
      }`}
    >
      {working && !reduce && (
        <motion.span
          aria-hidden
          className={`absolute inset-0 -z-10 bg-gradient-to-r ${accent.gradient}`}
          animate={{ opacity: [0.35, 0.7, 0.35] }}
          transition={{ duration: 2.4, repeat: Infinity, ease: "easeInOut" }}
        />
      )}
      <div className="flex items-center gap-3">
        <span
          className={`grid size-10 shrink-0 place-items-center rounded-xl border ${
            working ? `${accent.border} ${accent.soft}` : "border-border/60 bg-muted/30"
          }`}
        >
          <Icon
            className={`size-5 ${working ? accent.text : "text-muted-foreground"}`}
          />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <p className="truncate text-sm font-semibold text-foreground">
              {agent.name}
            </p>
            {agent.master && (
              <span className="rounded border border-primary/30 bg-primary/10 px-1.5 text-[9px] font-semibold uppercase tracking-wider text-primary">
                Mestre
              </span>
            )}
          </div>
          <p className="truncate text-[11px] text-muted-foreground">
            {agent.role}
          </p>
        </div>
        <div className="shrink-0 text-right">
          <div className="flex items-center justify-end gap-1.5">
            {working && (
              <span className="flex gap-0.5">
                {[0, 1, 2].map((i) => (
                  <motion.span
                    key={i}
                    className={`inline-block size-1 rounded-full ${accent.dot}`}
                    animate={reduce ? undefined : { opacity: [0.3, 1, 0.3] }}
                    transition={{
                      duration: 1,
                      repeat: Infinity,
                      delay: i * 0.18,
                    }}
                  />
                ))}
              </span>
            )}
            <span className={`text-[11px] font-medium ${status.className}`}>
              {status.label}
            </span>
          </div>
          <p className="mt-0.5 text-[10px] text-muted-foreground">
            {handled} {handled === 1 ? "lance" : "lances"}
          </p>
        </div>
      </div>
      {(agent.tacticId || lastTechnique) && (
        <div className="mt-2.5 flex flex-wrap items-center gap-1.5 border-t border-border/50 pt-2.5">
          {agent.tacticId && (
            <span
              className={`rounded-md border px-1.5 py-0.5 text-[10px] ${accent.border} ${accent.text}`}
            >
              {agent.tacticId} · {agent.tacticName}
            </span>
          )}
          {lastTechnique && (
            <span className="truncate text-[10px] text-muted-foreground">
              Última técnica: {lastTechnique}
            </span>
          )}
        </div>
      )}
    </motion.div>
  );
}
