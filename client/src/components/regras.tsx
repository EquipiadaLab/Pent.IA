import { useQuery } from "@tanstack/react-query";
import {
    ClipboardCheck,
    LoaderCircle,
    Lock,
    Radar,
    ShieldCheck,
    Timer,
    TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import type { Scope } from "./campanha/types";
import {
    Accordion,
    AccordionContent,
    AccordionItem,
    AccordionTrigger,
} from "./ui/accordion";
import { Badge } from "./ui/badge";
import { Separator } from "./ui/separator";

interface RuleDetail {
    label: string;
    value: string;
}

interface Rule {
    id: string;
    title: string;
    icon: React.ReactNode;
    description: string;
    badge: { label: string; className: string };
    details: RuleDetail[];
}

const ENFORCED_BADGE =
    "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";

function buildRules(scope: Scope | null): Rule[] {
    const rps = scope?.limits.max_requests_per_second ?? 2;
    const total = scope?.limits.max_total_requests ?? 200;
    const timeout = scope?.limits.request_timeout_s;
    const methods = scope?.allowed_methods ?? ["GET", "OPTIONS"];
    const blocked = scope?.blocked_profiles ?? ["intrusive"];
    const lockedTarget = scope?.locked_target ?? null;
    const blocksPrivate = scope?.blocks_private_targets ?? true;
    const preapproval = scope?.preapproval;

    return [
        {
            id: "SAFE-001",
            title: "Métodos seguros",
            icon: <Lock className="size-4" />,
            description:
                "O executor só pode emitir GET e OPTIONS. Qualquer método mutável é interrompido antes de tocar a rede.",
            badge: { label: "Enforced", className: ENFORCED_BADGE },
            details: [
                { label: "Métodos permitidos", value: methods.join(" · ") },
                { label: "Perfis bloqueados", value: blocked.join(" · ") || "—" },
            ],
        },
        {
            id: "SCOPE-001",
            title: "Fronteira de escopo",
            icon: <Radar className="size-4" />,
            description:
                "O alvo é travado no servidor: toda requisição é comparada com o alvo autorizado, nunca apenas com a intenção do prompt.",
            badge: lockedTarget
                ? {
                      label: "Alvo travado",
                      className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
                  }
                : {
                      label: "Allowlist do servidor",
                      className: ENFORCED_BADGE,
                  },
            details: [
                {
                    label: "Alvo",
                    value: lockedTarget ?? "definido pela allowlist do servidor",
                },
                {
                    label: "Redes privadas",
                    value: blocksPrivate
                        ? "bloqueadas (anti-SSRF)"
                        : "permitidas",
                },
            ],
        },
        {
            id: "RATE-002",
            title: "Ritmo controlado",
            icon: <Timer className="size-4" />,
            description:
                "Cada origem recebe no máximo algumas requisições por segundo para reduzir o impacto no ambiente autorizado.",
            badge: {
                label: `${rps} req/s`,
                className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
            },
            details: [
                { label: "Máx. por segundo", value: `${rps} req/s` },
                { label: "Máx. por campanha", value: `${total} requisições` },
                ...(timeout
                    ? [{ label: "Timeout", value: `${timeout}s por requisição` }]
                    : []),
            ],
        },
        {
            id: "HITL-001",
            title: "Aprovação humana",
            icon: <ClipboardCheck className="size-4" />,
            description:
                "Ações sensíveis ficam em fila com contexto e evidência até que uma pessoa aprove ou rejeite.",
            badge: preapproval?.active.length
                ? {
                      label: `${preapproval.active.length} pré-aprovados`,
                      className: ENFORCED_BADGE,
                  }
                : {
                      label: "Em fila",
                      className: "border-white/15 bg-white/[0.04] text-zinc-300",
                  },
            details: [
                {
                    label: "Pré-aprovações ativas",
                    value: preapproval?.active.length
                        ? preapproval.active.join(" · ")
                        : "nenhuma",
                },
                {
                    label: "Aprovado por",
                    value: preapproval?.approved_by || "—",
                },
            ],
        },
    ];
}

function useClock() {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const timer = window.setInterval(() => setNow(new Date()), 1000);
        return () => window.clearInterval(timer);
    }, []);
    return now;
}

