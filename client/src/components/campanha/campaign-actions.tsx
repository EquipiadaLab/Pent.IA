import { Clock3, FileText, LoaderCircle, Square } from "lucide-react";
import { Button } from "../ui/button";
import { ApiErrorState } from "./api-error-state";
import { durationLabel, formatTime, stateLabel } from "./helpers";
import type { Campaign, CampaignStatus } from "./types";

interface CampaignActionsProps {
  campaign: Campaign;
  status: CampaignStatus | null;
  active: boolean;
  pendingCount: number;
  isLocal: boolean;
  isStopping: boolean;
  stopError: string;
  exportError: string;
  isLoadingReport: boolean;
  onStop: () => void;
  onViewReport: () => void;
  onDownloadReport: () => void;
}

export function CampaignActions({
  campaign,
  status,
  active,
  pendingCount,
  isLocal,
  isStopping,
  stopError,
  exportError,
  isLoadingReport,
  onStop,
  onViewReport,
  onDownloadReport,
}: CampaignActionsProps) {
  return (
    <div className="mt-3 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-white/10 bg-zinc-950/80 px-4 py-3">
      {active && stopError && (
        <div className="w-full">
          <ApiErrorState compact message={stopError} />
        </div>
      )}
      {!active && exportError && (
        <div className="w-full">
          <ApiErrorState compact message={exportError} />
        </div>
      )}
      <div className="flex items-center gap-3">
        <div className="grid size-8 place-items-center rounded-lg bg-amber-500/10 text-amber-300">
          {active ? <Clock3 className="size-4" /> : <FileText className="size-4" />}
        </div>
        <div>
          <p className="text-xs font-medium text-zinc-200">
            {active
              ? pendingCount
                ? "Aprovação humana pendente"
                : "Agente conectado · campanha em andamento"
              : "Revisão da campanha"}
          </p>
          <p className="mt-0.5 text-[10px] text-zinc-500">
            {active
              ? `${status?.progress.played || 0} de ${status?.progress.total || 0} lances · ${durationLabel(status?.elapsed_s || 0)} decorridos`
              : campaign.finished_at
                ? `Finalizada às ${formatTime(campaign.finished_at)}`
                : stateLabel(campaign.state)}
          </p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        {active ? (
          <Button
            variant="destructive"
            size="sm"
            disabled={isStopping || !isLocal}
            onClick={onStop}
          >
            {isStopping ? (
              <LoaderCircle className="animate-spin" />
            ) : (
              <Square />
            )}
            Parar campanha
          </Button>
        ) : (
          <>
            <Button
              variant="outline"
              size="sm"
              disabled={isLoadingReport}
              onClick={onViewReport}
              className="border-white/10 bg-transparent text-zinc-300 hover:bg-white/5"
            >
              {isLoadingReport ? (
                <LoaderCircle className="animate-spin" />
              ) : (
                <FileText />
              )}
              {isLoadingReport ? "Analisando..." : "Ver relatório"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={onDownloadReport}
              className="border-white/10 bg-transparent text-zinc-300 hover:bg-white/5"
            >
              <FileText />
              Baixar .md
            </Button>
          </>
        )}
      </div>
    </div>
  );
}
