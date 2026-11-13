import { api, getApiErrorMessage } from "@/lib/api";
import {
    useMutation,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
    Activity,
    Check,
    Gauge,
    LoaderCircle,
    Play,
    Radio,
    RefreshCw,
    ShieldAlert,
    Sparkles,
    X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { PageHeader } from "./layout/page-header";
import { AgentsConstellation } from "./agents/agents-constellation";
import { AgentRoster } from "./agents/agent-roster";
import { fadeUp, scaleIn, staggerContainer } from "@/lib/motion";
import { CampaignBoard } from "./campanha/campaign-board";
import {
    CampaignCreateForm,
    type CampaignFormValues,
} from "./campanha/campaign-create-form";
import {
    CampaignReport,
    CampaignReportError,
} from "./campanha/campaign-report";
import { ACTIVE_STATES, durationLabel, stateLabel } from "./campanha/helpers";
import type {
    Campaign,
    CampaignStatus,
    CreateCampaignBody,
    GameReview,
    Scope,
} from "./campanha/types";
import {
    useCampaignWebSocket,
    type CampaignWebSocketState,
} from "./campanha/use-campaign-websocket";
import { Button } from "./ui/button";
import { Card, CardContent } from "./ui/card";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "./ui/select";

export default function Campanha() {
    const queryClient = useQueryClient();
    const reduce = useReducedMotion();
    const [selectedId, setSelectedId] = useState("");
    const [showCreate, setShowCreate] = useState(false);
    const [pendingAction, setPendingAction] = useState("");
    const [error, setError] = useState("");
    const [notice, setNotice] = useState("");
    const [showReport, setShowReport] = useState(false);
    const [webSocketState, setWebSocketState] =
        useState<CampaignWebSocketState>({ status: "idle", message: "" });

    const campaignsQuery = useQuery({
        queryKey: ["campaigns"],
        queryFn: async () => {
            const { data } = await api.get<Campaign[]>("/campaigns");
            return [...data].sort(
                (a, b) =>
                    new Date(b.created_at).getTime() - new Date(a.created_at).getTime(),
            );
        },
        refetchInterval: 5000,
    });
    const scopeQuery = useQuery({
        queryKey: ["scope"],
        queryFn: async () => (await api.get<Scope>("/scope")).data,
    });

    const campaigns = useMemo(
        () => campaignsQuery.data || [],
        [campaignsQuery.data],
    );
    const scope = scopeQuery.data || null;
    const defaultCampaign = campaigns.find((item) =>
        ACTIVE_STATES.includes(item.state),
    );
    const campaignId =
        selectedId || defaultCampaign?.id || campaigns[0]?.id || "";
    // Alvo travado no servidor: o front nunca envia URL (docs §2.2/§2.12).
    const lockedTarget =
        scope?.locked_target ||
        scope?.default_target ||
        scope?.authorized_targets[0] ||
        null;

    const campaignQuery = useQuery({
        queryKey: ["campaign", campaignId],
        queryFn: async () =>
            (await api.get<Campaign>(`/campaigns/${encodeURIComponent(campaignId)}`))
                .data,
        enabled: Boolean(campaignId),
        refetchInterval: (query) =>
            query.state.data &&
            ACTIVE_STATES.includes(query.state.data.state) &&
            webSocketState.status !== "connected"
                ? 1500
                : false,
    });
    const statusQuery = useQuery({
        queryKey: ["campaign-status", campaignId],
        queryFn: async () =>
            (
                await api.get<CampaignStatus>(
                    `/campaigns/${encodeURIComponent(campaignId)}/status`,
                )
            ).data,
        enabled: Boolean(campaignId),
        refetchInterval: (query) =>
            query.state.data &&
            ACTIVE_STATES.includes(query.state.data.state) &&
            webSocketState.status !== "connected"
                ? 1500
                : false,
    });
    const campaign = campaignQuery.data || null;
    const campaignStatus = statusQuery.data || null;
    const campaignIsActive = Boolean(
        campaign && ACTIVE_STATES.includes(campaign.state),
    );
    const campaignIsTerminal = Boolean(
        campaign && !ACTIVE_STATES.includes(campaign.state),
    );

    // Game Review (item 7): a primeira chamada ao /report pode levar ~20-30 s (IA).
    const reportQuery = useQuery({
        queryKey: ["campaign-report", campaignId],
        queryFn: async () =>
            (
                await api.get<GameReview>(
                    `/campaigns/${encodeURIComponent(campaignId)}/report`,
                    { timeout: 60_000 },
                )
            ).data,
        enabled: Boolean(campaignId) && campaignIsTerminal && showReport,
        staleTime: 5 * 60_000,
    });

    useCampaignWebSocket({
        campaignId,
        enabled: Boolean(campaign && campaignStatus && campaignIsActive),
        initialSeq: campaignStatus?.last_seq ?? 0,
        onStatusChange: setWebSocketState,
    });

    const createCampaignMutation = useMutation({
        mutationFn: async (body: CreateCampaignBody) =>
            (await api.post<Campaign>("/campaigns", body)).data,
        onSuccess: async (created) => {
            queryClient.setQueryData(["campaign", created.id], created);
            setSelectedId(created.id);
            setShowCreate(false);
            setShowReport(false);
            setNotice("Campanha criada. Acompanhe os lances em tempo real.");
            await queryClient.invalidateQueries({ queryKey: ["campaigns"] });
        },
    });
    const decideMoveMutation = useMutation({
        mutationFn: async ({
            campaignId,
            moveNumber,
            decision,
        }: {
            campaignId: string;
            moveNumber: number;
            decision: "approve" | "deny";
        }) =>
            api.post(
                `/campaigns/${encodeURIComponent(campaignId)}/moves/${moveNumber}/${decision}?actor=operator`,
            ),
        onSuccess: (_response, variables) => {
            void queryClient.invalidateQueries({
                queryKey: ["campaign", variables.campaignId],
            });
            void queryClient.invalidateQueries({
                queryKey: ["campaign-status", variables.campaignId],
            });
        },
    });
    const stopCampaignMutation = useMutation({
        mutationFn: async (campaignId: string) =>
            (
                await api.post<Campaign>(
                    `/campaigns/${encodeURIComponent(campaignId)}/stop`,
                )
            ).data,
        onSuccess: (stopped) => {
            queryClient.setQueryData(["campaign", stopped.id], stopped);
            void queryClient.invalidateQueries({
                queryKey: ["campaign-status", stopped.id],
            });
        },
    });
    const downloadReportMutation = useMutation({
        mutationFn: async (campaignId: string) =>
            (
                await api.get<Blob>(
                    `/campaigns/${encodeURIComponent(campaignId)}/report/export?format=md`,
                    { responseType: "blob" },
                )
            ).data,
        onSuccess: (blob, campaignId) => {
            const url = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = url;
            anchor.download = `campanha-${campaignId.slice(0, 8)}.md`;
            anchor.click();
            URL.revokeObjectURL(url);
        },
    });

    const isRefreshing =
        campaignsQuery.isFetching ||
        campaignQuery.isFetching ||
        statusQuery.isFetching;
    const isCreating = createCampaignMutation.isPending;

    const refreshCampaignScreen = useCallback(() => {
        void queryClient.invalidateQueries({ queryKey: ["campaigns"] });
        if (!campaignId) return;
        void queryClient.invalidateQueries({ queryKey: ["campaign", campaignId] });
        void queryClient.invalidateQueries({
            queryKey: ["campaign-status", campaignId],
        });
    }, [queryClient, campaignId]);

    // Após o /report, os lances ganham ai_explanation: propaga para o tabuleiro.
    const reportCampaign = reportQuery.data?.campaign;
    useEffect(() => {
        if (reportCampaign) {
            queryClient.setQueryData(["campaign", reportCampaign.id], reportCampaign);
        }
    }, [reportCampaign, queryClient]);

    const latestMove = campaign?.moves[campaign.moves.length - 1] || null;

    function createCampaign(values: CampaignFormValues) {
        setError("");
        setNotice("");
        // Alvo travado: não enviamos `origin`; o servidor usa o locked_target.
        createCampaignMutation.mutate({
            config: {
                authorized_by: values.authorizedBy,
                authorized_at: new Date().toISOString(),
            },
        });
    }

    function decideMove(moveNumber: number, decision: "approve" | "deny") {
        if (!campaign) return;
        setPendingAction(`${decision}-${moveNumber}`);
        setError("");
        setNotice("");
        decideMoveMutation.mutate(
            { campaignId: campaign.id, moveNumber, decision },
            {
                onSuccess: () =>
                    setNotice(
                        decision === "approve"
                            ? `Lance ${moveNumber} aprovado.`
                            : `Lance ${moveNumber} negado.`,
                    ),
                onSettled: () => setPendingAction(""),
            },
        );
    }

    function stopCampaign() {
        if (!campaign) return;
        if (
            !window.confirm(
                "Parar esta campanha agora? Os resultados obtidos serão preservados.",
            )
        ) {
            return;
        }
        setPendingAction("stop");
        setError("");
        stopCampaignMutation.mutate(campaign.id, {
            onSuccess: () => setNotice("Campanha interrompida."),
            onSettled: () => setPendingAction(""),
        });
    }

    function downloadReport() {
        if (!campaign) return;
        downloadReportMutation.mutate(campaign.id);
    }

    const liveLabel =
        webSocketState.status === "connected"
            ? "Ao vivo"
            : webSocketState.status === "polling"
                ? "Polling"
                : webSocketState.status === "error"
                    ? "Sem stream"
                    : "Conectando";
    const liveColor =
        webSocketState.status === "connected"
            ? "bg-emerald-400"
            : webSocketState.status === "error"
                ? "bg-rose-400"
                : "bg-amber-400";

    return (
        <div className="space-y-5">
            <PageHeader
                eyebrow="Agente autônomo"
                title="Campanha ao vivo"
                description="Os agentes jogam o pentest; o código arbitra. Acompanhe lance a lance."
                actions={
                    <>
                        {campaignIsActive && (
                            <span
                                role="status"
                                aria-live="polite"
                                title={webSocketState.message || undefined}
                                className="hidden items-center gap-2 rounded-full border border-border/60 bg-card/50 px-3 py-1.5 text-xs text-muted-foreground sm:flex"
                            >
                                <span className={`size-2 rounded-full ${liveColor}`} />
                                {liveLabel}
                            </span>
                        )}
                        {campaigns.length > 0 && (
                            <Select
                                value={campaignId || null}
                                onValueChange={(value) => {
                                    setSelectedId(value ?? "");
                                    setShowReport(false);
                                }}
                            >
                                <SelectTrigger
                                    aria-label="Selecionar campanha"
                                    className="h-9 w-44 max-w-44 rounded-xl text-xs"
                                >
                                    <SelectValue className="min-w-0 flex-1 truncate" />
                                </SelectTrigger>
                                <SelectContent>
                                    {campaigns.map((item) => (
                                        <SelectItem key={item.id} value={item.id}>
                                            {stateLabel(item.state)} ·{" "}
                                            {new Date(item.created_at).toLocaleDateString("pt-BR")}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                        <Button
                            aria-label="Atualizar"
                            variant="outline"
                            size="icon-sm"
                            className="rounded-xl border-border/60 bg-card/50"
                            disabled={isRefreshing}
                            onClick={refreshCampaignScreen}
                        >
                            <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
                        </Button>
                        <Button
                            size="sm"
                            className="rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                            onClick={() => setShowCreate((c) => !c)}
                        >
                            <Play />
                            Nova campanha
                        </Button>
                    </>
                }
            />

            <AnimatePresence>
                {(error || notice) && (
                    <motion.div
                        initial={{ opacity: 0, y: -8, height: 0 }}
                        animate={{ opacity: 1, y: 0, height: "auto" }}
                        exit={{ opacity: 0, y: -8, height: 0 }}
                        role={error ? "alert" : "status"}
                        className={`flex items-start gap-2 overflow-hidden rounded-2xl border px-4 py-3 text-sm ${
                            error
                                ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
                                : "border-emerald-500/25 bg-emerald-500/10 text-emerald-200"
                        }`}
                    >
                        {error ? (
                            <ShieldAlert className="mt-0.5 size-4 shrink-0" />
                        ) : (
                            <Check className="mt-0.5 size-4 shrink-0" />
                        )}
                        <span className="flex-1">{error || notice}</span>
                        <button
                            aria-label="Fechar mensagem"
                            onClick={() => {
                                setError("");
                                setNotice("");
                            }}
                        >
                            <X className="size-4 opacity-70 hover:opacity-100" />
                        </button>
                    </motion.div>
                )}
            </AnimatePresence>

            <AnimatePresence>
                {showCreate && (
                    <motion.div
                        key="create"
                        initial={{ opacity: 0, y: -10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                    >
                        {scopeQuery.isPending ? (
                            <Card className="border-border/60 bg-card/50">
                                <CardContent className="flex min-h-40 items-center justify-center text-muted-foreground">
                                    <LoaderCircle className="size-5 animate-spin" />
                                </CardContent>
                            </Card>
                        ) : (
                            <CampaignCreateForm
                                lockedTarget={lockedTarget}
                                isSubmitting={isCreating}
                                apiError={
                                    createCampaignMutation.error
                                        ? getApiErrorMessage(createCampaignMutation.error)
                                        : ""
                                }
                                scopeError={
                                    scopeQuery.error ? getApiErrorMessage(scopeQuery.error) : ""
                                }
                                onRetryScope={() => void scopeQuery.refetch()}
                                onSubmit={createCampaign}
                            />
                        )}
                    </motion.div>
                )}
            </AnimatePresence>

            {!campaign && !showCreate && (
                <EmptyState
                    loading={campaignsQuery.isPending}
                    hasError={campaignsQuery.isError || campaignQuery.isError}
                    errorMessage={
                        campaignsQuery.isError
                            ? getApiErrorMessage(campaignsQuery.error)
                            : campaignQuery.isError
                                ? getApiErrorMessage(campaignQuery.error)
                                : ""
                    }
                    empty={campaignsQuery.isSuccess && campaigns.length === 0}
                    onRetry={refreshCampaignScreen}
                    onCreate={() => setShowCreate(true)}
                />
            )}

            {campaign && (
                <>
                    {/* Deck: agentes + pontuação + progresso */}
                    <motion.div
                        variants={staggerContainer(0.08)}
                        initial="hidden"
                        animate="show"
                        className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]"
                    >
                        <motion.div variants={fadeUp}>
                            <Card className="h-full border-border/60 bg-card/50 backdrop-blur-sm">
                                <CardContent className="flex h-full flex-col p-5">
                                    <div className="flex items-center justify-between">
                                        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-primary">
                                            <Sparkles className="size-4" />
                                            Agentes em campo
                                        </p>
                                        <span className="rounded-full border border-border/60 bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground">
                                            {campaignIsActive ? "Operando" : "Standby"}
                                        </span>
                                    </div>
                                    <div className="mt-2 flex-1">
                                        <AgentsConstellation campaign={campaign} />
                                    </div>
                                    <CurrentFocus
                                        status={campaignStatus}
                                        active={campaignIsActive}
                                    />
                                </CardContent>
                            </Card>
                        </motion.div>

                        <motion.div variants={fadeUp} className="grid gap-3">
                            <ScorePanel campaign={campaign} reduce={Boolean(reduce)} />
                            <ProgressPanel
                                status={campaignStatus}
                                state={campaign.state}
                                elapsed={campaignStatus?.elapsed_s ?? 0}
                            />
                            <AgentRoster campaign={campaign} />
                        </motion.div>
                    </motion.div>

                    <motion.div variants={scaleIn} initial="hidden" animate="show">
                        <CampaignBoard
                            campaign={campaign}
                            latestMove={latestMove}
                            active={campaignIsActive}
                            pendingAction={pendingAction}
                            campaignError={
                                campaignQuery.error
                                    ? getApiErrorMessage(campaignQuery.error)
                                    : ""
                            }
                            actionError={
                                decideMoveMutation.error
                                    ? getApiErrorMessage(decideMoveMutation.error)
                                    : ""
                            }
                            onDecide={(moveNumber, decision) =>
                                void decideMove(moveNumber, decision)
                            }
                            isStopping={pendingAction === "stop"}
                            stopError={
                                stopCampaignMutation.error
                                    ? getApiErrorMessage(stopCampaignMutation.error)
                                    : ""
                            }
                            onStop={() => void stopCampaign()}
                            onDownloadReport={() => void downloadReport()}
                            isDownloadingReport={downloadReportMutation.isPending}
                            downloadError={
                                downloadReportMutation.error
                                    ? getApiErrorMessage(downloadReportMutation.error)
                                    : ""
                            }
                            canOpenReport={campaignIsTerminal}
                            onOpenReport={() => setShowReport(true)}
                        />
                    </motion.div>

                    <AnimatePresence>
                        {campaignIsTerminal && showReport && (
                            <motion.div
                                key="report"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 12 }}
                            >
                                {reportQuery.isError ? (
                                    <CampaignReportError
                                        message={getApiErrorMessage(reportQuery.error)}
                                        onRetry={() => void reportQuery.refetch()}
                                    />
                                ) : reportQuery.isPending || !reportQuery.data ? (
                                    <Card className="border-border/60 bg-card/50">
                                        <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-muted-foreground">
                                            <LoaderCircle className="size-5 animate-spin" />
                                            <p className="text-sm">
                                                Analisando a partida... (a IA escreve o resumo e
                                                comenta cada lance)
                                            </p>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    <CampaignReport
                                        report={reportQuery.data}
                                        onClose={() => setShowReport(false)}
                                    />
                                )}
                            </motion.div>
                        )}
                    </AnimatePresence>
                </>
            )}
        </div>
    );
}

/* --------------------------------------------------------------- Current focus */

function CurrentFocus({
    status,
    active,
}: {
    status: CampaignStatus | null;
    active: boolean;
}) {
    const current = status?.current_move ?? null;
    const text = !active
        ? "Partida encerrada."
        : current
            ? current.stage === "awaiting_approval"
                ? `Aguardando sua aprovação: ${current.title}`
                : `Jogando: ${current.title}`
            : "A IA está analisando o tabuleiro...";

    return (
        <div className="mt-3 flex items-center gap-2.5 rounded-xl border border-border/50 bg-background/40 px-3 py-2.5">
            <span className="relative flex size-2.5 shrink-0">
                {active && (
                    <motion.span
                        className="absolute inline-flex size-full rounded-full bg-primary opacity-60"
                        animate={{ scale: [1, 2], opacity: [0.6, 0] }}
                        transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                    />
                )}
                <span className="relative inline-flex size-2.5 rounded-full bg-primary" />
            </span>
            <p className="min-w-0 flex-1 truncate text-xs text-foreground">{text}</p>
            {current && (
                <span className="shrink-0 rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
                    {current.test_id}
                </span>
            )}
        </div>
    );
}

/* ---------------------------------------------------------------- Score panel */

function ScorePanel({
    campaign,
    reduce,
}: {
    campaign: Campaign;
    reduce: boolean;
}) {
    const score = campaign.score;
    const whitePct = score ? Math.min(100, Math.max(0, (score.eval_bar + 100) / 2)) : 50;
    const counts = score?.counts ?? {};

    return (
        <Card className="border-border/60 bg-card/50 backdrop-blur-sm">
            <CardContent className="flex items-stretch gap-4 p-5">
                {/* barra de avaliação vertical estilo Chess.com */}
                <div
                    className="relative w-3 shrink-0 overflow-hidden rounded-full bg-zinc-900 ring-1 ring-border/60"
                    title="Avaliação da partida"
                >
                    <motion.div
                        className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-zinc-200 to-white"
                        initial={{ height: "50%" }}
                        animate={{ height: `${whitePct}%` }}
                        transition={
                            reduce ? { duration: 0 } : { type: "spring", stiffness: 120, damping: 20 }
                        }
                    />
                </div>
                <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        <Gauge className="size-4" />
                        Avaliação da partida
                    </p>
                    <div className="mt-2 flex items-end gap-3">
                        <span className="text-4xl font-bold tabular-nums text-foreground">
                            {score ? score.accuracy.toFixed(1) : "—"}
                        </span>
                        <span className="pb-1 text-xs text-muted-foreground">Accuracy</span>
                        <span className="ml-auto pb-1 font-mono text-sm text-muted-foreground">
                            {score
                                ? `${score.eval_bar > 0 ? "+" : ""}${score.eval_bar.toFixed(0)}`
                                : "—"}
                        </span>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-1.5">
                        {(
                            [
                                ["blunder", "erros graves", "text-rose-300"],
                                ["mistake", "erros", "text-orange-300"],
                                ["inaccuracy", "imprecisões", "text-amber-300"],
                                ["best", "ótimos", "text-emerald-300"],
                            ] as const
                        ).map(([grade, label, color]) => (
                            <span
                                key={grade}
                                className="rounded-md border border-border/60 bg-muted/20 px-2 py-1 text-[10px] text-muted-foreground"
                            >
                                <span className={`font-semibold ${color}`}>
                                    {counts[grade] || 0}
                                </span>{" "}
                                {label}
                            </span>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

/* -------------------------------------------------------------- Progress panel */

function ProgressPanel({
    status,
    state,
    elapsed,
}: {
    status: CampaignStatus | null;
    state: Campaign["state"];
    elapsed: number;
}) {
    const progress = status?.progress ?? { played: 0, total: 0, percent: 0 };
    const pending = status?.pending_approvals.length ?? 0;

    return (
        <Card className="border-border/60 bg-card/50 backdrop-blur-sm">
            <CardContent className="p-5">
                <div className="flex items-center justify-between text-xs">
                    <p className="flex items-center gap-2 font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        <Radio className="size-4" />
                        Progresso
                    </p>
                    <span className="rounded-full border border-border/60 bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground">
                        {stateLabel(state)}
                    </span>
                </div>
                <div className="mt-3 flex items-center justify-between text-sm text-foreground">
                    <span>
                        Lance {progress.played} de {progress.total || "—"}
                    </span>
                    <span className="font-mono tabular-nums text-muted-foreground">
                        {durationLabel(elapsed)}
                    </span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted/40">
                    <motion.div
                        className="h-full rounded-full bg-gradient-to-r from-primary/70 to-primary"
                        initial={{ width: 0 }}
                        animate={{ width: `${progress.percent}%` }}
                        transition={{ type: "spring", stiffness: 120, damping: 20 }}
                    />
                </div>
                {pending > 0 && (
                    <p className="mt-3 flex items-center gap-1.5 text-xs text-amber-300">
                        <ShieldAlert className="size-3.5" />
                        {pending} {pending === 1 ? "lance aguarda" : "lances aguardam"} aprovação
                    </p>
                )}
            </CardContent>
        </Card>
    );
}

/* ----------------------------------------------------------------- Empty state */

function EmptyState({
    loading,
    hasError,
    errorMessage,
    empty,
    onRetry,
    onCreate,
}: {
    loading: boolean;
    hasError: boolean;
    errorMessage: string;
    empty: boolean;
    onRetry: () => void;
    onCreate: () => void;
}) {
    return (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
            <Card className="border-border/60 bg-card/40">
                <CardContent className="flex min-h-72 flex-col items-center justify-center gap-4 text-center">
                    <motion.span
                        animate={{ scale: [1, 1.08, 1] }}
                        transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
                        className="grid size-14 place-items-center rounded-2xl border border-primary/25 bg-primary/10 text-primary"
                    >
                        {hasError ? (
                            <ShieldAlert className="size-7" />
                        ) : loading ? (
                            <LoaderCircle className="size-7 animate-spin" />
                        ) : (
                            <Activity className="size-7" />
                        )}
                    </motion.span>
                    <div className="space-y-1">
                        <h2 className="text-lg font-semibold text-foreground">
                            {hasError
                                ? "Falha ao carregar"
                                : loading
                                    ? "Conectando à API..."
                                    : empty
                                        ? "Nenhuma campanha ainda"
                                        : "Carregando campanha..."}
                        </h2>
                        <p className="max-w-md text-sm text-muted-foreground">
                            {hasError
                                ? errorMessage
                                : "Inicie uma campanha para ver os agentes jogando o pentest ao vivo."}
                        </p>
                    </div>
                    <div className="flex gap-2">
                        {hasError && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={onRetry}
                                className="rounded-xl border-border/60"
                            >
                                <RefreshCw />
                                Tentar novamente
                            </Button>
                        )}
                        <Button
                            size="sm"
                            onClick={onCreate}
                            className="rounded-xl bg-primary text-primary-foreground hover:bg-primary/90"
                        >
                            <Play />
                            Iniciar campanha
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </motion.div>
    );
}