export default function Regras() {
    const scopeQuery = useQuery({
        queryKey: ["scope"],
        queryFn: async () => (await api.get<Scope>("/scope")).data,
    });

    const scope = scopeQuery.data ?? null;
    const rules = useMemo(() => buildRules(scope), [scope]);
    const now = useClock();

    const dateLabel = now
        .toLocaleDateString("pt-BR", {
            weekday: "short",
            day: "2-digit",
            month: "short",
            year: "numeric",
        })
        .toUpperCase();
    const timeLabel = now.toLocaleTimeString("pt-BR", { hour12: false });

    return (
        <main className="mx-auto w-full max-w-[1500px] pb-12">
            <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
                <div>
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-rose-500">
                        <span className="h-px w-6 bg-rose-500" />
                        Motor de políticas
                    </p>
                    <h1 className="mt-2 text-4xl font-semibold tracking-tight">
                        Regras predefinidas
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Determinismo no executor. Explicação no agente. Segurança
                        por construção.
                    </p>
                </div>
                <div className="text-right font-mono text-[11px] leading-relaxed text-zinc-500">
                    <p>{dateLabel}</p>
                    <p className="tabular-nums text-zinc-400">{timeLabel} BRT</p>
                </div>
            </header>

            <div className="mt-6 flex flex-wrap items-center gap-2">
                <Badge
                    variant="outline"
                    className="border-white/10 bg-white/[0.03] uppercase tracking-wider text-zinc-400"
                >
                    {rules.length} regras ativas
                </Badge>
                <Badge
                    variant="outline"
                    className={`uppercase tracking-wider ${ENFORCED_BADGE}`}
                >
                    Impostas pelo servidor
                </Badge>
            </div>

            {scopeQuery.isError && (
                <div className="mt-4 flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-200">
                    <TriangleAlert className="size-4 shrink-0" />
                    <span className="flex-1">
                        {getApiErrorMessage(scopeQuery.error)}
                    </span>
                    <button
                        className="text-rose-200/80 underline-offset-2 hover:underline"
                        onClick={() => void scopeQuery.refetch()}
                    >
                        Tentar de novo
                    </button>
                </div>
            )}

            {scopeQuery.isPending ? (
                <div className="mt-4 flex min-h-56 items-center justify-center rounded-2xl border border-white/10 bg-zinc-950/70 text-zinc-500">
                    <LoaderCircle className="size-5 animate-spin" />
                </div>
            ) : (
                <Accordion
                    multiple
                    defaultValue={["SAFE-001"]}
                    className="mt-4 border-white/10 bg-zinc-950/70"
                >
                    {rules.map((rule) => (
                        <AccordionItem
                            key={rule.id}
                            value={rule.id}
                            className="border-white/[0.07] data-open:bg-white/[0.02]"
                        >
                            <AccordionTrigger className="items-center px-5 py-4 hover:no-underline">
                                <span className="flex flex-1 items-center gap-3">
                                    <span className="grid size-9 shrink-0 place-items-center rounded-xl border border-rose-500/20 bg-rose-500/10 text-rose-300">
                                        {rule.icon}
                                    </span>
                                    <span className="min-w-0">
                                        <span className="flex flex-wrap items-center gap-2">
                                            <span className="text-sm font-medium text-zinc-100">
                                                {rule.title}
                                            </span>
                                            <Badge
                                                variant="outline"
                                                className={`uppercase tracking-wider ${rule.badge.className}`}
                                            >
                                                {rule.badge.label}
                                            </Badge>
                                        </span>
                                        <span className="mt-0.5 block font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                                            {rule.id} · Servidor enforced
                                        </span>
                                    </span>
                                </span>
                            </AccordionTrigger>
                            <AccordionContent className="px-5">
                                <p className="pl-12 text-sm leading-relaxed text-zinc-400">
                                    {rule.description}
                                </p>
                                <div className="mt-3 flex flex-wrap gap-2 pl-12">
                                    {rule.details.map((detail) => (
                                        <Badge
                                            key={detail.label}
                                            variant="outline"
                                            className="border-white/10 bg-white/[0.03] font-normal text-zinc-300"
                                        >
                                            <span className="text-zinc-500">
                                                {detail.label}:
                                            </span>{" "}
                                            {detail.value}
                                        </Badge>
                                    ))}
                                </div>
                                <Separator className="my-4 bg-white/[0.06]" />
                                <p className="flex items-center gap-1.5 pl-12 text-xs text-emerald-300">
                                    <ShieldCheck className="size-3.5" />
                                    Imposta pelo servidor — a tela não consegue
                                    afrouxar esta regra.
                                </p>
                            </AccordionContent>
                        </AccordionItem>
                    ))}
                </Accordion>
            )}
        </main>
    );
}
