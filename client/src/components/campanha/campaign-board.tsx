import {
  Activity,
  Bot,
  Bug,
  Check,
  ChevronRight,
  Circle,
  Copy,
  ExternalLink,
  FileDown,
  FileSearch,
  FileText,
  LoaderCircle,
  ScanSearch,
  ShieldAlert,
  Square,
  Terminal,
  Wrench,
  type LucideIcon,
} from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useState, type ReactNode } from "react";
import {
  MoveIcon,
  formatTime,
  gradeLabel,
  gradeTone,
  moveTone,
  phaseLabel,
  safeHttpUrl,
  statusTag,
} from "./helpers";
import type { Campaign, CampaignMove } from "./types";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { ApiErrorState } from "./api-error-state";

interface CampaignBoardProps {
  campaign: Campaign;
  latestMove: CampaignMove | null;
  active: boolean;
  campaignError: string;
  isStopping: boolean;
  stopError: string;
  onStop: () => void;
  onDownloadReport: () => void;
  isDownloadingReport: boolean;
  downloadError: string;
  canOpenReport: boolean;
  onOpenReport: () => void;
  canGenerateCves: boolean;
  isGeneratingCves: boolean;
  onGenerateCves: () => void;
}

/* ------------------------------------------------------------------ shell */

function Panel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`flex min-w-0 flex-col overflow-hidden rounded-2xl border border-border/60 bg-card/50 backdrop-blur-sm ${className}`}
    >
      {children}
    </section>
  );
}

function PanelHead({
  icon: Icon,
  title,
  accent = "text-muted-foreground",
  live = false,
  right,
}: {
  icon: LucideIcon;
  title: string;
  accent?: string;
  live?: boolean;
  right?: ReactNode;
}) {
  return (
    <header className="flex items-center justify-between gap-2 border-b border-border/50 px-4 py-3">
      <div className="flex min-w-0 items-center gap-2">
        <span className="relative flex size-4 items-center justify-center">
          <Icon className={`size-4 ${accent}`} />
          {live && (
            <motion.span
              className="absolute -right-0.5 -top-0.5 size-1.5 rounded-full bg-emerald-400"
              animate={{ opacity: [1, 0.3, 1] }}
              transition={{ duration: 1.4, repeat: Infinity }}
            />
          )}
        </span>
        <h3 className="truncate text-[11px] font-semibold uppercase tracking-[0.16em] text-foreground/80">
          {title}
        </h3>
      </div>
      {right && <div className="flex shrink-0 items-center gap-2">{right}</div>}
    </header>
  );
}

/* ------------------------------------------------------------------ board */

export function CampaignBoard({
  campaign,
  latestMove,
  active,
  campaignError,
  isStopping,
  stopError,
  onStop,
  onDownloadReport,
  isDownloadingReport,
  downloadError,
  canOpenReport,
  onOpenReport,
  canGenerateCves,
  isGeneratingCves,
  onGenerateCves,
}: CampaignBoardProps) {
  const [selectedMove, setSelectedMove] = useState<number | null>(null);
  const activeMove =
    campaign.moves.find((m) => m.move === selectedMove) ?? latestMove;
  const findingsCount = campaign.moves.filter(
    (m) => m.status && m.status !== "pass" && m.approval !== "denied",
  ).length;

  return (
    <div className="grid items-start gap-4 lg:grid-cols-[minmax(0,1.55fr)_minmax(0,1fr)]">
      <TimelineCard
        campaign={campaign}
        active={active}
        error={campaignError}
        stopError={stopError}
        isStopping={isStopping}
        onStop={onStop}
        selectedMove={activeMove?.move ?? null}
        onSelectMove={setSelectedMove}
      />

      <div className="flex min-w-0 flex-col gap-4">
        <ResultCard
          move={activeMove}
          findingsCount={findingsCount}
          canOpenReport={canOpenReport}
          onOpenReport={onOpenReport}
          onDownloadReport={onDownloadReport}
          isDownloadingReport={isDownloadingReport}
          downloadError={downloadError}
          canGenerateCves={canGenerateCves}
          isGeneratingCves={isGeneratingCves}
          onGenerateCves={onGenerateCves}
        />
      </div>
    </div>
  );
}

/* --------------------------------------------------------------- timeline */

