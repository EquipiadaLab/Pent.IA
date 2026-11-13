import { X } from "lucide-react";
import { Badge } from "../ui/badge";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import { formatTime } from "./helpers";
import type { ExecutiveSummary, GameReview } from "./types";

interface CampaignReportProps {
  report: GameReview;
  onClose: () => void;
}

const RISK_LABEL: Record<
  ExecutiveSummary["risk_level"],
  { label: string; className: string }
> = {
  critico: {
    label: "Risco crítico",
    className: "border-rose-500/40 bg-rose-500/15 text-rose-300",
  },
  alto: {
    label: "Risco alto",
    className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
  },
  medio: {
    label: "Risco médio",
    className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  },
  baixo: {
    label: "Risco baixo",
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
  },
};

export function CampaignReport({ report, onClose }: CampaignReportProps) {
  const summary = report.summary ?? null;
  const comparison = report.comparison ?? null;
  const risk = summary ? RISK_LABEL[summary.risk_level] : null;

  return (
    <Card className="mt-3 border-white/10 bg-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div>
          <CardTitle className="text-sm text-zinc-100">
            Game Review · relatório da campanha
          </CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            Resumo executivo, riscos e trilha de auditoria retornados pela API.
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
        {summary ? (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center gap-2">
              {risk && (
                <Badge
                  variant="outline"
                  className={`uppercase tracking-wider ${risk.className}`}
                >
                  {risk.label}
                </Badge>
              )}
              <span className="text-[10px] uppercase tracking-wider text-zinc-600">
                {summary.source === "ai" ? "Resumo por IA" : "Resumo por regras"}
              </span>
            </div>
            <p className="text-base font-semibold tracking-tight text-zinc-100">
              {summary.headline}
            </p>
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
              {summary.plain_language}
            </p>
            {summary.top_risks.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                  Principais riscos
                </p>
                <ul className="mt-2 space-y-2">
                  {summary.top_risks.map((item) => (
                    <li
                      key={`${item.move}-${item.title}`}
                      className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3 text-xs text-zinc-400"
                    >
                      <span className="mr-2 font-mono text-rose-300">
                        Lance {item.move}
                      </span>
                      <span className="text-zinc-200">{item.title}</span>
                      <p className="mt-1 leading-relaxed">{item.why}</p>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            {summary.next_steps.length > 0 && (
              <div>
                <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                  Próximos passos
                </p>
                <ul className="mt-2 list-inside list-disc space-y-1 text-xs text-zinc-300">
                  {summary.next_steps.map((step, index) => (
                    <li key={index}>{step}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-zinc-300">
            {report.executive_summary || "Resumo executivo indisponível."}
          </p>
        )}

        {comparison && (
          <div className="mt-5 rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
            <p className="text-[10px] uppercase tracking-wider text-zinc-500">
              Comparação com a partida anterior
              {comparison.accuracy_delta !== null && (
                <span
                  className={`ml-2 font-mono ${comparison.accuracy_delta >= 0 ? "text-emerald-300" : "text-rose-300"}`}
                >
                  {comparison.accuracy_delta >= 0 ? "+" : ""}
                  {comparison.accuracy_delta.toFixed(1)} acc
                </span>
              )}
            </p>
            <div className="mt-2 grid gap-2 sm:grid-cols-3 text-xs">
              <ComparisonCol
                label="Corrigidos"
                items={comparison.fixed}
                className="text-emerald-300"
              />
              <ComparisonCol
                label="Novos"
                items={comparison.new}
                className="text-rose-300"
              />
              <ComparisonCol
                label="Ainda falhando"
                items={comparison.still_failing}
                className="text-amber-200"
              />
            </div>
          </div>
        )}

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

function ComparisonCol({
  label,
  items,
  className,
}: {
  label: string;
  items: string[];
  className: string;
}) {
  return (
    <div className="rounded-md border border-white/[0.06] bg-black/30 p-2">
      <p className={`text-[10px] uppercase tracking-wider ${className}`}>
        {label} ({items.length})
      </p>
      {items.length > 0 ? (
        <ul className="mt-1 space-y-0.5 font-mono text-[11px] text-zinc-400">
          {items.map((item) => (
            <li key={item} className="truncate">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-1 text-[11px] text-zinc-600">—</p>
      )}
    </div>
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
