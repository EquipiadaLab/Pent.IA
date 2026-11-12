import { Globe2, LoaderCircle } from "lucide-react";
import { Card, CardContent } from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import { formatTime, stateLabel } from "./helpers";
import type { Campaign, CampaignStatus } from "./types";

interface CampaignOverviewProps {
  campaign: Campaign;
  status: CampaignStatus | null;
  statusLoading: boolean;
  statusError: string;
  pendingCount: number;
  active: boolean;
  onRetryStatus: () => void;
}

export function CampaignOverview({
  campaign,
  status,
  statusLoading,
  statusError,
  pendingCount,
  active,
  onRetryStatus,
}: CampaignOverviewProps) {
  const progress = status?.progress;
  const evidenceCount = campaign.moves.reduce(
    (total, move) => total + move.evidence.length,
    0,
  );

  return (
    <Card className="relative mt-5 border-rose-500/25 bg-gradient-to-br from-rose-950/30 via-zinc-950 to-zinc-950">
      <CardContent className="grid gap-6 p-5 md:grid-cols-[minmax(0,1fr)_auto] md:items-center md:p-6">
        <div className="min-w-0">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-rose-400">
              {campaign.id.slice(0, 8)} / live board
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/5 px-2 py-1 text-[10px] uppercase tracking-wider text-zinc-300">
              {active && (
                <span className="size-1.5 animate-pulse rounded-full bg-emerald-400" />
              )}
              {stateLabel(campaign.state)}
            </span>
            {campaign.config.unattended && (
              <span className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2 py-1 text-[10px] text-sky-300">
                Execução automática
              </span>
            )}
          </div>
          <h2 className="truncate text-xl font-semibold text-zinc-100 sm:text-2xl">
            {campaign.config.origin}
          </h2>
          <p className="mt-1 flex items-center gap-1.5 text-xs text-zinc-500">
            <Globe2 className="size-3.5" />
            Autorizado por {campaign.config.authorized_by || "—"} · iniciado{" "}
            {formatTime(campaign.created_at)}
          </p>
          <div className="mt-6">
            {statusError ? (
              <ApiErrorState
                compact
                message={statusError}
                onRetry={onRetryStatus}
              />
            ) : statusLoading && !status ? (
              <p className="flex items-center gap-2 text-xs text-zinc-500">
                <LoaderCircle className="size-3.5 animate-spin" />
                Sincronizando progresso...
              </p>
            ) : (
              <>
                <div className="mb-2 flex items-center justify-between gap-3 text-[10px] uppercase tracking-wider text-zinc-500">
                  <span>Progresso da campanha</span>
                  <span className="font-mono text-zinc-300">
                    {progress?.percent ?? 0}% · {progress?.played ?? campaign.moves.length}/
                    {progress?.total ?? "—"} lances
                  </span>
                </div>
                <div
                  className="h-1.5 overflow-hidden rounded-full bg-white/10"
                  role="progressbar"
                  aria-valuenow={progress?.percent ?? 0}
                  aria-valuemin={0}
                  aria-valuemax={100}
                >
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-rose-600 to-fuchsia-400 transition-all duration-500"
                    style={{
                      width: `${Math.min(100, Math.max(0, progress?.percent ?? 0))}%`,
                    }}
                  />
                </div>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center justify-between gap-4 border-t border-white/[0.08] pt-4 md:min-w-64 md:justify-end md:border-t-0 md:pt-0">
          <Metric
            value={
              statusError
                ? "—"
                : String(progress?.total ?? campaign.moves.length).padStart(2, "0")
            }
            label="Lances"
          />
          <Metric value={String(pendingCount).padStart(2, "0")} label="Aprovações" />
          <Metric value={String(evidenceCount).padStart(2, "0")} label="Evidências" />
        </div>
      </CardContent>
    </Card>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return (
    <div className="min-w-14 text-center">
      <p className="text-xl font-semibold tabular-nums text-zinc-100">{value}</p>
      <p className="mt-1 text-[9px] uppercase tracking-wider text-zinc-500">
        {label}
      </p>
    </div>
  );
}
