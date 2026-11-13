import { motion } from "motion/react";
import {
    ClipboardCheck,
    Lock,
    Radar,
    ShieldCheck,
    Timer,
    TriangleAlert,
    type LucideIcon,
} from "lucide-react";
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, getApiErrorMessage } from "@/lib/api";
import { fadeUp, staggerContainer } from "@/lib/motion";
import type { Scope } from "./campanha/types";
import { PageHeader } from "./layout/page-header";
import { Badge } from "./ui/badge";
import { Card, CardContent } from "./ui/card";

interface Rule {
    id: string;
    title: string;
    icon: LucideIcon;
    description: string;
    badge: { label: string; className: string };
    details: { label: string; value: string }[];
}

const ENFORCED = "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";

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
            icon: Lock,
            description:
                "O executor só pode emitir GET e OPTIONS. Qualquer método mutável é interrompido antes de tocar a rede.",
            badge: { label: "Enforced", className: ENFORCED },
            details: [
                { label: "Métodos permitidos", value: methods.join(" · ") },
                { label: "Perfis bloqueados", value: blocked.join(" · ") || "—" },
            ],
        },
        {
            id: "SCOPE-001",
            title: "Fronteira de escopo",
            icon: Radar,
            description:
                "O alvo é travado no servidor: toda requisição é comparada com o alvo autorizado, nunca com a intenção do prompt.",
            badge: lockedTarget
                ? {
                      label: "Alvo travado",
                      className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
                  }
                : { label: "Allowlist do servidor", className: ENFORCED },
            details: [
                { label: "Alvo", value: lockedTarget ?? "allowlist do servidor" },
                {
                    label: "Redes privadas",
                    value: blocksPrivate ? "bloqueadas (anti-SSRF)" : "permitidas",
                },
            ],
        },
        {
            id: "RATE-002",
            title: "Ritmo controlado",
            icon: Timer,
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
            icon: ClipboardCheck,
            description:
                "Ações sensíveis ficam em fila com contexto e evidência até que uma pessoa aprove ou rejeite.",
            badge: preapproval?.active.length
                ? {
                      label: `${preapproval.active.length} pré-aprovados`,
                      className: ENFORCED,
                  }
                : {
                      label: "Em fila",
                      className: "border-border/60 bg-muted/30 text-muted-foreground",
                  },
            details: [
                {
                    label: "Pré-aprovações ativas",
                    value: preapproval?.active.length
                        ? preapproval.active.join(" · ")
                        : "nenhuma",
                },
                { label: "Aprovado por", value: preapproval?.approved_by || "—" },
            ],
        },
    ];
}

export default function Regras() {
    const scopeQuery = useQuery({
        queryKey: ["scope"],
        queryFn: async () => (await api.get<Scope>("/scope")).data,
    });
    const scope = scopeQuery.data ?? null;
    const rules = useMemo(() => buildRules(scope), [scope]);

    return (
        <div className="space-y-5">
            <PageHeader
                eyebrow="Motor de políticas"
                title="Regras de engajamento"
                description="Determinismo no executor. Explicação no agente. Segurança por construção."
            />

            <div className="flex flex-wrap items-center gap-2">
                <Badge
                    variant="outline"
                    className="border-border/60 bg-card/50 uppercase tracking-wider text-muted-foreground"
                >
                    {rules.length} regras ativas
                </Badge>
                <Badge
                    variant="outline"
                    className={`uppercase tracking-wider ${ENFORCED}`}
                >
                    Impostas pelo servidor
                </Badge>
            </div>

            {scopeQuery.isError && (
                <div className="flex items-center gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/[0.06] px-4 py-3 text-sm text-rose-200">
                    <TriangleAlert className="size-4 shrink-0" />
                    <span className="flex-1">{getApiErrorMessage(scopeQuery.error)}</span>
                    <button
                        className="underline-offset-2 hover:underline"
                        onClick={() => void scopeQuery.refetch()}
                    >
                        Tentar de novo
                    </button>
                </div>
            )}

            <motion.div
                variants={staggerContainer(0.08)}
                initial="hidden"
                animate="show"
                className="grid gap-3 sm:grid-cols-2"
            >
                {rules.map((rule) => {
                    const Icon = rule.icon;
                    return (
                        <motion.div
                            key={rule.id}
                            variants={fadeUp}
                            whileHover={{ y: -3 }}
                        >
                            <Card className="h-full border-border/60 bg-card/50 backdrop-blur-sm transition-colors hover:border-border">
                                <CardContent className="flex h-full flex-col p-5">
                                    <div className="flex items-start gap-3">
                                        <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
                                            <Icon className="size-5" />
                                        </span>
                                        <div className="min-w-0 flex-1">
                                            <div className="flex flex-wrap items-center gap-2">
                                                <h2 className="text-sm font-semibold text-foreground">
                                                    {rule.title}
                                                </h2>
                                                <Badge
                                                    variant="outline"
                                                    className={`uppercase tracking-wider ${rule.badge.className}`}
                                                >
                                                    {rule.badge.label}
                                                </Badge>
                                            </div>
                                            <p className="mt-0.5 font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                                                {rule.id} · servidor enforced
                                            </p>
                                        </div>
                                    </div>

                                    <p className="mt-3 text-sm leading-relaxed text-muted-foreground">
                                        {rule.description}
                                    </p>

                                    <div className="mt-3 flex flex-wrap gap-1.5">
                                        {rule.details.map((detail) => (
                                            <span
                                                key={detail.label}
                                                className="rounded-md border border-border/60 bg-muted/20 px-2 py-1 text-[11px] text-foreground/90"
                                            >
                                                <span className="text-muted-foreground">
                                                    {detail.label}:
                                                </span>{" "}
                                                {detail.value}
                                            </span>
                                        ))}
                                    </div>

                                    <p className="mt-auto flex items-center gap-1.5 pt-4 text-xs text-emerald-300">
                                        <ShieldCheck className="size-3.5" />
                                        A tela não consegue afrouxar esta regra.
                                    </p>
                                </CardContent>
                            </Card>
                        </motion.div>
                    );
                })}
            </motion.div>
        </div>
    );
}
