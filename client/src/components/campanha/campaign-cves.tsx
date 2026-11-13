import { AlertTriangle, ExternalLink, ShieldCheck, X } from "lucide-react";
import { Badge } from "../ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "../ui/card";
import { ApiErrorState } from "./api-error-state";
import { safeHttpUrl } from "./helpers";
import type { CveItem, CvesResponse } from "./types";

interface CampaignCvesProps {
  data: CvesResponse;
  onClose: () => void;
}

function severityTone(severity: string | null): string {
  switch ((severity ?? "").toUpperCase()) {
    case "CRITICAL":
      return "border-rose-500/40 bg-rose-500/15 text-rose-300";
    case "HIGH":
      return "border-rose-400/30 bg-rose-400/10 text-rose-300";
    case "MEDIUM":
      return "border-amber-400/30 bg-amber-400/10 text-amber-200";
    case "LOW":
      return "border-border/60 bg-muted/30 text-muted-foreground";
    default:
      return "border-border/60 bg-muted/30 text-muted-foreground";
  }
}

export function CampaignCves({ data, onClose }: CampaignCvesProps) {
  const matches = data.matches ?? [];
  const totalCves = matches.reduce((sum, m) => sum + (m.cves?.length ?? 0), 0);

  return (
    <Card className="mt-3 border-white/10 bg-zinc-950/80">
      <CardHeader className="flex grid-cols-[1fr_auto] items-center border-b border-white/[0.07] pb-4">
        <div>
          <CardTitle className="text-sm text-zinc-100">
            CVEs e exploits conhecidos (NVD)
          </CardTitle>
          <p className="mt-1 text-xs text-zinc-500">
            Correlação entre a tecnologia observada na campanha e a base pública
            do NIST.
          </p>
        </div>
        <button
          type="button"
          aria-label="Fechar CVEs"
          className="text-zinc-500 hover:text-zinc-200"
          onClick={onClose}
        >
          <X className="size-4" />
        </button>
      </CardHeader>
      <CardContent className="pt-4">
        {totalCves === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-8 text-center">
            <ShieldCheck className="size-7 text-emerald-300/80" />
            <p className="max-w-md text-sm text-zinc-400">
              Nenhum CVE conhecido para as tecnologias observadas nesta campanha.
              Isso não garante ausência de falhas — apenas que a NVD não retornou
              registros para os termos identificados.
            </p>
          </div>
        ) : (
          <div className="space-y-5">
            {matches.map((match) => (
              <section key={`${match.search_term}-${match.move}`}>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-sm font-semibold text-zinc-100">
                    {match.search_term}
                  </h3>
                  {match.move !== null && (
                    <span className="font-mono text-[10px] text-zinc-500">
                      Lance {match.move}
                    </span>
                  )}
                  <span className="text-[10px] text-zinc-600">
                    {match.cves.length}{" "}
                    {match.cves.length === 1 ? "CVE" : "CVEs"}
                  </span>
                </div>

                {match.error ? (
                  <p className="mt-2 text-xs text-amber-200">
                    Não foi possível consultar a NVD agora.
                  </p>
                ) : match.cves.length === 0 ? (
                  <p className="mt-2 text-xs text-zinc-600">
                    Sem CVE conhecido para este termo.
                  </p>
                ) : (
                  <ul className="mt-2 space-y-2">
                    {match.cves.map((cve) => (
                      <CveRow key={cve.cve_id} cve={cve} />
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function CveRow({ cve }: { cve: CveItem }) {
  const nvdHref = safeHttpUrl(cve.nvd_url);
  const hasExploit = cve.exploits.length > 0;

  return (
    <li className="rounded-lg border border-white/[0.07] bg-white/[0.02] p-3">
      <div className="flex flex-wrap items-center gap-2">
        {nvdHref ? (
          <a
            href={nvdHref}
            target="_blank"
            rel="noreferrer noopener"
            className="inline-flex items-center gap-1 font-mono text-xs text-sky-300 hover:underline"
          >
            {cve.cve_id}
            <ExternalLink className="size-3" />
          </a>
        ) : (
          <span className="font-mono text-xs text-zinc-200">{cve.cve_id}</span>
        )}
        {cve.cvss_score !== null && (
          <Badge
            variant="outline"
            className={`uppercase tracking-wider ${severityTone(cve.cvss_severity)}`}
          >
            {cve.cvss_severity ?? "—"} · {cve.cvss_score.toFixed(1)}
          </Badge>
        )}
        {cve.cwe_ids.map((cwe) => (
          <span
            key={cwe}
            className="rounded border border-white/[0.08] bg-black/30 px-1.5 py-0.5 font-mono text-[10px] text-zinc-400"
          >
            {cwe}
          </span>
        ))}
      </div>

      {cve.description && (
        <p className="mt-2 line-clamp-3 text-xs leading-relaxed text-zinc-400">
          {cve.description}
        </p>
      )}

      {hasExploit && (
        <div className="mt-2 flex flex-col gap-1 rounded-md border border-rose-400/20 bg-rose-400/[0.06] p-2">
          <p className="flex items-center gap-1.5 text-[11px] font-medium text-rose-300">
            <AlertTriangle className="size-3.5" />
            Exploit público conhecido
          </p>
          {cve.exploits.map((exploit, index) => {
            const href = safeHttpUrl(exploit.url);
            if (!href) return null;
            return (
              <a
                key={`${exploit.url}-${index}`}
                href={href}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 truncate text-[11px] text-rose-200/90 hover:underline"
              >
                <ExternalLink className="size-3 shrink-0" />
                <span className="truncate">{exploit.source || exploit.url}</span>
              </a>
            );
          })}
        </div>
      )}
    </li>
  );
}

interface CampaignCvesErrorProps {
  message: string;
  onRetry: () => void;
}

export function CampaignCvesError({ message, onRetry }: CampaignCvesErrorProps) {
  return (
    <Card className="mt-3 border-rose-500/25 bg-zinc-950/80">
      <CardHeader>
        <CardTitle className="text-sm text-zinc-100">
          Não foi possível consultar a NVD
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ApiErrorState message={message} onRetry={onRetry} />
      </CardContent>
    </Card>
  );
}
