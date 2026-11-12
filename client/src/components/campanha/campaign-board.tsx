import {
  Activity,
  Check,
  ChevronRight,
  Circle,
  LoaderCircle,
  LockKeyhole,
  Sparkles,
  X,
} from "lucide-react";
import { Button } from "../ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import { formatTime, gradeLabel, moveTone, phaseLabel, MoveIcon } from "./helpers";
import type { Campaign, CampaignMove } from "./types";

interface CampaignBoardProps {
  campaign: Campaign;
  latestMove: CampaignMove | null;
  active: boolean;
  isLocal: boolean;
  pendingAction: string;
  campaignError: string;
  actionError: string;
  onDecide: (moveNumber: number, decision: "approve" | "deny") => void;
}

export function CampaignBoard({
  campaign,
  latestMove,
  active,
  isLocal,
  pendingAction,
  campaignError,
  actionError,
  onDecide,
}: CampaignBoardProps) {
  return (
    <div className="mt-3 grid gap-3 xl:grid-cols-[1.25fr_0.9fr]">
      <Timeline
        campaign={campaign}
        active={active}
        error={campaignError}
      />
      <CoachCard
        move={latestMove}
        isLocal={isLocal}
        pendingAction={pendingAction}
        actionError={actionError}
        onDecide={onDecide}
      />
    </div>
  );
}

