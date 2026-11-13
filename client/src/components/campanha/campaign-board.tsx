import {
  ArrowRight,
  Bot,
  Check,
  ChevronRight,
  Circle,
  Copy,
  Crown,
  ExternalLink,
  FileDown,
  FileSearch,
  FileText,
  Globe,
  LoaderCircle,
  LockKeyhole,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Square,
  Terminal,
  Wrench,
  X,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
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
  pendingAction: string;
  campaignError: string;
  actionError: string;
  onDecide: (moveNumber: number, decision: "approve" | "deny") => void;
  isStopping: boolean;
  stopError: string;
  onStop: () => void;
  onDownloadReport: () => void;
  isDownloadingReport: boolean;
  downloadError: string;
  canOpenReport: boolean;
  onOpenReport: () => void;
}

export function CampaignBoard({
  campaign,
  latestMove,
  active,
  pendingAction,
  campaignError,
  actionError,
  onDecide,
  isStopping,
  stopError,
  onStop,
  onDownloadReport,
  isDownloadingReport,
  downloadError,
  canOpenReport,
  onOpenReport,
}: CampaignBoardProps) {
  const pendingMoves = campaign.moves.filter(
    (move) => move.approval === "pending",
  );

  const [selectedMove, setSelectedMove] = useState<number | null>(null);
  const activeMove =
    campaign.moves.find((move) => move.move === selectedMove) ?? latestMove;

  return (
    <div className="mt-4 grid gap-3 lg:h-[calc(100svh-15rem)] lg:min-h-0 lg:grid-cols-[76px_minmax(0,1.5fr)_minmax(0,1fr)]">
      <AgentsRail />

      <div className="flex min-h-0 min-w-0 flex-col gap-3">
        <TimelineCard
          campaign={campaign}
          active={active}
          error={campaignError}
          selectedMove={activeMove?.move ?? null}
          onSelectMove={setSelectedMove}
          isStopping={isStopping}
          stopError={stopError}
          onStop={onStop}
        />
        <UrlBar origin={campaign.config.origin} />
      </div>

      <div className="flex min-w-0 flex-col gap-3">
        <ApprovalQueue
          pendingMoves={pendingMoves}
          pendingAction={pendingAction}
          actionError={actionError}
          onDecide={onDecide}
          onSelectMove={setSelectedMove}
        />
        <ResultsPanel
          move={activeMove}
          findingsCount={
            campaign.moves.filter(
              (move) =>
                move.status && move.status !== "pass" && move.approval !== "denied",
            ).length
          }
          onDownloadReport={onDownloadReport}
          isDownloadingReport={isDownloadingReport}
          downloadError={downloadError}
          canOpenReport={canOpenReport}
          onOpenReport={onOpenReport}
        />
      </div>
    </div>
  );
}

/* ---------------------------------------------------------------- Agents rail */

const PLACEHOLDER_AGENTS = [
  "Reconhecimento",
  "Exploração",
  "Evidências",
  "Relatório",
  "Revisão",
  "Escopo",
];

function AgentsRail() {
  return (
    <Card className="flex flex-row gap-3 border-white/10 bg-zinc-950/75 p-3 lg:flex-col lg:items-center lg:gap-2">
      <button
        type="button"
        aria-current="true"
        title="Agente Mestre Pent"
        className="grid size-11 shrink-0 place-items-center rounded-full border-2 border-rose-500/60 bg-rose-500/15 text-rose-300 ring-2 ring-rose-500/20"
      >
        <Crown className="size-5" />
      </button>
      <span className="hidden text-center text-[9px] uppercase leading-tight tracking-wider text-zinc-500 lg:block">
        Mestre Pent
      </span>

      <div className="mx-1 hidden h-px w-full bg-white/[0.07] lg:block" />

      <div className="flex gap-2 lg:flex-col lg:items-center">
        {PLACEHOLDER_AGENTS.map((label) => (
          <button
            key={label}
            type="button"
            disabled
            title={`${label} · em breve`}
            className="grid size-11 shrink-0 cursor-not-allowed place-items-center rounded-full border border-white/10 bg-white/[0.02] text-zinc-600"
          >
            <Bot className="size-5" />
          </button>
        ))}
      </div>

      <span className="mt-auto hidden text-center text-[9px] uppercase leading-tight tracking-wider text-zinc-600 lg:block">
        Outros agentes · em breve
      </span>
    </Card>
  );
}