function TimelineCard({
  campaign,
  active,
  error,
  stopError,
  isStopping,
  onStop,
  selectedMove,
  onSelectMove,
}: {
  campaign: Campaign;
  active: boolean;
  error: string;
  stopError: string;
  isStopping: boolean;
  onStop: () => void;
  selectedMove: number | null;
  onSelectMove: (move: number) => void;
}) {
  const href = safeHttpUrl(campaign.config.origin);
  const host = (() => {
    try {
      return new URL(campaign.config.origin).host;
    } catch {
      return campaign.config.origin;
    }
  })();
  const moves = [...campaign.moves].sort((a, b) => b.move - a.move);

  return (
    <Panel>
      <PanelHead
        icon={Activity}
        title="Linha do tempo"
        accent="text-primary"
        live={active}
        right={
          <>
            <span className="rounded-md border border-border/60 bg-muted/30 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
              {String(campaign.moves.length).padStart(2, "0")}
            </span>
            {active && (
              <Button
                variant="destructive"
                size="xs"
                disabled={isStopping}
                onClick={onStop}
                title="Parada de emergência"
              >
                {isStopping ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Square />
                )}
                Parar
              </Button>
            )}
          </>
        }
      />

      {host && (
        <div className="flex items-center gap-2 border-b border-border/50 px-4 py-2">
          <span className="size-1.5 rounded-full bg-emerald-400/70" />
          <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-muted-foreground">
            {host}
          </span>
          {href && (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="inline-flex items-center gap-1 text-[10px] uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
            >
              Abrir <ExternalLink className="size-3" />
            </a>
          )}
        </div>
      )}

      <div className="timeline-scrollbar max-h-[30rem] min-h-0 overflow-y-auto p-2">
        {(stopError || error) && (
          <div className="mb-2 px-1">
            <ApiErrorState compact message={stopError || error} />
          </div>
        )}

        {moves.length === 0 ? (
          <div className="flex min-h-48 flex-col items-center justify-center gap-3 px-4 text-center">
            {active ? (
              <LoaderCircle className="size-5 animate-spin text-primary" />
            ) : (
              <Circle className="size-5 text-muted-foreground/50" />
            )}
            <p className="text-sm text-muted-foreground">
              {campaign.state === "failed"
                ? "Bloqueado: fora do escopo autorizado."
                : "Aguardando o primeiro lance do agente..."}
            </p>
          </div>
        ) : (
          <ol className="flex flex-col gap-1.5">
            {moves.map((move) => {
              const tag = statusTag(move);
              const isSelected = move.move === selectedMove;
              return (
                <motion.li
                  key={move.move}
                  layout
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.28 }}
                >
                  <button
                    type="button"
                    aria-pressed={isSelected}
                    onClick={() => onSelectMove(move.move)}
                    className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/40 ${moveTone(
                      move,
                    )} ${
                      isSelected
                        ? "ring-1 ring-primary/60"
                        : "hover:border-foreground/20"
                    }`}
                  >
                    <span className="grid size-7 shrink-0 place-items-center rounded-full border border-border/60 bg-background">
                      <MoveIcon move={move} />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-center gap-2">
                        <span className="font-mono text-[10px] text-muted-foreground">
                          #{String(move.move).padStart(2, "0")}
                        </span>
                        <span className="truncate text-sm font-medium text-foreground">
                          {move.title}
                        </span>
                      </span>
                      <span className="mt-0.5 flex items-center gap-1.5 text-[10px] text-muted-foreground">
                        <span>{phaseLabel(move.phase)}</span>
                        <span>·</span>
                        <span>{gradeLabel(move.grade)}</span>
                        <span>·</span>
                        <span className="font-mono">
                          {formatTime(move.started_at)}
                        </span>
                      </span>
                    </span>
                    <Badge
                      variant="outline"
                      className={`shrink-0 uppercase tracking-wider ${tag.className}`}
                    >
                      {tag.label}
                    </Badge>
                    <ChevronRight
                      className={`size-4 shrink-0 transition-colors ${
                        isSelected ? "text-primary" : "text-muted-foreground/40"
                      }`}
                    />
                  </button>
                </motion.li>
              );
            })}
          </ol>
        )}
      </div>
    </Panel>
  );
}

/* ----------------------------------------------------------------- result */

const VERDICT: Record<string, { label: string; className: string }> = {
  confirmed: {
    label: "Confirmado",
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
  discarded: {
    label: "Descartado",
    className: "border-border/60 bg-muted/30 text-muted-foreground",
  },
  inconclusive: {
    label: "Não reconfirmado",
    className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  },
};

function ResultCard({
  move,
  findingsCount,
  canOpenReport,
  onOpenReport,
  onDownloadReport,
  isDownloadingReport,
  downloadError,
  canGenerateCves,
  isGeneratingCves,
  onGenerateCves,
}: {
  move: CampaignMove | null;
  findingsCount: number;
  canOpenReport: boolean;
  onOpenReport: () => void;
  onDownloadReport: () => void;
  isDownloadingReport: boolean;
  downloadError: string;
  canGenerateCves: boolean;
  isGeneratingCves: boolean;
  onGenerateCves: () => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);
  const [copied, setCopied] = useState(false);
  const [lastMove, setLastMove] = useState(move?.move ?? null);
  if ((move?.move ?? null) !== lastMove) {
    setLastMove(move?.move ?? null);
    setShowEvidence(false);
  }

  const copyReproduce = (text: string) => {
    void navigator.clipboard
      ?.writeText(text)
      .then(() => {
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1600);
      })
      .catch(() => undefined);
  };

  const attackHref = move ? safeHttpUrl(move.attack_url) : null;
  const verdict = move?.verdict ? VERDICT[move.verdict] : null;

  return (
    <Panel>
      <PanelHead
        icon={ScanSearch}
        title="Resultado do lance"
        accent="text-primary"
        right={
          <span className="font-mono text-[10px] text-muted-foreground">
            {findingsCount} achado{findingsCount === 1 ? "" : "s"}
          </span>
        }
      />

      <div className="timeline-scrollbar max-h-[32rem] min-h-0 overflow-y-auto">
        {move ? (
          <AnimatePresence mode="wait">
            <motion.div
              key={move.move}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.22 }}
              className="space-y-4 p-4"
            >
              <div>
                <div className="flex items-center justify-between gap-2">
                  <Badge
                    variant="outline"
                    className={`uppercase tracking-wider ${gradeTone(move.grade)}`}
                  >
                    {gradeLabel(move.grade)}
                  </Badge>
                  <span className="font-mono text-[10px] text-muted-foreground">
                    #{String(move.move).padStart(2, "0")} · {move.test_id}
                  </span>
                </div>
                <h3 className="mt-2 text-base font-semibold tracking-tight text-foreground">
                  {move.title}
                </h3>
                {(verdict || move.recommended_by || move.attack_technique_id) && (
                  <div className="mt-2 flex flex-wrap items-center gap-1.5">
                    {verdict && (
                      <Badge
                        variant="outline"
                        className={`uppercase tracking-wider ${verdict.className}`}
                      >
                        {verdict.label}
                      </Badge>
                    )}
                    {move.recommended_by && (
                      <Badge
                        variant="outline"
                        className="border-sky-400/30 bg-sky-400/10 text-sky-300"
                      >
                        {move.recommended_by}
                      </Badge>
                    )}
                    {move.attack_technique_id &&
                      (attackHref ? (
                        <a
                          href={attackHref}
                          target="_blank"
                          rel="noreferrer noopener"
                          className="inline-flex"
                        >
                          <Badge
                            variant="outline"
                            className="border-violet-400/30 bg-violet-400/10 text-violet-300 hover:bg-violet-400/20"
                          >
                            ATT&CK {move.attack_technique_id}
                          </Badge>
                        </a>
                      ) : (
                        <Badge
                          variant="outline"
                          className="border-violet-400/30 bg-violet-400/10 text-violet-300"
                        >
                          ATT&CK {move.attack_technique_id}
                        </Badge>
                      ))}
                  </div>
                )}
              </div>

              <Section icon={ShieldAlert} iconClass="text-amber-300" label="Risco observado">
                {move.impact ||
                  move.explanation ||
                  "Sem risco relevante registrado para este lance."}
              </Section>

              {move.exploitation_scenario && (
                <Section
                  icon={Bug}
                  iconClass="text-rose-300"
                  label="Como seria explorado"
                >
                  {move.exploitation_scenario}
                </Section>
              )}

              <Section icon={Wrench} iconClass="text-primary" label="Solução sugerida" tone="primary">
                {move.recommendation || "Nenhuma ação necessária até aqui."}
              </Section>

              {move.ai_explanation && (
                <Section
                  icon={Bot}
                  iconClass="text-sky-300"
                  label="Comentário do penteador (IA)"
                  badge={
                    move.ai_review?.verdict === "approved"
                      ? "revisado pelo juiz"
                      : undefined
                  }
                >
                  {move.ai_explanation}
                </Section>
              )}

              {move.reproduce.length > 0 && (
                <div>
                  <div className="flex items-center justify-between">
                    <SectionLabel icon={Terminal} iconClass="text-muted-foreground">
                      Como reproduzir
                    </SectionLabel>
                    <Button
                      variant="ghost"
                      size="icon-xs"
                      aria-label="Copiar comandos"
                      className="text-muted-foreground hover:bg-foreground/10 hover:text-foreground"
                      onClick={() => copyReproduce(move.reproduce.join("\n"))}
                    >
                      {copied ? (
                        <Check className="size-3.5" />
                      ) : (
                        <Copy className="size-3.5" />
                      )}
                    </Button>
                  </div>
                  <pre className="mt-1.5 overflow-x-auto rounded-lg border border-border/60 bg-background/60 p-2.5 font-mono text-[11px] leading-relaxed text-foreground/90">
                    {move.reproduce.join("\n")}
                  </pre>
                </div>
              )}

              {move.evidence.length > 0 && (
                <div>
                  <Button
                    size="sm"
                    variant="outline"
                    className="w-full border-border/60 bg-card/50 text-foreground/90 hover:bg-foreground/5"
                    onClick={() => setShowEvidence((v) => !v)}
                  >
                    <FileSearch />
                    {showEvidence
                      ? "Ocultar evidência"
                      : `Ver ${move.evidence.length} evidência${move.evidence.length === 1 ? "" : "s"}`}
                  </Button>
                  {showEvidence && (
                    <ul className="mt-2 flex flex-col gap-2">
                      {move.evidence.map((item) => (
                        <li
                          key={item.id}
                          className="rounded-lg border border-border/60 bg-background/50 p-2.5 text-xs"
                        >
                          <p className="break-all font-mono text-foreground/90">
                            {item.request}
                          </p>
                          {item.response_status !== null && (
                            <span className="mt-1 inline-block rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                              HTTP {item.response_status}
                            </span>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </motion.div>
          </AnimatePresence>
        ) : (
          <div className="flex min-h-48 flex-col items-center justify-center gap-2 p-6 text-center">
            <ScanSearch className="size-6 text-muted-foreground/50" />
            <p className="text-sm text-muted-foreground">
              Selecione um lance na linha do tempo para ver o resultado.
            </p>
          </div>
        )}
      </div>

      <div className="space-y-2 border-t border-border/50 p-4">
        {downloadError && <ApiErrorState compact message={downloadError} />}
        {canOpenReport && (
          <Button
            onClick={onOpenReport}
            className="w-full bg-primary text-primary-foreground hover:bg-primary/90"
          >
            <FileText />
            Ver Revisão da Penteada
          </Button>
        )}
        {canGenerateCves && (
          <Button
            variant="outline"
            disabled={isGeneratingCves}
            onClick={onGenerateCves}
            className="w-full border-rose-400/30 bg-rose-400/[0.06] text-rose-200 hover:bg-rose-400/10"
          >
            {isGeneratingCves ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Bug />
            )}
            Gerar CVEs (NVD)
          </Button>
        )}
        <Button
          variant="outline"
          disabled={isDownloadingReport}
          onClick={onDownloadReport}
          className="w-full border-border/60 bg-card/50 text-foreground hover:bg-foreground/5"
        >
          {isDownloadingReport ? (
            <LoaderCircle className="animate-spin" />
          ) : (
            <FileDown />
          )}
          Baixar relatório
        </Button>
      </div>
    </Panel>
  );
}

/* ---------------------------------------------------------------- bits */

function SectionLabel({
  icon: Icon,
  iconClass = "",
  children,
}: {
  icon: LucideIcon;
  iconClass?: string;
  children: ReactNode;
}) {
  return (
    <p className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
      <Icon className={`size-3.5 ${iconClass}`} />
      {children}
    </p>
  );
}

function Section({
  icon,
  iconClass,
  label,
  badge,
  tone = "default",
  children,
}: {
  icon: LucideIcon;
  iconClass?: string;
  label: string;
  badge?: string;
  tone?: "default" | "primary";
  children: ReactNode;
}) {
  return (
    <div>
      <div className="flex items-center gap-2">
        <SectionLabel icon={icon} iconClass={iconClass}>
          {label}
        </SectionLabel>
        {badge && (
          <span className="rounded bg-emerald-400/10 px-1 text-[9px] text-emerald-300">
            {badge}
          </span>
        )}
      </div>
      <p
        className={`mt-1 text-xs leading-relaxed ${
          tone === "primary" ? "text-primary/90" : "text-foreground/90"
        }`}
      >
        {children}
      </p>
    </div>
  );
}