function Timeline({
  campaign,
  active,
  error,
}: {
  campaign: Campaign;
  active: boolean;
  error: string;
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
      <CardContent className="max-h-[480px] overflow-y-auto pt-2">
        {error && <ApiErrorState compact message={error} />}
        {campaign.moves.length ? (
          <ol className="divide-y divide-white/[0.06]">
            {[...campaign.moves]
              .sort((a, b) => b.move - a.move)
              .map((move) => (
                <li
                  key={move.move}
                  className={`my-2 rounded-xl border p-3 transition-colors ${moveTone(move)}`}
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
                        {move.approval === "pending" && (
                          <span className="text-[9px] uppercase tracking-wider text-amber-300">
                            Aguardando aprovação
                          </span>
                        )}
                      </div>
                      <h3 className="mt-1 text-sm font-medium text-zinc-200">
                        {move.title}
                      </h3>
                      <div className="mt-1.5 flex flex-wrap items-center gap-2 text-[10px] text-zinc-500">
                        <span>{phaseLabel(move.phase)}</span>
                        <span>·</span>
                        <span>{gradeLabel(move.grade)}</span>
                        <span>·</span>
                        <span
                          className={
                            move.severity === "high"
                              ? "text-rose-300"
                              : move.severity === "medium"
                                ? "text-amber-200"
                                : "text-zinc-400"
                          }
                        >
                          Severidade {move.severity}
                        </span>
                      </div>
                      {move.plan && (
                        <div className="mt-3 grid gap-1.5 border-l border-rose-500/30 pl-3 text-xs">
                          <p className="text-zinc-300">
                            <span className="text-rose-300">Hipótese:</span>{" "}
                            {move.plan.hypothesis}
                          </p>
                          <p className="text-zinc-500">
                            <span className="text-zinc-400">Esperado:</span>{" "}
                            {move.plan.expected_result}
                          </p>
                          <p className="text-zinc-600">
                            Planejado por{" "}
                            {move.plan.source === "ai" ? "IA" : "regras"}
                          </p>
                        </div>
                      )}
                      {move.explanation && (
                        <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-zinc-400">
                          {move.explanation}
                        </p>
                      )}
                      {move.verdict && (
                        <span className="mt-2 inline-flex rounded-full border border-white/10 px-2 py-1 text-[10px] text-zinc-400">
                          {move.verdict === "confirmed"
                            ? "Confirmado (2 observações)"
                            : move.verdict === "discarded"
                              ? "Descartado: não se reproduziu"
                              : "Não reconfirmado"}
                        </span>
                      )}
                    </div>
                    <ChevronRight className="mt-1 size-4 shrink-0 text-zinc-700" />
                  </div>
                </li>
              ))}
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

function CoachCard({
  move,
  isLocal,
  pendingAction,
  actionError,
  onDecide,
}: {
  move: CampaignMove | null;
  isLocal: boolean;
  pendingAction: string;
  actionError: string;
  onDecide: CampaignBoardProps["onDecide"];
}) {
  return (
    <Card className="border-rose-500/20 bg-gradient-to-b from-rose-950/15 to-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div className="flex items-center gap-2">
          <Sparkles className="size-4 text-rose-400" />
          <CardTitle className="text-xs uppercase tracking-[0.16em] text-zinc-400">
            Feedback do treinador
          </CardTitle>
        </div>
        <span className="font-mono text-[10px] text-zinc-500">
          {move ? `LANCE ${move.move}` : "AGUARDANDO"}
        </span>
      </CardHeader>
      <CardContent className="pt-4">
        {actionError && (
          <div className="mb-3">
            <ApiErrorState compact message={actionError} />
          </div>
        )}
        {move ? (
          <>
            <div className="flex items-center gap-3">
              <div className="grid size-9 place-items-center rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-300">
                <MoveIcon move={move} />
              </div>
              <div>
                <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                  {gradeLabel(move.grade)}
                </p>
                <p className="text-sm font-medium text-zinc-200">
                  {move.test_id} · {move.title}
                </p>
              </div>
            </div>

            {move.plan && (
              <div className="mt-4 rounded-xl border border-white/[0.07] bg-black/20 p-3">
                <p className="text-[10px] uppercase tracking-wider text-rose-300">
                  Plano do agente · {move.plan.source === "ai" ? "IA" : "Regras"}
                </p>
                <p className="mt-2 text-xs leading-relaxed text-zinc-300">
                  <strong className="font-medium text-zinc-100">Hipótese:</strong>{" "}
                  {move.plan.hypothesis}
                </p>
                <p className="mt-2 text-xs leading-relaxed text-zinc-500">
                  <strong className="font-medium text-zinc-400">Esperado:</strong>{" "}
                  {move.plan.expected_result}
                </p>
                {move.plan.rationale && (
                  <p className="mt-2 text-xs leading-relaxed text-zinc-600">
                    Por quê: {move.plan.rationale}
                  </p>
                )}
              </div>
            )}

            <div className="mt-4 border-t border-white/[0.07] pt-3">
              <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                {move.ai_explanation
                  ? "Comentário do treinador"
                  : "Resultado observado"}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-300">
                {move.ai_explanation ||
                  move.explanation ||
                  (move.approval === "pending"
                    ? "Este teste aguarda sua aprovação antes de ser executado."
                    : "O agente ainda está analisando este lance.")}
              </p>
              {move.impact && (
                <p className="mt-3 text-xs leading-relaxed text-zinc-500">
                  Impacto: {move.impact}
                </p>
              )}
            </div>

            {move.approval === "pending" && (
              <div className="mt-4 rounded-xl border border-amber-400/25 bg-amber-400/[0.06] p-3">
                <div className="flex items-center gap-2 text-xs font-medium text-amber-200">
                  <LockKeyhole className="size-3.5" />
                  Aprovação humana necessária
                </div>
                <p className="mt-2 text-xs leading-relaxed text-zinc-400">
                  {move.plan?.hypothesis ||
                    "O agente solicitou autorização para executar este teste."}
                </p>
                {isLocal ? (
                  <div className="mt-3 flex gap-2">
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
                  </div>
                ) : (
                  <p className="mt-3 text-xs text-amber-200/80">
                    Decisão desabilitada para alvos não locais.
                  </p>
                )}
              </div>
            )}
          </>
        ) : (
          <div className="flex min-h-52 flex-col items-center justify-center text-center">
            <Sparkles className="size-6 text-zinc-600" />
            <p className="mt-3 text-sm text-zinc-400">
              O próximo lance está aguardando análise.
            </p>
            <p className="mt-1 text-xs text-zinc-600">
              Hipótese e resultado aparecerão aqui.
            </p>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
