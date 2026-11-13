import { useQuery } from "@tanstack/react-query";
import {
    Check,
    ChevronRight,
    Copy,
    Crosshair,
    FileSearch,
    FileText,
    LoaderCircle,
    ScrollText,
    TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { api, getApiErrorMessage } from "@/lib/api";
import { ACTIVE_STATES } from "./campanha/helpers";
import type { Campaign, CampaignMove } from "./campanha/types";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";

function findingId(move: CampaignMove) {
    return `F-${String(move.move).padStart(3, "0")}`;
}

function findingPath(move: CampaignMove) {
    const request = move.evidence[0]?.request;
    if (request) {
        const path = request.split(/\s+/).find((token) => token.startsWith("/"));
        if (path) return path;
    }
    return move.test_id;
}

function confidenceLabel(confidence: CampaignMove["confidence"]) {
    if (!confidence) return "indefinida";
    return { high: "alta", medium: "média", low: "baixa" }[confidence];
}

function severityBadge(move: CampaignMove): { label: string; className: string } {
    if (move.status === "inconclusive")
        return {
            label: "Inconclusivo",
            className: "border-white/15 bg-white/[0.04] text-zinc-300",
        };
    return {
        low: {
            label: "Baixo",
            className: "border-sky-400/30 bg-sky-400/10 text-sky-300",
        },
        medium: {
            label: "Médio",
            className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
        },
        high: {
            label: "Alto",
            className: "border-rose-400/30 bg-rose-400/10 text-rose-300",
        },
    }[move.severity];
}

const SEVERITY_RANK: Record<CampaignMove["severity"], number> = {
    high: 3,
    medium: 2,
    low: 1,
};

function rawResponse(move: CampaignMove) {
    const evidence = move.evidence[0];
    if (!evidence) return "Sem evidência bruta registrada para este achado.";
    const lines = [evidence.request];
    if (evidence.response_status !== null) {
        lines.push(`HTTP/1.1 ${evidence.response_status}`);
    }
    for (const [key, value] of Object.entries(evidence.response_headers)) {
        lines.push(`${key}: ${value}`);
    }
    if (evidence.response_sha256) {
        lines.push(`# sha256: ${evidence.response_sha256}`);
    }
    if (evidence.note) {
        lines.push(`# nota: ${evidence.note}`);
    }
    return lines.join("\n");
}

function useCopy() {
    const [copiedKey, setCopiedKey] = useState("");
    useEffect(() => {
        if (!copiedKey) return;
        const timer = window.setTimeout(() => setCopiedKey(""), 1600);
        return () => window.clearTimeout(timer);
    }, [copiedKey]);
    const copy = (text: string, key: string) => {
        void navigator.clipboard
            ?.writeText(text)
            .then(() => setCopiedKey(key))
            .catch(() => undefined);
    };
    return { copiedKey, copy };
}

export default function Achados() {
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

    const campaignQuery = useQuery({
        queryKey: ["campaign", campaignId],
        queryFn: async () =>
            (
                await api.get<Campaign>(
                    `/campaigns/${encodeURIComponent(campaignId)}`,
                )
            ).data,
        enabled: Boolean(campaignId),
        refetchInterval: (query) =>
            query.state.data && ACTIVE_STATES.includes(query.state.data.state)
                ? 2500
                : false,
    });

    const campaign = campaignQuery.data || null;
    const findings = useMemo(() => {
        if (!campaign) return [];
        return campaign.moves
            .filter(
                (move) =>
                    move.status &&
                    move.status !== "pass" &&
                    move.approval !== "denied" &&
                    move.approval !== "pending",
            )
            .sort(
                (a, b) =>
                    SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity] ||
                    a.move - b.move,
            );
    }, [campaign]);

    const [selectedId, setSelectedId] = useState("");
    const selected =
        findings.find((move) => findingId(move) === selectedId) ??
        findings[0] ??
        null;

    const { copiedKey, copy } = useCopy();

    const isLoading =
        campaignsQuery.isPending ||
        (Boolean(campaignId) && campaignQuery.isPending);
    const error = campaignsQuery.error
        ? getApiErrorMessage(campaignsQuery.error)
        : campaignQuery.error
            ? getApiErrorMessage(campaignQuery.error)
            : "";

    return (
        <main className="mx-auto w-full max-w-[1500px] pb-12">
            <header className="flex flex-wrap items-end justify-between gap-4 pt-8">
                <div>
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-rose-500">
                        <span className="h-px w-6 bg-rose-500" />
                        Registro de evidências
                    </p>
                    <h1 className="mt-2 text-4xl font-semibold tracking-tight">
                        Achados validados
                    </h1>
                    <p className="mt-1 text-sm text-muted-foreground">
                        Cada risco tem uma evidência, uma confiança e um próximo
                        movimento.
                    </p>
                </div>
                <Button
                    variant="outline"
                    size="sm"
                    disabled={!selected}
                    className="border-white/10 bg-white/[0.03] text-zinc-200 hover:bg-white/10"
                    onClick={() =>
                        selected && copy(rawResponse(selected), "header")
                    }
                >
                    {copiedKey === "header" ? <Check /> : <Copy />}
                    {copiedKey === "header"
                        ? "Evidência copiada"
                        : "Copiar evidência selecionada"}
                </Button>
            </header>

            <div className="mt-6 flex items-center justify-between gap-3">
                <p className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                    <FileSearch className="size-4" />
                    {String(findings.length).padStart(2, "0")} achados nesta campanha
                </p>
                {findings.length > 0 && (
                    <Badge
                        variant="outline"
                        className="border-emerald-500/25 bg-emerald-500/10 uppercase tracking-wider text-emerald-300"
                    >
                        Todos verificáveis
                    </Badge>
                )}
            </div>

            {error && (
                <Card className="mt-4 border-rose-500/30 bg-rose-500/[0.06]">
                    <CardContent className="flex items-center gap-3 py-4 text-sm text-rose-200">
                        <TriangleAlert className="size-4 shrink-0" />
                        {error}
                    </CardContent>
                </Card>
            )}

            {isLoading ? (
                <Card className="mt-4 border-white/10 bg-zinc-950/80">
                    <CardContent className="flex min-h-56 items-center justify-center text-zinc-500">
                        <LoaderCircle className="size-5 animate-spin" />
                    </CardContent>
                </Card>
            ) : findings.length === 0 ? (
                <Card className="mt-4 border-white/10 bg-zinc-950/80">
                    <CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
                        <ScrollText className="size-7 text-zinc-600" />
                        <div>
                            <p className="text-sm font-medium text-zinc-200">
                                Nenhum achado validado ainda
                            </p>
                            <p className="mt-1 text-xs text-zinc-500">
                                Os achados aparecem aqui conforme o agente valida os
                                lances da campanha.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <>
                    <div className="mt-4 grid gap-3 lg:grid-cols-2">
                        {findings.map((move) => {
                            const badge = severityBadge(move);
                            const id = findingId(move);
                            const isActive = selected
                                ? findingId(selected) === id
                                : false;
                            return (
                                <button
                                    key={id}
                                    type="button"
                                    aria-pressed={isActive}
                                    onClick={() => setSelectedId(id)}
                                    className={`group rounded-2xl border bg-zinc-950/70 p-5 text-left transition-colors hover:border-white/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-500/40 ${
                                        isActive
                                            ? "border-rose-500/50 bg-rose-950/10 ring-1 ring-rose-500/30"
                                            : "border-white/10"
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <span className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                                            {id} · {findingPath(move)}
                                        </span>
                                        <Badge
                                            variant="outline"
                                            className={`uppercase tracking-wider ${badge.className}`}
                                        >
                                            {badge.label}
                                        </Badge>
                                    </div>
                                    <h2 className="mt-3 text-lg font-semibold tracking-tight text-zinc-100">
                                        {move.title}
                                    </h2>
                                    <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-zinc-400">
                                        {move.explanation ||
                                            move.ai_explanation ||
                                            move.plan?.hypothesis ||
                                            "Sem descrição registrada para este achado."}
                                    </p>
                                    <div className="mt-5 flex items-center justify-between border-t border-white/[0.06] pt-3 text-[11px] text-zinc-500">
                                        <span>
                                            Confiança {confidenceLabel(move.confidence)}{" "}
                                            · {move.evidence.length} evidência
                                            {move.evidence.length === 1 ? "" : "s"}
                                        </span>
                                        <ChevronRight
                                            className={`size-4 transition-colors ${
                                                isActive
                                                    ? "text-rose-400"
                                                    : "text-zinc-700 group-hover:text-zinc-500"
                                            }`}
                                        />
                                    </div>
                                </button>
                            );
                        })}
                    </div>

                    {selected && (
                        <NarrativePanel
                            move={selected}
                            copiedKey={copiedKey}
                            onCopyRaw={() =>
                                copy(rawResponse(selected), "raw")
                            }
                        />
                    )}
                </>
            )}
        </main>
    );
}

function NarrativePanel({
    move,
    copiedKey,
    onCopyRaw,
}: {
    move: CampaignMove;
    copiedKey: string;
    onCopyRaw: () => void;
}) {
    const path = findingPath(move);
    return (
        <Card className="mt-3 border-rose-500/20 bg-gradient-to-b from-rose-950/10 to-zinc-950/80">
            <CardContent className="p-5">
                <div className="flex items-center justify-between gap-3">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-rose-400">
                        <span className="size-1.5 rounded-full bg-rose-400" />
                        Narrativa selecionada
                    </p>
                    <Badge
                        variant="outline"
                        className="border-rose-500/30 bg-rose-500/10 font-mono uppercase tracking-wider text-rose-300"
                    >
                        {findingId(move)}
                    </Badge>
                </div>
                <h2 className="mt-2 text-lg font-semibold tracking-tight text-zinc-100">
                    {move.title}
                </h2>

                <div className="mt-4 grid gap-4 lg:grid-cols-2">
                    <div className="space-y-3">
                        <NarrativeRow
                            icon={<Crosshair className="size-4 text-rose-300" />}
                            label="Ação"
                            tag="Observado"
                            text={
                                move.plan?.action ||
                                `Verificação controlada em ${path}.`
                            }
                        />
                        <NarrativeRow
                            icon={<FileText className="size-4 text-sky-300" />}
                            label="Evidência"
                            tag="Bruto"
                            text={`${move.evidence.length} evidência${
                                move.evidence.length === 1 ? "" : "s"
                            } · confiança ${confidenceLabel(move.confidence)}.`}
                        />
                        <NarrativeRow
                            icon={
                                <TriangleAlert className="size-4 text-amber-300" />
                            }
                            label="Impacto"
                            tag="Priorizar"
                            text={
                                [
                                    move.impact,
                                    move.recommendation
                                        ? `Correção: ${move.recommendation}`
                                        : "",
                                ]
                                    .filter(Boolean)
                                    .join(" ") ||
                                "Sem impacto priorizado para este achado."
                            }
                        />
                    </div>

                    <div className="flex flex-col rounded-xl border border-white/[0.07] bg-black/40">
                        <div className="flex items-center justify-between border-b border-white/[0.07] px-3 py-2">
                            <span className="font-mono text-[10px] uppercase tracking-wider text-zinc-500">
                                Raw response · selecionada
                            </span>
                            <Button
                                variant="ghost"
                                size="icon-xs"
                                aria-label="Copiar resposta bruta"
                                className="text-zinc-400 hover:bg-white/10 hover:text-white"
                                onClick={onCopyRaw}
                            >
                                {copiedKey === "raw" ? <Check /> : <Copy />}
                            </Button>
                        </div>
                        <pre className="overflow-x-auto px-3 py-3 font-mono text-[11px] leading-relaxed text-zinc-300">
                            {rawResponse(move)}
                        </pre>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

function NarrativeRow({
    icon,
    label,
    tag,
    text,
}: {
    icon: React.ReactNode;
    label: string;
    tag: string;
    text: string;
}) {
    return (
        <div className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-3">
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-white/10 bg-zinc-950">
                {icon}
            </span>
            <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-zinc-500">
                    {label} ·{" "}
                    <span className="text-emerald-400">{tag}</span>
                </p>
                <p className="mt-1 text-xs leading-relaxed text-zinc-300">
                    {text}
                </p>
            </div>
        </div>
    );
}
