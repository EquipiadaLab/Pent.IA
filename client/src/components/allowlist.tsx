import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
    AlertTriangle,
    LoaderCircle,
    Lock,
    RefreshCw,
    ShieldBan,
    Target,
} from "lucide-react";
import { api, getApiErrorMessage } from "@/lib/api";
import { fadeUp, staggerContainer } from "@/lib/motion";
import type { Scope } from "./campanha/types";
import { PageHeader } from "./layout/page-header";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

export default function Allowlist() {
    const scopeQuery = useQuery({
        queryKey: ["scope"],
        queryFn: async () => (await api.get<Scope>("/scope")).data,
    });
    const scope = scopeQuery.data;
    const lockedTarget = scope?.locked_target ?? null;
    const targets = scope?.authorized_targets ?? [];

    return (
        <div className="space-y-5">
            <PageHeader
                eyebrow="Superfície autorizada"
                title="Escopo e allowlist"
                description="O agente só enxerga o alvo autorizado pela configuração do servidor."
                actions={
                    <Button
                        aria-label="Atualizar escopo"
                        variant="outline"
                        size="icon-sm"
                        className="rounded-xl border-border/60 bg-card/50"
                        disabled={scopeQuery.isFetching}
                        onClick={() => void scopeQuery.refetch()}
                    >
                        <RefreshCw className={scopeQuery.isFetching ? "animate-spin" : ""} />
                    </Button>
                }
            />

            {scopeQuery.isError && (
                <div
                    role="alert"
                    className="flex items-center justify-between gap-3 rounded-2xl border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200"
                >
                    <span>{getApiErrorMessage(scopeQuery.error)}</span>
                    <Button
                        variant="outline"
                        size="sm"
                        className="rounded-xl border-rose-500/30 text-rose-200 hover:bg-rose-500/10"
                        onClick={() => void scopeQuery.refetch()}
                    >
                        Tentar novamente
                    </Button>
                </div>
            )}

            {scopeQuery.isPending ? (
                <Card className="border-border/60 bg-card/40">
                    <CardContent className="flex min-h-56 items-center justify-center text-muted-foreground">
                        <LoaderCircle className="size-5 animate-spin" />
                    </CardContent>
                </Card>
            ) : (
                <motion.div
                    variants={staggerContainer(0.08)}
                    initial="hidden"
                    animate="show"
                    className="grid gap-4 lg:grid-cols-[1.4fr_1fr]"
                >
                    {/* Alvo travado */}
                    <motion.div variants={fadeUp}>
                        <Card className="relative h-full overflow-hidden border-primary/25 bg-gradient-to-br from-primary/[0.08] to-card/60">
                            <CardContent className="p-6">
                                <div className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                                    <Target className="size-4" />
                                    Alvo autorizado
                                </div>
                                <div className="mt-4 flex items-center gap-3 rounded-2xl border border-border/60 bg-background/50 p-4">
                                    <span className="grid size-11 shrink-0 place-items-center rounded-xl border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                                        <Lock className="size-5" />
                                    </span>
                                    <div className="min-w-0 flex-1">
                                        <p className="break-all font-mono text-sm text-foreground">
                                            {lockedTarget || targets[0] || "Definido pelo servidor"}
                                        </p>
                                        <p className="mt-0.5 text-[11px] uppercase tracking-wider text-muted-foreground">
                                            {lockedTarget
                                                ? "Alvo travado · só este endereço é testado"
                                                : "Allowlist do servidor"}
                                        </p>
                                    </div>
                                    <span className="shrink-0 rounded-md border border-emerald-500/30 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
                                        ALLOW
                                    </span>
                                </div>
                                {targets.length > 1 && (
                                    <ul className="mt-2 space-y-1.5">
                                        {targets.slice(1).map((origin) => (
                                            <li
                                                key={origin}
                                                className="break-all rounded-lg border border-border/50 bg-background/30 px-3 py-2 font-mono text-xs text-muted-foreground"
                                            >
                                                {origin}
                                            </li>
                                        ))}
                                    </ul>
                                )}
                                <p className="mt-4 text-xs leading-relaxed text-muted-foreground">
                                    A tela não cria campo de URL: qualquer outro endereço enviado
                                    é recusado pelo servidor com <code className="font-mono">403</code>.
                                </p>
                            </CardContent>
                        </Card>
                    </motion.div>

                    {/* Limites / fora de escopo */}
                    <motion.div variants={fadeUp} className="grid content-start gap-4">
                        <Card className="border-rose-500/15 bg-rose-500/[0.035]">
                            <CardContent className="p-5">
                                <div className="flex items-start gap-3">
                                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-400" />
                                    <div>
                                        <p className="text-sm font-semibold text-foreground">
                                            Fora do escopo
                                        </p>
                                        <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                                            Destinos não autorizados são bloqueados pelo servidor.
                                            Esta tela é somente leitura, carregada de{" "}
                                            <code className="font-mono">/scope</code>.
                                        </p>
                                    </div>
                                </div>
                            </CardContent>
                        </Card>

                        <Card className="border-border/60 bg-card/50">
                            <CardContent className="space-y-3 p-5 text-xs">
                                <Row
                                    label="Métodos permitidos"
                                    value={scope?.allowed_methods.join(" · ") || "—"}
                                />
                                <Row
                                    label="Máx. requisições/s"
                                    value={String(scope?.limits.max_requests_per_second ?? "—")}
                                />
                                <Row
                                    label="Máx. por campanha"
                                    value={String(scope?.limits.max_total_requests ?? "—")}
                                />
                                <Row
                                    icon={<ShieldBan className="size-3.5 text-rose-300" />}
                                    label="Redes privadas"
                                    value={
                                        scope?.blocks_private_targets
                                            ? "bloqueadas (anti-SSRF)"
                                            : "permitidas"
                                    }
                                />
                            </CardContent>
                        </Card>
                    </motion.div>
                </motion.div>
            )}
        </div>
    );
}

function Row({
    label,
    value,
    icon,
}: {
    label: string;
    value: string;
    icon?: React.ReactNode;
}) {
    return (
        <div className="flex items-center justify-between gap-4 border-b border-border/50 pb-2.5 last:border-0 last:pb-0">
            <span className="flex items-center gap-1.5 text-muted-foreground">
                {icon}
                {label}
            </span>
            <span className="text-right font-mono text-foreground/90">{value}</span>
        </div>
    );
}
