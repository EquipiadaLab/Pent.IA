import {
  Activity,
  ArrowRight,
  Check,
  CheckCheck,
  ChevronRight,
  Circle,
  FileSearch,
  Info,
  LoaderCircle,
  LockKeyhole,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Wrench,
  X,
  Zap,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "../ui/alert-dialog";
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
  statusTag,
} from "./helpers";
import type { Campaign, CampaignMove } from "./types";

import { Badge } from "../ui/badge";
import { Button } from "../ui/button";
import { Switch } from "../ui/switch";
import { ApiErrorState } from "./api-error-state";

interface CampaignBoardProps {
  campaign: Campaign;
  latestMove: CampaignMove | null;
  active: boolean;
  pendingAction: string;
  campaignError: string;
  actionError: string;
  onDecide: (moveNumber: number, decision: "approve" | "deny") => void;
}

export function CampaignBoard({
  campaign,
  latestMove,
  active,
  pendingAction,
  campaignError,
  actionError,
  onDecide,
}: CampaignBoardProps) {
  const pendingMove =
    campaign.moves.find((move) => move.approval === "pending") || null;

  const [selectedMove, setSelectedMove] = useState<number | null>(null);
  const activeMove =
    campaign.moves.find((move) => move.move === selectedMove) ?? latestMove;

  // Confirmação do usuário por lance. A automação fica sempre ativa enquanto a
  // API de confirmação não existe (ver onboarding abaixo).
  const autoConfirm = true;
  const [confirmedMoves, setConfirmedMoves] = useState<Set<number>>(new Set());
  const confirmMove = (moveNumber: number) =>
    setConfirmedMoves((prev) => {
      const next = new Set(prev);
      next.add(moveNumber);
      return next;
    });
  const isMoveConfirmed = (moveNumber: number) =>
    autoConfirm || confirmedMoves.has(moveNumber);

  return (
    <>
      <div className="mt-3 grid gap-3 xl:grid-cols-[1.25fr_0.9fr]">
        <Timeline
          campaign={campaign}
          active={active}
          error={campaignError}
          selectedMove={activeMove?.move ?? null}
          onSelectMove={setSelectedMove}
          isMoveConfirmed={isMoveConfirmed}
        />
        <AnalysisCard
          move={activeMove}
          autoConfirm={autoConfirm}
          confirmed={activeMove ? isMoveConfirmed(activeMove.move) : false}
          onConfirm={confirmMove}
        />
      </div>
      <HumanApprovalDialog
        move={pendingMove}
        pendingAction={pendingAction}
        actionError={actionError}
        onDecide={onDecide}
      />
    </>
  );
}

