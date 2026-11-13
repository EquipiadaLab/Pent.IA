import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
    ClipboardCheck,
    ClipboardX,
    Clock,
    Flag,
    History,
    Lightbulb,
    LoaderCircle,
    RefreshCw,
    Search,
    ShieldOff,
    Square,
    TriangleAlert,
    Zap,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ACTIVE_STATES } from "./campanha/helpers";
import {
    primaryCampaignId,
    useCampaignsList,
} from "@/hooks/use-campaigns";
import { fadeUp, staggerContainer } from "@/lib/motion";
import type { TimelineEntry } from "./campanha/types";
import { PageHeader } from "./layout/page-header";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";

type StatusTone = { label: string; className: string };

const STATUS: Record<string, StatusTone> = {
    permitido: {
        label: "Permitido",
        className: "border-border/60 bg-muted/30 text-muted-foreground",
    },
    bloqueado: {
        label: "Bloqueado",
        className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    },
    aprovado: {
        label: "Aprovado",
        className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-300",
    },
    negado: {
        label: "Negado",
        className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
    },
    fila: {
        label: "Em fila",
        className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
    },
    registrado: {
        label: "Registrado",
        className: "border-border/60 bg-muted/20 text-muted-foreground",
    },
    parado: {
        label: "Parado",
        className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
    },
};

interface AuditRow {
    key: string;
    time: string;
    actor: string;
    action: string;
    icon: React.ReactNode;
    target: string;
    status: StatusTone;
    search: string;
}

function str(details: Record<string, unknown>, key: string): string {
    const value = details[key];
    return typeof value === "string" ? value : "";
}

function targetLabel(details: Record<string, unknown>): string {
    const raw = str(details, "url") || str(details, "origin");
    if (!raw) return "—";
    try {
        const url = new URL(raw);
        return url.pathname && url.pathname !== "/" ? url.pathname : url.host;
    } catch {
        return raw;
    }
}

function moveSuffix(move: number | null) {
    return move ? ` ${String(move).padStart(2, "0")}` : "";
}

function describe(entry: TimelineEntry): Omit<AuditRow, "key" | "time" | "search"> {
    const d = entry.details || {};
    switch (entry.kind) {
        case "decision":
            return {
                actor: "agente/planner",
                action: `Planejou lance${moveSuffix(entry.move)}`,
                icon: <Lightbulb className="size-3.5 text-primary" />,
                target: str(d, "test_id") || "—",
                status: STATUS.registrado,
            };
        case "command":
            return {
                actor: "agente/executor",
                action: `Executou ${str(d, "method") || "requisição"}`,
                icon: <Zap className="size-3.5 text-primary" />,
                target: targetLabel(d),
                status: d.allowed === false ? STATUS.bloqueado : STATUS.permitido,
            };
        case "blocked":
            return {
                actor: "política/escopo",
                action: "Bloqueou origem não autorizada",
                icon: <ShieldOff className="size-3.5 text-rose-300" />,
                target: targetLabel(d),
                status: STATUS.bloqueado,
            };
        case "approval": {
            const approved = str(d, "approval") === "approved";
            return {
                actor: `humano/${str(d, "actor") || "operador"}`,
                action: `${approved ? "Aprovou" : "Negou"} lance${moveSuffix(entry.move)}`,
                icon: approved ? (
                    <ClipboardCheck className="size-3.5 text-emerald-300" />
                ) : (
                    <ClipboardX className="size-3.5 text-amber-300" />
                ),
                target: "—",
                status: approved ? STATUS.aprovado : STATUS.negado,
            };
        }
        case "approval_requested":
            return {
                actor: "agente/planner",
                action: `Solicitou aprovação${moveSuffix(entry.move)}`,
                icon: <Clock className="size-3.5 text-sky-300" />,
                target: "—",
                status: STATUS.fila,
            };
        case "result":
            return {
                actor: "agente/executor",
                action: `Registrou resultado${moveSuffix(entry.move)}`,
                icon: <ClipboardCheck className="size-3.5 text-primary" />,
                target: entry.move ? `lance ${String(entry.move).padStart(2, "0")}` : "—",
                status: STATUS.registrado,
            };
        case "stop":
            return {
                actor: `humano/${str(d, "actor") || "operador"}`,
                action: "Parada de emergência",
                icon: <Square className="size-3.5 text-rose-300" />,
                target: "—",
                status: STATUS.parado,
            };
        case "campaign":
            return {
                actor: "sistema",
                action: entry.summary,
                icon: <Flag className="size-3.5 text-muted-foreground" />,
                target: str(d, "origin") || str(d, "state") || "—",
                status: STATUS.registrado,
            };
        default:
            return {
                actor: "sistema",
                action: entry.summary,
                icon: <History className="size-3.5 text-muted-foreground" />,
                target: "—",
                status: STATUS.registrado,
            };
    }
}

