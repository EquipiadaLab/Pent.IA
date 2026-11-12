import { X } from "lucide-react";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import { formatTime } from "./helpers";
import type { GameReview } from "./types";

interface CampaignReportProps {
  report: GameReview;
  onClose: () => void;
}

export function CampaignReport({ report, onClose }: CampaignReportProps) {
  return (
    <Card className="mt-3 border-white/10 bg-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div>
          <CardTitle className="text-sm text-zinc-100">
            Relatório da campanha
          </CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            Resumo e trilha de auditoria retornados pela API.
          </p>
        </div>
        <button
          type="button"
          aria-label="Fechar relatório"
          className="text-zinc-500 hover:text-zinc-200"
          onClick={onClose}
        >
          <X className="size-4" />
        </button>
      </CardHeader>
      <CardContent className="pt-4">
        <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
          {report.executive_summary || "Resumo executivo indisponível."}
        </p>

        {report.key_moments.length > 0 && (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            {report.key_moments.map((moment) => (
              <div
                key={`${moment.move}-${moment.summary}`}
                className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3 text-xs text-zinc-400"
              >
                <span className="mr-2 font-mono text-rose-300">
                  Lance {moment.move}
                </span>
                {moment.summary}
              </div>
            ))}
          </div>
        )}

        {report.audit.length > 0 && (
          <div className="mt-5 overflow-x-auto">
            <table className="w-full min-w-[560px] text-left text-xs">
              <thead className="text-[10px] uppercase tracking-wider text-zinc-600">
                <tr>
                  <th className="pb-2 font-medium">Horário</th>
                  <th className="pb-2 font-medium">Método / URL</th>
                  <th className="pb-2 font-medium">Resultado</th>
                  <th className="pb-2 font-medium">Ator</th>
                </tr>
              </thead>
              <tbody>
                {report.audit.map((entry, index) => (
                  <tr
                    key={`${entry.at}-${entry.method}-${index}`}
                    className={
                      entry.allowed
                        ? "border-t border-white/[0.06] text-zinc-400"
                        : "border-t border-white/[0.06] text-rose-300"
                    }
                  >
                    <td className="py-2 pr-3 font-mono">
                      {formatTime(entry.at)}
                    </td>
                    <td className="max-w-md truncate py-2 pr-3">
                      {entry.method} {entry.url}
                    </td>
                    <td className="py-2 pr-3">
                      {entry.allowed
                        ? (entry.status_code ?? "Permitido")
                        : entry.reason || "Bloqueado"}
                    </td>
                    <td className="py-2">{entry.actor}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

interface CampaignReportErrorProps {
  message: string;
  onRetry: () => void;
}

export function CampaignReportError({
  message,
  onRetry,
}: CampaignReportErrorProps) {
  return (
    <Card className="mt-3 border-rose-500/25 bg-zinc-950/80">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-100">
          Não foi possível carregar o relatório
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ApiErrorState message={message} onRetry={onRetry} />
      </CardContent>
    </Card>
  );
}
