import { useQuery } from "@tanstack/react-query";
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
import { useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ACTIVE_STATES } from "./campanha/helpers";
import type { Campaign, TimelineEntry } from "./campanha/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "./ui/table";

type StatusTone = { label: string; className: string };

const STATUS: Record<string, StatusTone> = {
    permitido: {
        label: "Permitido",
        className: "border-white/15 bg-white/[0.04] text-zinc-300",
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
        className: "border-white/10 bg-white/[0.03] text-zinc-500",
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
                icon: <Lightbulb className="size-3.5 text-rose-300" />,
                target: str(d, "test_id") || "—",
                status: STATUS.registrado,
            };
        case "command":
            return {
                actor: "agente/executor",
                action: `Executou ${str(d, "method") || "requisição"}`,
                icon: <Zap className="size-3.5 text-rose-300" />,
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
                icon: <ClipboardCheck className="size-3.5 text-rose-300" />,
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
                icon: <Flag className="size-3.5 text-zinc-400" />,
                target: str(d, "origin") || str(d, "state") || "—",
                status: STATUS.registrado,
            };
        default:
            return {
                actor: "sistema",
                action: entry.summary,
                icon: <History className="size-3.5 text-zinc-400" />,
                target: "—",
                status: STATUS.registrado,
            };
    }
}

function useClock() {
    const [now, setNow] = useState(() => new Date());
    useEffect(() => {
        const timer = window.setInterval(() => setNow(new Date()), 1000);
        return () => window.clearInterval(timer);
    }, []);
    return now;
}

export default function Auditoria() {
    const [search, setSearch] = useState("");

    const campaignsQuery = useQuery({
        queryKey: ["campaigns"],
        queryFn: async () => {
            const { data } = await api.get<Campaign[]>("/campaigns");
            return [...data].sort(
                (a, b) =>
                    new Date(b.created_at).getTime() -
                    new Date(a.created_at).getTime(),
            );
        },
        refetchInterval: 5000,
    });

    const campaigns = useMemo(
        () => campaignsQuery.data || [],
        [campaignsQuery.data],
    );
    const campaignId =
        campaigns.find((item) => ACTIVE_STATES.includes(item.state))?.id ||
        campaigns[0]?.id ||
        "";

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
        <main className="mx-auto w-full max-w-[1500px] pb-12">
            <header className="flex flex-wrap items-start justify-between gap-4 pt-8">
                <div>
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-rose-500">
                        <span className="h-px w-6 bg-rose-500" />
                        Trilha de auditoria · append only
                    </p>
                    <h1 className="mt-2 text-4xl font-semibold tracking-tight">
                        Trilha de auditoria
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Ações do agente, aprovações humanas e bloqueios em uma única
                        linha do tempo.
                    </p>
                </div>
                <div className="text-right font-mono text-[11px] leading-relaxed text-zinc-500">
                    <p>{dateLabel}</p>
                    <p className="tabular-nums text-zinc-400">{timeLabel} BRT</p>
                </div>
            </header>

            <div className="mt-6 rounded-2xl border border-white/10 bg-zinc-950/70">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.07] p-4">
                    <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                        <History className="size-4" />
                        {String(rows.length).padStart(2, "0")} eventos nesta campanha
                    </p>
                    <div className="flex items-center gap-2">
                        <div className="relative">
                            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-zinc-500" />
                            <Input
                                value={search}
                                onChange={(event) => setSearch(event.target.value)}
                                placeholder="Buscar evento..."
                                className="h-9 w-56 rounded-xl border-white/10 bg-zinc-900 pl-9 text-sm"
                            />
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={!campaignId || isSyncing}
                            onClick={() => void auditQuery.refetch()}
                            className="border-white/10 bg-white/[0.03] text-zinc-200 hover:bg-white/10"
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
                    <div className="flex min-h-48 items-center justify-center text-zinc-500">
                        <LoaderCircle className="size-5 animate-spin" />
                    </div>
                ) : filtered.length === 0 ? (
                    <div className="flex min-h-48 flex-col items-center justify-center gap-2 text-center text-sm text-zinc-400">
                        <History className="size-6 text-zinc-600" />
                        {rows.length === 0
                            ? "Nenhum evento registrado nesta campanha ainda."
                            : "Nenhum evento corresponde à busca."}
                    </div>
                ) : (
                    <Table>
                        <TableHeader>
                            <TableRow className="border-white/[0.07] hover:bg-transparent">
                                <TableHead className="pl-4 text-[10px] uppercase tracking-wider text-zinc-500">
                                    Horário
                                </TableHead>
                                <TableHead className="text-[10px] uppercase tracking-wider text-zinc-500">
                                    Ator
                                </TableHead>
                                <TableHead className="text-[10px] uppercase tracking-wider text-zinc-500">
                                    Ação
                                </TableHead>
                                <TableHead className="text-[10px] uppercase tracking-wider text-zinc-500">
                                    Alvo
                                </TableHead>
                                <TableHead className="pr-4 text-right text-[10px] uppercase tracking-wider text-zinc-500">
                                    Status
                                </TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {filtered.map((row) => (
                                <TableRow
                                    key={row.key}
                                    className="border-white/[0.05] hover:bg-white/[0.02]"
                                >
                                    <TableCell className="pl-4 font-mono text-xs text-zinc-400">
                                        {row.time}
                                    </TableCell>
                                    <TableCell className="font-mono text-xs text-zinc-400">
                                        {row.actor}
                                    </TableCell>
                                    <TableCell>
                                        <span className="flex items-center gap-2 text-sm text-zinc-200">
                                            <span className="grid size-6 shrink-0 place-items-center rounded-md border border-white/10 bg-zinc-950">
                                                {row.icon}
                                            </span>
                                            {row.action}
                                        </span>
                                    </TableCell>
                                    <TableCell className="max-w-48 truncate font-mono text-xs text-zinc-400">
                                        {row.target}
                                    </TableCell>
                                    <TableCell className="pr-4 text-right">
                                        <Badge
                                            variant="outline"
                                            className={`uppercase tracking-wider ${row.status.className}`}
                                        >
                                            {row.status.label}
                                        </Badge>
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                )}
            </div>
        </main>
    );
}