/* ------------------------------------------------------------- Timeline (center) */

function TimelineCard({
  campaign,
  active,
  error,
  selectedMove,
  onSelectMove,
  isStopping,
  stopError,
  onStop,
}: {
  campaign: Campaign;
  active: boolean;
  error: string;
  selectedMove: number | null;
  onSelectMove: (move: number) => void;
  isStopping: boolean;
  stopError: string;
  onStop: () => void;
}) {
  const score = campaign.score;
  const evalPercent = score
    ? Math.min(100, Math.max(0, (score.eval_bar + 100) / 2))
    : 50;

  return (
    <Card className="flex min-h-0 flex-1 flex-col border-white/10 bg-zinc-950/75">
      <CardHeader className="gap-3 border-b border-white/[0.07] pb-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-zinc-300">
            <span className="size-2 animate-pulse rounded-full bg-rose-500" />
            Linha do tempo · ao vivo
          </CardTitle>
          <div className="flex items-center gap-2">
            <span className="rounded-md border border-white/10 px-2 py-1 font-mono text-[10px] text-zinc-500">
              {String(campaign.moves.length).padStart(2, "0")} lances
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
          </div>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between text-[10px] uppercase tracking-wider text-zinc-500">
            <span>Avaliação da partida</span>
            <span className="font-mono text-zinc-300">
              {score ? `${score.accuracy.toFixed(1)} acc` : "—"} ·{" "}
              {score
                ? `${score.eval_bar > 0 ? "+" : ""}${score.eval_bar.toFixed(0)}`
                : "—"}
            </span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-300 to-emerald-400 transition-all duration-500"
              style={{ width: `${evalPercent}%` }}
            />
          </div>
        </div>
      </CardHeader>

      <CardContent className="timeline-scrollbar min-h-0 flex-1 overflow-y-auto pt-2">
        {stopError && (
          <div className="mb-2">
            <ApiErrorState compact message={stopError} />
          </div>
        )}
        {error && <ApiErrorState compact message={error} />}
        {campaign.moves.length ? (
          <ol className="divide-y divide-white/[0.06]">
            {[...campaign.moves]
              .sort((a, b) => b.move - a.move)
              .map((move) => {
                const tag = statusTag(move);
                const isSelected = move.move === selectedMove;
                return (
                  <li key={move.move} className="py-1">
                    <button
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => onSelectMove(move.move)}
                      className={`w-full cursor-pointer rounded-xl border p-3 text-left transition-colors hover:border-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/40 ${moveTone(
                        move,
                      )} ${isSelected ? "ring-1 ring-rose-400/60" : ""}`}
                    >
                      <div className="flex items-start gap-3">
                        <div className="relative mt-0.5 grid size-6 shrink-0 place-items-center rounded-full border border-white/10 bg-zinc-950">
                          <MoveIcon move={move} />
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                              Lance {String(move.move).padStart(2, "0")} ·{" "}
                              {formatTime(move.started_at)}
                            </span>
                            <span className="rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[9px] text-zinc-500">
                              {move.test_id}
                            </span>
                          </div>
                          <h3 className="mt-1 text-sm font-medium text-zinc-200">
                            {move.title}
                          </h3>
                          <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-zinc-500">
                            <span>{phaseLabel(move.phase)}</span>
                            <span>·</span>
                            <span>{gradeLabel(move.grade)}</span>
                          </div>
                        </div>
                        <div className="flex shrink-0 flex-col items-end gap-2">
                          <Badge
                            variant="outline"
                            className={`uppercase tracking-wider ${tag.className}`}
                          >
                            {tag.label}
                          </Badge>
                          <ChevronRight
                            className={`size-4 transition-colors ${isSelected ? "text-rose-400" : "text-zinc-700"
                              }`}
                          />
                        </div>
                      </div>
                    </button>
                  </li>
                );
              })}
          </ol>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center gap-3 text-center">
            {active ? (
              <LoaderCircle className="size-5 animate-spin text-rose-400" />
            ) : (
              <Circle className="size-5 text-zinc-600" />
            )}
            <p className="text-sm text-zinc-400">
              {campaign.state === "failed"
                ? "Bloqueado: fora do escopo autorizado."
                : "Aguardando o primeiro lance do agente..."}
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function UrlBar({ origin }: { origin: string }) {
  // §6.3: só vira href se for http(s) de verdade.
  const href = safeHttpUrl(origin);
  return (
    <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-zinc-900/80 px-3 py-2">
      <Globe className="size-4 shrink-0 text-zinc-500" />
      <span className="min-w-0 flex-1 truncate font-mono text-xs text-zinc-300">
        {origin || "Alvo definido pelo servidor"}
      </span>
      {href && (
        <a
          href={href}
          target="_blank"
          rel="noreferrer noopener"
          className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-[10px] uppercase tracking-wider text-zinc-400 transition-colors hover:bg-white/5 hover:text-zinc-200"
        >
          Abrir
          <ExternalLink className="size-3" />
        </a>
      )}
    </div>
  );
}

/* ------------------------------------------------------- Approval queue (top-right) */

function ApprovalQueue({
  pendingMoves,
  pendingAction,
  actionError,
  onDecide,
  onSelectMove,
}: {
  pendingMoves: CampaignMove[];
  pendingAction: string;
  actionError: string;
  onDecide: CampaignBoardProps["onDecide"];
  onSelectMove: (move: number) => void;
}) {
  const notifiedMove = useRef<number | null>(null);
  const head = pendingMoves[0] ?? null;
  const headNumber = head?.move ?? null;

  useEffect(() => {
    if (headNumber === null) {
      notifiedMove.current = null;
      return;
    }
    if (notifiedMove.current === headNumber) return;
    notifiedMove.current = headNumber;
    playApprovalNotification();
  }, [headNumber]);

  return (
    <Card className="border-amber-400/20 bg-gradient-to-b from-amber-950/10 to-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <CardTitle className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-zinc-300">
          <LockKeyhole className="size-4 text-amber-300" />
          Ações do bot para aprovação
        </CardTitle>
        <Badge
          variant="outline"
          className="border-amber-400/30 bg-amber-400/10 uppercase tracking-wider text-amber-200"
        >
          {pendingMoves.length} na fila
        </Badge>
      </CardHeader>
      <CardContent className="pt-4">
        {pendingMoves.length === 0 ? (
          <div className="flex min-h-28 flex-col items-center justify-center gap-2 text-center">
            <ShieldCheck className="size-6 text-zinc-600" />
            <p className="text-sm text-zinc-400">
              Nenhuma ação aguardando aprovação.
            </p>
          </div>
        ) : (
          <>
            <ul className="space-y-2">
              {pendingMoves.map((move, index) => (
                <li key={move.move}>
                  <button
                    type="button"
                    onClick={() => onSelectMove(move.move)}
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors hover:border-white/20 ${index === 0
                      ? "border-amber-400/40 bg-amber-400/5"
                      : "border-white/10 bg-white/[0.02]"
                      }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="truncate text-sm font-medium text-zinc-200">
                        {move.title}
                      </span>
                      <span className="shrink-0 font-mono text-[10px] text-zinc-500">
                        {move.test_id}
                      </span>
                    </div>
                    {move.plan?.hypothesis && (
                      <p className="mt-1 line-clamp-1 text-xs text-zinc-500">
                        {move.plan.hypothesis}
                      </p>
                    )}
                  </button>
                </li>
              ))}
            </ul>

            {actionError && (
              <div className="mt-3">
                <ApiErrorState compact message={actionError} />
              </div>
            )}

            {head && (
              <div className="mt-4 flex items-center justify-between gap-2 border-t border-white/[0.07] pt-4">
                <span className="truncate text-[11px] text-zinc-500">
                  Decidindo lance {String(head.move).padStart(2, "0")}
                </span>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={Boolean(pendingAction)}
                    onClick={() => onDecide(head.move, "deny")}
                    className="border-white/10 bg-transparent text-zinc-300 hover:bg-white/5"
                  >
                    {pendingAction === `deny-${head.move}` ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <X />
                    )}
                    Negar
                  </Button>
                  <Button
                    size="sm"
                    disabled={Boolean(pendingAction)}
                    onClick={() => onDecide(head.move, "approve")}
                    className="bg-rose-600 text-white hover:bg-rose-500"
                  >
                    {pendingAction === `approve-${head.move}` ? (
                      <LoaderCircle className="animate-spin" />
                    ) : (
                      <ArrowRight />
                    )}
                    Avançar
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

/* ----------------------------------------------------- Results panel (bottom-right) */

const VERDICT_LABEL: Record<string, { label: string; className: string }> = {
  confirmed: {
    label: "Confirmado (2 observações)",
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
  discarded: {
    label: "Descartado: não se reproduziu",
    className: "border-white/15 bg-white/[0.04] text-zinc-400",
  },
  inconclusive: {
    label: "Não reconfirmado",
    className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  },
};

function ResultsPanel({
  move,
  findingsCount,
  onDownloadReport,
  isDownloadingReport,
  downloadError,
  canOpenReport,
  onOpenReport,
}: {
  move: CampaignMove | null;
  findingsCount: number;
  onDownloadReport: () => void;
  isDownloadingReport: boolean;
  downloadError: string;
  canOpenReport: boolean;
  onOpenReport: () => void;
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
  const verdict = move?.verdict ? VERDICT_LABEL[move.verdict] : null;

  return (
    <Card className="flex flex-1 flex-col border-rose-500/20 bg-gradient-to-b from-rose-950/15 to-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <CardTitle className="flex items-center gap-2 text-xs uppercase tracking-[0.16em] text-zinc-300">
          <ScanSearch className="size-4 text-rose-400" />
          Resultados e sugestões
        </CardTitle>
        <span className="font-mono text-[10px] text-zinc-500">
          {findingsCount} achado{findingsCount === 1 ? "" : "s"}
        </span>
      </CardHeader>
      <CardContent className="flex flex-1 flex-col pt-4">
        {move ? (
          <>
            <div className="flex items-center justify-between gap-3">
              <Badge
                variant="outline"
                className={`uppercase tracking-wider ${gradeTone(move.grade)}`}
              >
                {gradeLabel(move.grade)}
              </Badge>
              <span className="font-mono text-[10px] text-zinc-500">
                {move.test_id}
              </span>
            </div>
            <h3 className="mt-2 text-base font-semibold tracking-tight text-zinc-100">
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
                    Recomendado por: {move.recommended_by}
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
                        {move.attack_technique_name
                          ? ` · ${move.attack_technique_name}`
                          : ""}
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

            <div className="mt-3 space-y-3">
              <div>
                <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                  <ShieldAlert className="size-3.5 text-amber-300" />
                  Risco observado
                </p>
                <p className="mt-1 text-xs leading-relaxed text-zinc-300">
                  {move.impact ||
                    move.explanation ||
                    "Sem risco relevante registrado para este lance."}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                  <Wrench className="size-3.5 text-rose-300" />
                  Solução sugerida
                </p>
                <p className="mt-1 text-xs leading-relaxed text-rose-200/90">
                  {move.recommendation || "Nenhuma ação necessária até aqui."}
                </p>
              </div>
              {move.ai_explanation && (
                <div>
                  <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                    <Bot className="size-3.5 text-sky-300" />
                    Comentário do treinador (IA)
                    {move.ai_review?.verdict === "approved" && (
                      <span className="rounded bg-emerald-400/10 px-1 text-[9px] text-emerald-300">
                        revisado pelo juiz
                      </span>
                    )}
                  </p>
                  <p className="mt-1 text-xs leading-relaxed text-zinc-300">
                    {move.ai_explanation}
                  </p>
                </div>
              )}
            </div>

            {move.reproduce.length > 0 && (
              <div className="mt-3">
                <div className="flex items-center justify-between">
                  <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                    <Terminal className="size-3.5 text-zinc-400" />
                    Como reproduzir
                  </p>
                  <Button
                    variant="ghost"
                    size="icon-xs"
                    aria-label="Copiar comandos de reprodução"
                    className="text-zinc-400 hover:bg-white/10 hover:text-white"
                    onClick={() => copyReproduce(move.reproduce.join("\n"))}
                  >
                    {copied ? (
                      <Check className="size-3.5" />
                    ) : (
                      <Copy className="size-3.5" />
                    )}
                  </Button>
                </div>
                <pre className="mt-1 overflow-x-auto rounded-lg border border-white/[0.07] bg-black/40 p-2.5 font-mono text-[11px] leading-relaxed text-zinc-300">
                  {move.reproduce.join("\n")}
                </pre>
              </div>
            )}

            {move.evidence.length > 0 && (
              <div className="mt-3">
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full border-white/10 bg-white/[0.03] text-zinc-200 hover:bg-white/10"
                  onClick={() => setShowEvidence((value) => !value)}
                >
                  <FileSearch />
                  {showEvidence ? "Ocultar evidência" : "Abrir evidência bruta"}
                </Button>
                {showEvidence && (
                  <ul className="mt-2 space-y-2">
                    {move.evidence.map((item) => (
                      <li
                        key={item.id}
                        className="rounded-lg border border-white/[0.07] bg-black/30 p-2.5 text-xs"
                      >
                        <p className="break-all font-mono text-zinc-300">
                          {item.request}
                        </p>
                        {item.response_status !== null && (
                          <span className="mt-1 inline-block rounded bg-white/[0.05] px-1.5 py-0.5 font-mono text-[10px] text-zinc-500">
                            HTTP {item.response_status}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="flex flex-1 flex-col items-center justify-center gap-2 text-center">
            <ScanSearch className="size-6 text-zinc-600" />
            <p className="text-sm text-zinc-400">
              Selecione um lance para ver o resultado.
            </p>
          </div>
        )}

        <div className="mt-4 space-y-2 border-t border-white/[0.07] pt-3">
          {downloadError && (
            <ApiErrorState compact message={downloadError} />
          )}
          {canOpenReport && (
            <Button
              onClick={onOpenReport}
              className="w-full bg-rose-600 text-white hover:bg-rose-500"
            >
              <FileText />
              Ver Game Review
            </Button>
          )}
          <Button
            variant="outline"
            disabled={isDownloadingReport}
            onClick={onDownloadReport}
            className="w-full border-white/10 bg-white/[0.03] text-zinc-100 hover:bg-white/10"
          >
            {isDownloadingReport ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <FileDown />
            )}
            Baixar relatório detalhado
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function playApprovalNotification() {
  if (typeof window.AudioContext === "undefined") return;

  const context = new window.AudioContext();
  const oscillator = context.createOscillator();
  const gain = context.createGain();
  const startAt = context.currentTime;

  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(880, startAt);
  oscillator.frequency.setValueAtTime(1175, startAt + 0.12);
  gain.gain.setValueAtTime(0.0001, startAt);
  gain.gain.exponentialRampToValueAtTime(0.12, startAt + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, startAt + 0.38);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.onended = () => void context.close();

  void context
    .resume()
    .then(() => {
      oscillator.start(context.currentTime);
      oscillator.stop(context.currentTime + 0.4);
    })
    .catch((error: unknown) => {
      console.warn("Não foi possível reproduzir o som de aprovação.", error);
      void context.close();
    });
}
