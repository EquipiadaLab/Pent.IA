import { AnimatePresence, motion } from "motion/react";
import {
    Check,
    ChevronRight,
    Copy,
    Crosshair,
    FileText,
    LoaderCircle,
    ScrollText,
    TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { getApiErrorMessage } from "@/lib/api";
import {
    primaryCampaignId,
    useCampaign,
    useCampaignsList,
} from "@/hooks/use-campaigns";
import { ACCENT, agentForMove } from "@/data/agents";
import { fadeUp, staggerContainer } from "@/lib/motion";
import type { CampaignMove } from "./campanha/types";
import { PageHeader } from "./layout/page-header";
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
            className: "border-border/60 bg-muted/30 text-muted-foreground",
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
    if (evidence.response_status !== null)
        lines.push(`HTTP/1.1 ${evidence.response_status}`);
    for (const [key, value] of Object.entries(evidence.response_headers))
        lines.push(`${key}: ${value}`);
    if (evidence.response_sha256) lines.push(`# sha256: ${evidence.response_sha256}`);
    if (evidence.note) lines.push(`# nota: ${evidence.note}`);
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
    const campaignsQuery = useCampaignsList();
    const campaigns = useMemo(
        () => campaignsQuery.data || [],
        [campaignsQuery.data],
    );
    const campaignId = primaryCampaignId(campaigns);
    const campaignQuery = useCampaign(campaignId);
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
        <div className="space-y-5">
            <PageHeader
                eyebrow="Registro de evidências"
                title="Achados validados"
                description="Cada risco tem uma evidência, uma confiança e um próximo movimento."
                actions={
                    <Button
                        variant="outline"
                        size="sm"
                        disabled={!selected}
                        className="rounded-xl border-border/60 bg-card/50"
                        onClick={() => selected && copy(rawResponse(selected), "header")}
                    >
                        {copiedKey === "header" ? <Check /> : <Copy />}
                        {copiedKey === "header" ? "Copiado" : "Copiar evidência"}
                    </Button>
                }
            />

            <div className="flex items-center justify-between gap-3 text-xs">
                <p className="flex items-center gap-2 font-mono uppercase tracking-wider text-muted-foreground">
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
                <Card className="border-rose-500/30 bg-rose-500/[0.06]">
                    <CardContent className="flex items-center gap-3 py-4 text-sm text-rose-200">
                        <TriangleAlert className="size-4 shrink-0" />
                        {error}
                    </CardContent>
                </Card>
            )}

            {isLoading ? (
                <Card className="border-border/60 bg-card/40">
                    <CardContent className="flex min-h-56 items-center justify-center text-muted-foreground">
                        <LoaderCircle className="size-5 animate-spin" />
                    </CardContent>
                </Card>
            ) : findings.length === 0 ? (
                <Card className="border-border/60 bg-card/40">
                    <CardContent className="flex min-h-56 flex-col items-center justify-center gap-3 text-center">
                        <ScrollText className="size-7 text-muted-foreground" />
                        <div>
                            <p className="text-sm font-medium text-foreground">
                                Nenhum achado validado ainda
                            </p>
                            <p className="mt-1 text-xs text-muted-foreground">
                                Os achados aparecem aqui conforme o agente valida os lances.
                            </p>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
                    <motion.div
                        variants={staggerContainer(0.05)}
                        initial="hidden"
                        animate="show"
                        className="grid content-start gap-3"
                    >
                        {findings.map((move) => {
                            const badge = severityBadge(move);
                            const id = findingId(move);
                            const isActive = selected ? findingId(selected) === id : false;
                            const agent = agentForMove(move);
                            const accent = ACCENT[agent.accent];
                            return (
                                <motion.button
                                    key={id}
                                    variants={fadeUp}
                                    type="button"
                                    aria-pressed={isActive}
                                    onClick={() => setSelectedId(id)}
                                    whileHover={{ y: -2 }}
                                    className={`group rounded-2xl border p-5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary/40 ${
                                        isActive
                                            ? "border-primary/50 bg-primary/[0.06] ring-1 ring-primary/30"
                                            : "border-border/60 bg-card/50 hover:border-border"
                                    }`}
                                >
                                    <div className="flex items-start justify-between gap-3">
                                        <span className="font-mono text-[11px] uppercase tracking-wider text-muted-foreground">
                                            {id} · {findingPath(move)}
                                        </span>
                                        <Badge
                                            variant="outline"
                                            className={`uppercase tracking-wider ${badge.className}`}
                                        >
                                            {badge.label}
                                        </Badge>
                                    </div>
                                    <h2 className="mt-3 text-lg font-semibold tracking-tight text-foreground">
                                        {move.title}
                                    </h2>
                                    <p className="mt-1.5 line-clamp-2 text-sm leading-relaxed text-muted-foreground">
                                        {move.explanation ||
                                            move.ai_explanation ||
                                            move.plan?.hypothesis ||
                                            "Sem descrição registrada para este achado."}
                                    </p>
                                    <div className="mt-4 flex items-center justify-between border-t border-border/50 pt-3 text-[11px] text-muted-foreground">
                                        <span className="flex items-center gap-2">
                                            <span
                                                className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 ${accent.border} ${accent.text}`}
                                            >
                                                <agent.icon className="size-3" />
                                                {agent.name}
                                            </span>
                                            Confiança {confidenceLabel(move.confidence)}
                                        </span>
                                        <ChevronRight
                                            className={`size-4 transition-colors ${
                                                isActive
                                                    ? "text-primary"
                                                    : "text-muted-foreground/40 group-hover:text-muted-foreground"
                                            }`}
                                        />
                                    </div>
                                </motion.button>
                            );
                        })}
                    </motion.div>

                    <div className="lg:sticky lg:top-6 lg:self-start">
                        <AnimatePresence mode="wait">
                            {selected && (
                                <motion.div
                                    key={findingId(selected)}
                                    initial={{ opacity: 0, y: 12 }}
                                    animate={{ opacity: 1, y: 0 }}
                                    exit={{ opacity: 0, y: -8 }}
                                    transition={{ duration: 0.25 }}
                                >
                                    <NarrativePanel
                                        move={selected}
                                        copiedKey={copiedKey}
                                        onCopyRaw={() => copy(rawResponse(selected), "raw")}
                                    />
                                </motion.div>
                            )}
                        </AnimatePresence>
                    </div>
                </div>
            )}
        </div>
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
        <Card className="border-primary/20 bg-gradient-to-b from-primary/[0.06] to-card/60">
            <CardContent className="p-5">
                <div className="flex items-center justify-between gap-3">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.18em] text-primary">
                        <span className="size-1.5 rounded-full bg-primary" />
                        Narrativa selecionada
                    </p>
                    <Badge
                        variant="outline"
                        className="border-primary/30 bg-primary/10 font-mono uppercase tracking-wider text-primary"
                    >
                        {findingId(move)}
                    </Badge>
                </div>
                <h2 className="mt-2 text-lg font-semibold tracking-tight text-foreground">
                    {move.title}
                </h2>

                <div className="mt-4 space-y-3">
                    <NarrativeRow
                        icon={<Crosshair className="size-4 text-rose-300" />}
                        label="Ação"
                        text={move.plan?.action || `Verificação controlada em ${path}.`}
                    />
                    <NarrativeRow
                        icon={<FileText className="size-4 text-sky-300" />}
                        label="Evidência"
                        text={`${move.evidence.length} evidência${
                            move.evidence.length === 1 ? "" : "s"
                        } · confiança ${confidenceLabel(move.confidence)}.`}
                    />
                    <NarrativeRow
                        icon={<TriangleAlert className="size-4 text-amber-300" />}
                        label="Impacto"
                        text={
                            [
                                move.impact,
                                move.recommendation
                                    ? `Correção: ${move.recommendation}`
                                    : "",
                            ]
                                .filter(Boolean)
                                .join(" ") || "Sem impacto priorizado para este achado."
                        }
                    />
                </div>

                <div className="mt-4 rounded-xl border border-border/60 bg-background/50">
                    <div className="flex items-center justify-between border-b border-border/50 px-3 py-2">
                        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
                            Resposta bruta
                        </span>
                        <Button
                            variant="ghost"
                            size="icon-xs"
                            aria-label="Copiar resposta bruta"
                            className="text-muted-foreground hover:text-foreground"
                            onClick={onCopyRaw}
                        >
                            {copiedKey === "raw" ? <Check /> : <Copy />}
                        </Button>
                    </div>
                    <pre className="max-h-64 overflow-auto px-3 py-3 font-mono text-[11px] leading-relaxed text-muted-foreground">
                        {rawResponse(move)}
                    </pre>
                </div>
            </CardContent>
        </Card>
    );
}

function NarrativeRow({
    icon,
    label,
    text,
}: {
    icon: React.ReactNode;
    label: string;
    text: string;
}) {
    return (
        <div className="flex gap-3 rounded-xl border border-border/50 bg-background/30 p-3">
            <span className="mt-0.5 grid size-8 shrink-0 place-items-center rounded-lg border border-border/60 bg-card">
                {icon}
            </span>
            <div className="min-w-0">
                <p className="text-[10px] uppercase tracking-wider text-muted-foreground">
                    {label}
                </p>
                <p className="mt-1 text-xs leading-relaxed text-foreground/90">{text}</p>
            </div>
        </div>
    );
}
