import { Activity, LoaderCircle, Shield } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import type { Campaign, Scope } from "./types";

interface CampaignInsightsProps {
  campaign: Campaign;
  scope: Scope | null;
  scopeLoading: boolean;
  scopeError: string;
  onRetryScope: () => void;
}

export function CampaignInsights({
  campaign,
  scope,
  scopeLoading,
  scopeError,
  onRetryScope,
}: CampaignInsightsProps) {
  return (
    <div className="mt-3 grid gap-3 lg:grid-cols-[1fr_1fr]">
      <Card className="border-white/10 bg-zinc-950/75">
        <CardHeader className="flex grid-cols-[1fr_auto] items-center pb-2">
          <div className="flex items-center gap-2">
            <Activity className="size-4 text-emerald-400" />
            <CardTitle className="text-xs uppercase tracking-[0.16em] text-zinc-400">
              Avaliação da partida
            </CardTitle>
          </div>
          <span className="font-mono text-[10px] text-zinc-600">
            {campaign.score ? "ATUALIZADO" : "SEM RESULTADOS"}
          </span>
        </CardHeader>
        <CardContent className="pt-2">
          <div className="flex items-end justify-between">
            <div>
              <p className="text-3xl font-semibold tabular-nums text-zinc-100">
                {campaign.score ? campaign.score.accuracy.toFixed(1) : "—"}
              </p>
              <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                Accuracy
              </p>
            </div>
            <div className="text-right text-xs text-zinc-500">
              Avaliação do site
              <span className="ml-2 font-mono text-zinc-300">
                {campaign.score
                  ? `${campaign.score.eval_bar > 0 ? "+" : ""}${campaign.score.eval_bar.toFixed(0)}`
                  : "—"}
              </span>
            </div>
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-zinc-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-300 to-emerald-400 transition-all"
              style={{
                width: `${Math.min(
                  100,
                  Math.max(0, ((campaign.score?.eval_bar ?? -100) + 100) / 2),
                )}%`,
              }}
            />
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            {(["blunder", "mistake", "inaccuracy", "inconclusive"] as const).map(
              (grade) => (
                <span
                  key={grade}
                  className="rounded-md border border-white/[0.08] bg-white/[0.02] px-2 py-1 text-[10px] text-zinc-500"
                >
                  {campaign.score?.counts[grade] || 0}{" "}
                  {grade === "blunder"
                    ? "erros graves"
                    : grade === "mistake"
                      ? "erros"
                      : grade === "inaccuracy"
                        ? "imprecisões"
                        : "inconclusivos"}
                </span>
              ),
            )}
          </div>
        </CardContent>
      </Card>

      <Card className="border-white/10 bg-zinc-950/75">
        <CardHeader className="flex grid-cols-[1fr_auto] items-center pb-2">
          <div className="flex items-center gap-2">
            <Shield className="size-4 text-sky-300" />
            <CardTitle className="text-xs uppercase tracking-[0.16em] text-zinc-400">
              Regras de engajamento
            </CardTitle>
          </div>
          <span className="rounded-full border border-emerald-500/20 bg-emerald-500/[0.07] px-2 py-1 text-[9px] uppercase tracking-wider text-emerald-300">
            Escopo local
          </span>
        </CardHeader>
        <CardContent className="space-y-3 pt-2">
          <PolicyRow label="Alvo autorizado" value={campaign.config.origin} />
          <PolicyRow
            label="Autorizado por"
            value={campaign.config.authorized_by || "—"}
          />
          {scopeError ? (
            <ApiErrorState
              compact
              message={scopeError}
              onRetry={onRetryScope}
            />
          ) : scopeLoading && !scope ? (
            <p className="flex items-center gap-2 text-xs text-zinc-500">
              <LoaderCircle className="size-3.5 animate-spin" />
              Carregando regras do servidor...
            </p>
          ) : scope ? (
            <>
              <PolicyRow
                label="Métodos permitidos"
                value={scope.allowed_methods.join(" / ")}
              />
              <PolicyRow
                label="Limites"
                value={`Até ${scope.limits.max_requests_per_second} req/s · ${scope.limits.max_total_requests} por campanha`}
              />
            </>
          ) : (
            <p className="text-xs text-zinc-500">
              Regras de escopo indisponíveis.
            </p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function PolicyRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-white/[0.05] pb-2 last:border-b-0 last:pb-0">
      <span className="text-xs text-zinc-500">{label}</span>
      <span className="max-w-[65%] break-all text-right text-xs text-zinc-300">
        {value}
      </span>
    </div>
  );
}
