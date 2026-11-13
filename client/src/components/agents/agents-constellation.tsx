import { motion, useReducedMotion } from "motion/react";
import {
  ACCENT,
  AGENTS,
  deriveAgentActivity,
  type AgentActivity,
} from "@/data/agents";
import type { Campaign } from "@/components/campanha/types";

interface AgentsConstellationProps {
  campaign: Campaign | null;
}

const RADIUS = 34; // % do contêiner

function nodePosition(index: number, total: number) {
  const angle = (index / total) * 2 * Math.PI; // começa à direita
  return {
    left: 50 + RADIUS * Math.cos(angle),
    top: 50 + RADIUS * Math.sin(angle),
  };
}

export function AgentsConstellation({ campaign }: AgentsConstellationProps) {
  const reduce = useReducedMotion();
  const master = AGENTS.find((a) => a.master) ?? AGENTS[0];
  const specialists = AGENTS.filter((a) => !a.master);
  const masterActivity = deriveAgentActivity(master, campaign);
  const activities = specialists.map((agent) =>
    deriveAgentActivity(agent, campaign),
  );

  return (
    <div className="relative mx-auto aspect-square w-full max-w-[340px]">
      {/* feixes */}
      <svg
        viewBox="0 0 100 100"
        className="absolute inset-0 size-full"
        aria-hidden
      >
        {specialists.map((agent, i) => {
          const pos = nodePosition(i, specialists.length);
          const accent = ACCENT[agent.accent];
          const working = activities[i].working;
          return (
            <g key={agent.id}>
              <line
                x1="50"
                y1="50"
                x2={pos.left}
                y2={pos.top}
                className={working ? accent.text : "text-border"}
                stroke="currentColor"
                strokeWidth={working ? 0.7 : 0.4}
                strokeOpacity={working ? 0.9 : 0.35}
                strokeDasharray="2 2"
              />
              {working && !reduce && (
                <motion.circle
                  r="1.4"
                  className={accent.text}
                  fill="currentColor"
                  initial={{ cx: 50, cy: 50 }}
                  animate={{ cx: [50, pos.left], cy: [50, pos.top] }}
                  transition={{
                    duration: 1.4,
                    repeat: Infinity,
                    ease: "easeInOut",
                  }}
                />
              )}
            </g>
          );
        })}
      </svg>

      {/* nó central (mestre) */}
      <CenterNode activity={masterActivity} />

      {/* especialistas */}
      {specialists.map((agent, i) => {
        const pos = nodePosition(i, specialists.length);
        return (
          <OrbitNode
            key={agent.id}
            activity={activities[i]}
            left={pos.left}
            top={pos.top}
          />
        );
      })}
    </div>
  );
}

function CenterNode({ activity }: { activity: AgentActivity }) {
  const reduce = useReducedMotion();
  const { agent, working } = activity;
  const accent = ACCENT[agent.accent];
  const Icon = agent.icon;
  return (
    <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
      {working && !reduce && (
        <motion.span
          className={`absolute inset-0 rounded-full ${accent.soft}`}
          animate={{ scale: [1, 1.5], opacity: [0.5, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <motion.div
        animate={reduce ? undefined : { y: [0, -4, 0] }}
        transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}
        className={`relative grid size-20 place-items-center rounded-full border-2 ${accent.border} ${accent.soft} ${accent.glow} backdrop-blur-sm`}
      >
        <Icon className={`size-8 ${accent.text}`} />
      </motion.div>
      <p className="mt-2 text-center text-[11px] font-semibold text-foreground">
        {agent.name}
      </p>
    </div>
  );
}

function OrbitNode({
  activity,
  left,
  top,
}: {
  activity: AgentActivity;
  left: number;
  top: number;
}) {
  const reduce = useReducedMotion();
  const { agent, working, handled } = activity;
  const accent = ACCENT[agent.accent];
  const Icon = agent.icon;
  return (
    <motion.div
      className="absolute flex flex-col items-center"
      style={{ left: `${left}%`, top: `${top}%`, x: "-50%", y: "-50%" }}
      initial={{ opacity: 0, scale: 0.6 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ type: "spring", stiffness: 260, damping: 20 }}
    >
      {working && !reduce && (
        <motion.span
          className={`absolute top-0 size-14 rounded-full ${accent.soft}`}
          animate={{ scale: [1, 1.6], opacity: [0.45, 0] }}
          transition={{ duration: 1.8, repeat: Infinity, ease: "easeOut" }}
        />
      )}
      <div
        className={`relative grid size-14 place-items-center rounded-full border ${
          working ? `${accent.border} ${accent.glow}` : "border-border/70"
        } bg-card/70 backdrop-blur-sm transition-colors`}
      >
        <Icon
          className={`size-6 ${working ? accent.text : "text-muted-foreground"}`}
        />
        {handled > 0 && (
          <span
            className={`absolute -right-1 -top-1 grid size-5 place-items-center rounded-full border border-background text-[10px] font-bold text-background ${accent.dot}`}
          >
            {handled}
          </span>
        )}
      </div>
      <p className="mt-1.5 text-center text-[10px] font-medium text-muted-foreground">
        {agent.name}
      </p>
    </motion.div>
  );
}