function Timeline({
  campaign,
  active,
  error,
  selectedMove,
  onSelectMove,
  isMoveConfirmed,
}: {
  campaign: Campaign;
  active: boolean;
  error: string;
  selectedMove: number | null;
  onSelectMove: (move: number) => void;
  isMoveConfirmed: (move: number) => boolean;
}) {
  return (
    <Card className="border-white/10 bg-zinc-950/75">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div className="flex items-center gap-2">
          <Activity className="size-4 text-rose-400" />
          <CardTitle className="text-xs uppercase tracking-[0.16em] text-zinc-300">
            Linha do tempo · ao vivo
          </CardTitle>
        </div>
        <span className="rounded-md border border-white/10 px-2 py-1 font-mono text-[10px] text-zinc-500">
          {String(campaign.moves.length).padStart(2, "0")} lances
        </span>
      </CardHeader>
      <CardContent className="timeline-scrollbar max-h-145 overflow-y-auto pt-2">
        {error && <ApiErrorState compact message={error} />}
        {campaign.moves.length ? (
          <ol className="divide-y divide-white/[0.06]">
            {[...campaign.moves]
              .sort((a, b) => b.move - a.move)
              .map((move) => {
                const tag = statusTag(move);
                const isSelected = move.move === selectedMove;
                const confirmed =
                  isMoveConfirmed(move.move) &&
                  move.approval !== "pending" &&
                  move.approval !== "denied";
                return (
                  <li key={move.move} className="py-1">
                    <button
                      type="button"
                      aria-pressed={isSelected}
                      onClick={() => onSelectMove(move.move)}
                      className={`w-full cursor-pointer rounded-xl border p-3 text-left transition-colors hover:border-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/40 ${moveTone(move)} ${isSelected
                        ? "ring-1 ring-rose-400/60 ring-offset-0"
                        : ""
                        }`}
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
                            {confirmed && (
                              <>
                                <span>·</span>
                                <span className="inline-flex items-center gap-1 text-emerald-400">
                                  <CheckCheck className="size-3" />
                                  Confirmado
                                </span>
                              </>
                            )}
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

function AnalysisCard({
  move,
  autoConfirm,
  confirmed,
  onConfirm,
}: {
  move: CampaignMove | null;
  autoConfirm: boolean;
  confirmed: boolean;
  onConfirm: (move: number) => void;
}) {
  const [showEvidence, setShowEvidence] = useState(false);

  useEffect(() => {
    setShowEvidence(false);
  }, [move?.move]);

  const comment =
    move?.ai_explanation ||
    move?.explanation ||
    (move?.approval === "pending"
      ? "Este lance aguarda aprovação antes de ser executado."
      : "O agente ainda está analisando este lance.");

  return (
    <Card className="border-rose-500/20 bg-gradient-to-b from-rose-950/15 to-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div className="flex items-center gap-2">
          <ScanSearch className="size-4 text-rose-400" />
          <CardTitle className="text-xs uppercase tracking-[0.16em] text-zinc-300">
            Pente-fino · leitura do lance
          </CardTitle>
        </div>
        <span className="font-mono text-[10px] text-zinc-500">
          {move ? `LANCE ${String(move.move).padStart(2, "0")}` : "AGUARDANDO"}
        </span>
      </CardHeader>
      <CardContent className="pt-4">
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
                {move.test_id} · análise verificável
              </span>
            </div>

            <h3 className="mt-3 text-lg font-semibold tracking-tight text-zinc-100">
              {move.title}
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-zinc-400">
              {comment}
            </p>

            <div className="mt-4 grid gap-4 border-t border-white/[0.07] pt-4 sm:grid-cols-2">
              <div>
                <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                  <ShieldAlert className="size-3.5 text-amber-300" />
                  Risco observado
                </p>
                <p className="mt-2 text-xs leading-relaxed text-zinc-300">
                  {move.impact ||
                    move.explanation ||
                    "Sem risco relevante registrado para este lance."}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
                  <Wrench className="size-3.5 text-rose-300" />
                  Correção acionável
                </p>
                <p className="mt-2 text-xs leading-relaxed text-rose-200/90">
                  {move.recommendation ||
                    "Nenhuma ação necessária até aqui."}
                </p>
              </div>
            </div>

            {move.evidence.length > 0 && (
              <div className="mt-4">
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full border-white/10 bg-white/[0.03] text-zinc-200 hover:bg-white/10"
                  onClick={() => setShowEvidence((value) => !value)}
                >
                  <FileSearch />
                  {showEvidence ? "Ocultar evidência bruta" : "Abrir evidência bruta"}
                  <ArrowRight
                    className={`transition-transform ${showEvidence ? "rotate-90" : ""}`}
                  />
                </Button>
                {showEvidence && (
                  <ul className="mt-3 space-y-2">
                    {move.evidence.map((item) => (
                      <li
                        key={item.id}
                        className="rounded-lg border border-white/[0.07] bg-black/30 p-3 text-xs"
                      >
                        <p className="break-all font-mono text-zinc-300">
                          {item.request}
                        </p>
                        <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-zinc-500">
                          {item.response_status !== null && (
                            <span className="rounded bg-white/[0.05] px-1.5 py-0.5 font-mono">
                              HTTP {item.response_status}
                            </span>
                          )}
                          {item.response_sha256 && (
                            <span className="font-mono">
                              sha256: {item.response_sha256.slice(0, 12)}…
                            </span>
                          )}
                        </div>
                        {item.note && (
                          <p className="mt-2 leading-relaxed text-zinc-500">
                            {item.note}
                          </p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {move.approval !== "denied" && move.status && (
              <div className="mt-4 flex items-center gap-2 rounded-lg border border-emerald-500/20 bg-emerald-500/[0.06] px-3 py-2.5 text-xs text-emerald-300">
                <ShieldCheck className="size-4 shrink-0" />
                Lance executado com escopo preservado.
              </div>
            )}

            <div className="mt-5 border-t border-white/[0.07] pt-4">
              <div className="flex items-center justify-between gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] px-3 py-2.5">
                <label
                  htmlFor="auto-confirm"
                  className="flex items-center gap-2.5"
                >
                  <Zap className="size-4 shrink-0 text-rose-400" />
                  <span>
                    <span className="block text-xs font-medium text-zinc-200">
                      Confirmar lances automaticamente
                    </span>
                    <span className="block text-[10px] text-zinc-500">
                      Dispensa a confirmação manual de cada lance.
                    </span>
                  </span>
                </label>
                <Switch
                  id="auto-confirm"
                  checked={autoConfirm}
                  disabled
                  aria-label="Confirmar lances automaticamente"
                />
              </div>
              <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-relaxed text-zinc-600">
                <Info className="mt-px size-3 shrink-0" />
                Sempre ativa por enquanto — a confirmação manual será liberada
                quando a API de confirmação existir.
              </p>

              <Button
                size="sm"
                disabled={autoConfirm || confirmed}
                onClick={() => onConfirm(move.move)}
                className={`mt-3 w-full ${confirmed
                  ? "border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/10"
                  : "bg-rose-600 text-white hover:bg-rose-500"
                  }`}
              >
                {confirmed ? (
                  <>
                    <CheckCheck />
                    {autoConfirm
                      ? "Confirmado automaticamente"
                      : "Lance confirmado"}
                  </>
                ) : (
                  <>
                    <Check />
                    Confirmar lance
                  </>
                )}
              </Button>
            </div>
          </>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center text-center">
            <ScanSearch className="size-6 text-zinc-600" />
            <p className="mt-3 text-sm text-zinc-400">
              Selecione um lance na linha do tempo.
            </p>
            <p className="mt-1 text-xs text-zinc-600">
              A leitura pente-fino do lance aparecerá aqui.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HumanApprovalDialog({
  move,
  pendingAction,
  actionError,
  onDecide,
}: {
  move: CampaignMove | null;
  pendingAction: string;
  actionError: string;
  onDecide: CampaignBoardProps["onDecide"];
}) {
  const notifiedMove = useRef<number | null>(null);

  useEffect(() => {
    if (!move || move.approval !== "pending") {
      notifiedMove.current = null;
      return;
    }

    if (notifiedMove.current === move.move) return;
    notifiedMove.current = move.move;
    playApprovalNotification();
  }, [move?.approval, move?.move]);

  const isPending = Boolean(move);

  return (
    <AlertDialog open={isPending}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <div className="mb-1 grid size-10 place-items-center rounded-xl border border-amber-400/25 bg-amber-400/10 text-amber-200">
            <LockKeyhole className="size-5" />
          </div>
          <AlertDialogTitle>Aprovação humana necessária</AlertDialogTitle>
          <AlertDialogDescription>
            {move?.plan?.hypothesis ||
              "O agente solicitou autorização para executar este teste."}
          </AlertDialogDescription>
        </AlertDialogHeader>

        {move && (
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm">
            <p className="font-medium text-zinc-100">
              Lance {move.move} · {move.test_id}
            </p>
            <p className="mt-1 text-zinc-400">{move.title}</p>
            {move.plan?.expected_result && (
              <p className="mt-3 text-xs leading-relaxed text-zinc-500">
                Resultado esperado: {move.plan.expected_result}
              </p>
            )}
          </div>
        )}

        {actionError && <ApiErrorState compact message={actionError} />}

        <AlertDialogFooter>
          {move && (
            <>
              <Button
                size="sm"
                disabled={Boolean(pendingAction)}
                onClick={() => onDecide(move.move, "deny")}
                variant="outline"
                className="border-white/10 bg-transparent text-zinc-300 hover:bg-white/5"
              >
                {pendingAction === `deny-${move.move}` ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <X />
                )}
                Negar
              </Button>
              <Button
                size="sm"
                disabled={Boolean(pendingAction)}
                onClick={() => onDecide(move.move, "approve")}
                className="bg-rose-600 text-white hover:bg-rose-500"
              >
                {pendingAction === `approve-${move.move}` ? (
                  <LoaderCircle className="animate-spin" />
                ) : (
                  <Check />
                )}
                Aprovar lance
              </Button>
            </>
          )}
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
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