export default function Auditoria() {
    const [search, setSearch] = useState("");
    const campaignsQuery = useCampaignsList();
    const campaigns = useMemo(
        () => campaignsQuery.data || [],
        [campaignsQuery.data],
    );
    const campaignId = primaryCampaignId(campaigns);

    const auditQuery = useQuery({
        queryKey: ["campaign-audit", campaignId],
        queryFn: async () =>
            (
                await api.get<TimelineEntry[]>(
                    `/campaigns/${encodeURIComponent(campaignId)}/audit`,
                )
            ).data,
        enabled: Boolean(campaignId),
        refetchInterval: () => {
            const active = campaigns.find((item) => item.id === campaignId);
            return active && ACTIVE_STATES.includes(active.state) ? 4000 : false;
        },
    });

    const rows = useMemo<AuditRow[]>(() => {
        const entries = auditQuery.data || [];
        return [...entries]
            .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
            .map((entry, index) => {
                const described = describe(entry);
                return {
                    key: `${entry.at}-${index}`,
                    time: new Date(entry.at).toLocaleTimeString("pt-BR", {
                        hour12: false,
                    }),
                    ...described,
                    search:
                        `${described.actor} ${described.action} ${described.target} ${described.status.label} ${entry.summary}`.toLowerCase(),
                };
            });
    }, [auditQuery.data]);

    const filtered = useMemo(() => {
        const term = search.trim().toLowerCase();
        if (!term) return rows;
        return rows.filter((row) => row.search.includes(term));
    }, [rows, search]);

    const error = campaignsQuery.error
        ? getApiErrorMessage(campaignsQuery.error)
        : auditQuery.error
            ? getApiErrorMessage(auditQuery.error)
            : "";
    const isLoading =
        campaignsQuery.isPending ||
        (Boolean(campaignId) && auditQuery.isPending);
    const isSyncing = auditQuery.isFetching;

    return (
        <div className="space-y-5">
            <PageHeader
                eyebrow="Append only"
                title="Trilha de auditoria"
                description="Ações do agente, aprovações humanas e bloqueios em uma única linha do tempo."
            />

            <div className="overflow-hidden rounded-2xl border border-border/60 bg-card/40 backdrop-blur-sm">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 p-4">
                    <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                        <History className="size-4" />
                        {String(rows.length).padStart(2, "0")} eventos nesta campanha
                    </p>
                    <div className="flex items-center gap-2">
                        <div className="relative">
                            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                            <Input
                                value={search}
                                onChange={(event) => setSearch(event.target.value)}
                                placeholder="Buscar evento..."
                                className="h-9 w-56 rounded-xl border-border/60 bg-background/50 pl-9 text-sm"
                            />
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={!campaignId || isSyncing}
                            onClick={() => void auditQuery.refetch()}
                            className="rounded-xl border-border/60 bg-card/50"
                        >
                            <RefreshCw className={isSyncing ? "animate-spin" : ""} />
                            Sincronizar
                        </Button>
                    </div>
                </div>

                {error ? (
                    <div className="flex items-center gap-3 p-6 text-sm text-rose-200">
                        <TriangleAlert className="size-4 shrink-0" />
                        {error}
                    </div>
                ) : isLoading ? (
                    <div className="flex min-h-48 items-center justify-center text-muted-foreground">
                        <LoaderCircle className="size-5 animate-spin" />
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-center text-sm text-muted-foreground">
                        <History className="size-6 opacity-60" />
                        {rows.length === 0
                            ? "Nenhum evento registrado nesta campanha ainda."
                            : "Nenhum evento corresponde à busca."}
                    </div>
                ) : (
                    <motion.ul
                        variants={staggerContainer(0.025)}
                        initial="hidden"
                        animate="show"
                        className="divide-y divide-border/40"
                    >
                        {filtered.map((row) => (
                            <motion.li
                                key={row.key}
                                variants={fadeUp}
                                className="flex items-center gap-3 px-4 py-2.5 transition-colors hover:bg-foreground/[0.02]"
                            >
                                <span className="w-16 shrink-0 font-mono text-xs text-muted-foreground tabular-nums">
                                    {row.time}
                                </span>
                                <span className="grid size-7 shrink-0 place-items-center rounded-lg border border-border/60 bg-background/50">
                                    {row.icon}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <p className="truncate text-sm text-foreground">
                                        {row.action}
                                    </p>
                                    <p className="truncate font-mono text-[11px] text-muted-foreground">
                                        {row.actor} · {row.target}
                                    </p>
                                </div>
                                <Badge
                                    variant="outline"
                                    className={`shrink-0 uppercase tracking-wider ${row.status.className}`}
                                >
                                    {row.status.label}
                                </Badge>
                            </motion.li>
                        ))}
                    </motion.ul>
                )}
            </div>
        </div>
    );
}
