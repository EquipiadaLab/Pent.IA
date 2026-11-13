import { ACCENT, agentForMove } from "@/data/agents";
import axios from "axios";
import { api, getApiErrorMessage } from "@/lib/api";
import { fadeUp, scaleIn, staggerContainer } from "@/lib/motion";
import {
    useMutation,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";
import {
    Activity,
    ArrowRight,
    Check,
    Gauge,
    LoaderCircle,
    LockKeyhole,
    Play,
    Radio,
    RefreshCw,
    ShieldAlert,
    Sparkles,
    X,
    Zap,
} from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgentsField } from "./agents/agents-field";
import { CampaignBoard } from "./campanha/campaign-board";
import {
    CampaignCreateForm,
    type CampaignFormValues,
} from "./campanha/campaign-create-form";
import { CampaignCves, CampaignCvesError } from "./campanha/campaign-cves";
import {
    CampaignReport,
    CampaignReportError,
} from "./campanha/campaign-report";
import {
    ACTIVE_STATES,
    durationLabel,
    playApprovalNotification,
    stateLabel,
} from "./campanha/helpers";
import type {
    AgentsParticipationResponse,
    Campaign,
    CampaignMove,
    CampaignStatus,
    CreateCampaignBody,
    CvesResponse,
    GameReview, MoveGrade, Scope
} from "./campanha/types";
import {
    useCampaignWebSocket,
    type CampaignWebSocketState,
} from "./campanha/use-campaign-websocket";
import { PageHeader } from "./layout/page-header";
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
    const [showCves, setShowCves] = useState(false);
    // UX: a Revisão/CVEs aparecem abaixo do tabuleiro, fora da tela. Ao clicar,
    // rolamos até a seção (o nonce garante a rolagem mesmo se já estiver aberta).
    const reportSectionRef = useRef<HTMLDivElement>(null);
    const cvesSectionRef = useRef<HTMLDivElement>(null);
    const [scrollTarget, setScrollTarget] = useState<{
        section: "report" | "cves";
        nonce: number;
    } | null>(null);
    useEffect(() => {
        if (!scrollTarget) return;
        const el =
            scrollTarget.section === "report"
                ? reportSectionRef.current
                : cvesSectionRef.current;
        if (!el) return;
        const id = window.requestAnimationFrame(() => {
            el.scrollIntoView({
                behavior: reduce ? "auto" : "smooth",
                block: "start",
            });
            el.focus({ preventScroll: true });
        });
        return () => window.cancelAnimationFrame(id);
    }, [scrollTarget, reduce]);
    // Piloto automático: aprova sozinho os lances menos graves e só segura os
    // de severidade "high" (os mais graves) para decisão humana.
    const [autoPilot, setAutoPilot] = useState(false);
    const autoApprovedRef = useRef<Set<string>>(new Set());
    const lastReconcileRef = useRef(0);
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
        // Mesmo com o WebSocket conectado mantemos um polling lento como rede de
        // segurança: se um evento (ex.: approval_requested) se perder numa rajada
        // rápida, o estado completo da campanha se reconcilia sozinho.
        refetchInterval: (query) => {
            const data = query.state.data;
            if (!data || !ACTIVE_STATES.includes(data.state)) return false;
            return webSocketState.status === "connected" ? 4000 : 1500;
        },
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
        refetchInterval: (query) => {
            const data = query.state.data;
            if (!data || !ACTIVE_STATES.includes(data.state)) return false;
            return webSocketState.status === "connected" ? 4000 : 1500;
        },
    });
    const campaign = campaignQuery.data || null;
    const campaignStatus = statusQuery.data || null;
    const campaignIsActive = Boolean(
        campaign && ACTIVE_STATES.includes(campaign.state),
    );
    const campaignIsTerminal = Boolean(
        campaign && !ACTIVE_STATES.includes(campaign.state),
    );

    // Revisão da Penteada (item 7): a primeira chamada ao /report pode levar ~20-30 s (IA).
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

    // Participação agregada por agente (seção 0B). Atualiza enquanto a campanha
    // está ativa para alimentar o card "Agentes em campo".
    const agentsQuery = useQuery({
        queryKey: ["campaign-agents", campaignId],
        queryFn: async () =>
            (
                await api.get<AgentsParticipationResponse>(
                    `/campaigns/${encodeURIComponent(campaignId)}/agents`,
                )
            ).data,
        enabled: Boolean(campaignId),
        refetchInterval: (query) =>
            query.state.data && campaignIsActive ? 4000 : false,
    });
    const agentsParticipation = agentsQuery.data?.agents ?? null;

    // CVEs/exploits conhecidos (seção 0C). Consulta externa à NVD — lenta na
    // primeira chamada; só dispara quando o usuário clica em "Gerar CVEs".
    const cvesQuery = useQuery({
        queryKey: ["campaign-cves", campaignId],
        queryFn: async () =>
            (
                await api.get<CvesResponse>(
                    `/campaigns/${encodeURIComponent(campaignId)}/cves`,
                    { timeout: 60_000 },
                )
            ).data,
        enabled: Boolean(campaignId) && campaignIsTerminal && showCves,
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
            actor = "operator",
        }: {
            campaignId: string;
            moveNumber: number;
            decision: "approve" | "deny";
            actor?: string;
        }) =>
            api.post(
                `/campaigns/${encodeURIComponent(campaignId)}/moves/${moveNumber}/${decision}?actor=${encodeURIComponent(actor)}`,
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

    // Após o /report, os lances ganham ai_explanation: propaga para os lances.
    const reportCampaign = reportQuery.data?.campaign;
    useEffect(() => {
        if (reportCampaign) {
            queryClient.setQueryData(["campaign", reportCampaign.id], reportCampaign);
        }
    }, [reportCampaign, queryClient]);

    // Piloto automático: aprova automaticamente os lances pendentes que NÃO são
    // de severidade "high". Os mais graves continuam aguardando o humano.
    useEffect(() => {
        if (!autoPilot || !campaign || !campaignIsActive) return;
        const seen = autoApprovedRef.current;
        for (const move of campaign.moves) {
            if (move.approval !== "pending") continue;
            if (move.severity === "high") continue; // os mais graves pedem humano
            const key = `${campaign.id}:${move.move}`;
            if (seen.has(key)) continue;
            seen.add(key);
            decideMoveMutation.mutate(
                {
                    campaignId: campaign.id,
                    moveNumber: move.move,
                    decision: "approve",
                    actor: "piloto-automatico",
                },
                {
                    // 409 = o servidor já avançou o lance; ignoramos em silêncio.
                    onError: () => undefined,
                },
            );
        }
    }, [autoPilot, campaign, campaignIsActive, decideMoveMutation]);

    // Ao trocar de campanha, zera o controle de lances já auto-aprovados.
    useEffect(() => {
        autoApprovedRef.current = new Set();
    }, [campaignId]);

    // Rede de segurança contra dessincronização: se o /status aponta que há um
    // lance aguardando aprovação mas ele ainda não apareceu em campaign.moves
    // (um evento se perdeu numa rajada rápida), força um refetch dos lances.
    useEffect(() => {
        if (!campaign || !campaignStatus || !campaignIsActive) return;
        const pendingNums = new Set(
            campaign.moves
                .filter((m) => m.approval === "pending")
                .map((m) => m.move),
        );
        const statusPending = campaignStatus.pending_approvals ?? [];
        const awaiting =
            campaignStatus.current_move?.stage === "awaiting_approval" ||
            statusPending.length > 0;
        const desync =
            statusPending.some((p) => !pendingNums.has(p.move)) ||
            (awaiting && pendingNums.size === 0);
        if (!desync) return;
        const now = Date.now();
        if (now - lastReconcileRef.current < 1500) return;
        lastReconcileRef.current = now;
        void queryClient.invalidateQueries({
            queryKey: ["campaign", campaignId],
        });
    }, [campaign, campaignStatus, campaignIsActive, campaignId, queryClient]);

    const latestMove = campaign?.moves[campaign.moves.length - 1] || null;
    const pendingHighCount =
        campaign?.moves.filter(
            (m) => m.approval === "pending" && m.severity === "high",
        ).length ?? 0;
    // Lances que REALMENTE precisam de um clique humano: com o piloto automático
    // ligado, só os de severidade alta; sem ele, todos os pendentes.
    const humanPendingMoves = campaign
        ? campaign.moves
              .filter(
                  (m) =>
                      m.approval === "pending" &&
                      (!autoPilot || m.severity === "high"),
              )
              .sort((a, b) => a.move - b.move)
        : [];
    // 409 ("lance X nao esta aguardando aprovacao") é benigno: o servidor já
    // avançou aquele lance. Não mostramos como erro.
    const decideErrorRaw = decideMoveMutation.error;
    const decideError =
        decideErrorRaw &&
        !(
            axios.isAxiosError(decideErrorRaw) &&
            decideErrorRaw.response?.status === 409
        )
            ? getApiErrorMessage(decideErrorRaw)
            : "";

    function createCampaign(values: CampaignFormValues) {
        setError("");
        setNotice("");
        // Alvo travado: não enviamos `origin`; o servidor usa o locked_target.
        // O limite de lances agora é imposto pelo servidor (config.max_moves).
        createCampaignMutation.mutate({
            config: {
                authorized_by: values.authorizedBy,
                authorized_at: new Date().toISOString(),
                max_moves: values.moveLimit ?? null,
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
                onError: (mutationError) => {
                    // 409 = o servidor já avançou esse lance. Resincroniza em vez
                    // de assustar o usuário com um erro.
                    if (
                        axios.isAxiosError(mutationError) &&
                        mutationError.response?.status === 409
                    ) {
                        setNotice(`Lance ${moveNumber} já havia sido resolvido.`);
                        void queryClient.invalidateQueries({
                            queryKey: ["campaign", campaign.id],
                        });
                    }
                },
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
                        {campaignIsActive && (
                            <Button
                                size="sm"
                                variant="outline"
                                aria-pressed={autoPilot}
                                onClick={() => setAutoPilot((value) => !value)}
                                title="Aprova sozinho os lances menos graves; os de severidade alta continuam pedindo sua autorização."
                                className={`rounded-xl ${
                                    autoPilot
                                        ? "border-emerald-400/40 bg-emerald-400/10 text-emerald-200 hover:bg-emerald-400/15"
                                        : "border-border/60 bg-card/50"
                                }`}
                            >
                                <Zap
                                    className={autoPilot ? "fill-emerald-300/40" : ""}
                                />
                                Piloto auto
                                <span className="text-[10px] opacity-70">
                                    {autoPilot ? "ON" : "OFF"}
                                </span>
                            </Button>
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
                        className={`flex items-start gap-2 overflow-hidden rounded-2xl border px-4 py-3 text-sm ${error
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
                {autoPilot && campaignIsActive && (
                    <motion.div
                        key="autopilot-banner"
                        initial={{ opacity: 0, y: -8, height: 0 }}
                        animate={{ opacity: 1, y: 0, height: "auto" }}
                        exit={{ opacity: 0, y: -8, height: 0 }}
                        role="status"
                        className="flex items-start gap-2 overflow-hidden rounded-2xl border border-emerald-400/25 bg-emerald-400/[0.07] px-4 py-3 text-sm text-emerald-100"
                    >
                        <Zap className="mt-0.5 size-4 shrink-0 fill-emerald-300/40 text-emerald-300" />
                        <span className="flex-1">
                            Piloto automático ligado: os lances de severidade baixa e
                            média são aprovados sozinhos.{" "}
                            {pendingHighCount > 0 ? (
                                <strong className="font-semibold text-emerald-50">
                                    {pendingHighCount}{" "}
                                    {pendingHighCount === 1
                                        ? "lance grave aguarda"
                                        : "lances graves aguardam"}{" "}
                                    sua autorização.
                                </strong>
                            ) : (
                                "Os de severidade alta ainda pedem sua autorização."
                            )}
                        </span>
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
                                    <div className="mt-3 flex-1">
                                        <AgentsField
                                            campaign={campaign}
                                            participation={agentsParticipation}
                                        />
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
                                campaign={campaign}
                                status={campaignStatus}
                                state={campaign.state}
                                active={campaignIsActive}
                                elapsed={campaignStatus?.elapsed_s ?? 0}
                                moveLimit={campaign.config.max_moves ?? undefined}
                                pendingMoves={humanPendingMoves}
                                pendingAction={pendingAction}
                                actionError={decideError}
                                onDecide={(moveNumber, decision) =>
                                    void decideMove(moveNumber, decision)
                                }
                            />
                        </motion.div>
                    </motion.div>

                    <motion.div variants={scaleIn} initial="hidden" animate="show">
                        <CampaignBoard
                            campaign={campaign}
                            latestMove={latestMove}
                            active={campaignIsActive}
                            campaignError={
                                campaignQuery.error
                                    ? getApiErrorMessage(campaignQuery.error)
                                    : ""
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
                            onOpenReport={() => {
                                setShowReport(true);
                                setScrollTarget({ section: "report", nonce: Date.now() });
                            }}
                            canGenerateCves={campaignIsTerminal}
                            isGeneratingCves={showCves && cvesQuery.isFetching}
                            onGenerateCves={() => {
                                setShowCves(true);
                                setScrollTarget({ section: "cves", nonce: Date.now() });
                            }}
                        />
                    </motion.div>

                    <AnimatePresence>
                        {campaignIsTerminal && showReport && (
                            <motion.div
                                key="report"
                                ref={reportSectionRef}
                                tabIndex={-1}
                                aria-live="polite"
                                className="scroll-mt-6 outline-none"
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
                                                Analisando a penteada... (a IA escreve o resumo e
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

                    <AnimatePresence>
                        {campaignIsTerminal && showCves && (
                            <motion.div
                                key="cves"
                                ref={cvesSectionRef}
                                tabIndex={-1}
                                aria-live="polite"
                                className="scroll-mt-6 outline-none"
                                initial={{ opacity: 0, y: 12 }}
                                animate={{ opacity: 1, y: 0 }}
                                exit={{ opacity: 0, y: 12 }}
                            >
                                {cvesQuery.isError ? (
                                    <CampaignCvesError
                                        message={getApiErrorMessage(cvesQuery.error)}
                                        onRetry={() => void cvesQuery.refetch()}
                                    />
                                ) : cvesQuery.isPending || !cvesQuery.data ? (
                                    <Card className="border-border/60 bg-card/50">
                                        <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-muted-foreground">
                                            <LoaderCircle className="size-5 animate-spin" />
                                            <p className="text-sm">
                                                Consultando base de vulnerabilidades (NVD)...
                                            </p>
                                        </CardContent>
                                    </Card>
                                ) : (
                                    <CampaignCves
                                        data={cvesQuery.data}
                                        onClose={() => setShowCves(false)}
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
        ? "Penteada encerrada."
        : current
            ? current.stage === "awaiting_approval"
                ? `Aguardando sua aprovação: ${current.title}`
                : `Jogando: ${current.title}`
            : "A IA está passando o pente no alvo...";

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

const GRADE_META: {
    grade: MoveGrade;
    label: string;
    bar: string;
    text: string;
}[] = [
        { grade: "brilliant", label: "Brilhante", bar: "bg-cyan-400", text: "text-cyan-300" },
        { grade: "great", label: "Ótimo", bar: "bg-blue-400", text: "text-blue-300" },
        { grade: "best", label: "Melhor lance", bar: "bg-emerald-400", text: "text-emerald-300" },
        { grade: "good", label: "Bom", bar: "bg-emerald-300", text: "text-emerald-200" },
        { grade: "inaccuracy", label: "Imprecisão", bar: "bg-amber-400", text: "text-amber-300" },
        { grade: "mistake", label: "Erro", bar: "bg-orange-400", text: "text-orange-300" },
        { grade: "blunder", label: "Erro grave", bar: "bg-rose-500", text: "text-rose-300" },
        { grade: "miss", label: "Não executado", bar: "bg-zinc-500", text: "text-zinc-400" },
        { grade: "inconclusive", label: "Inconclusivo", bar: "bg-zinc-600", text: "text-zinc-400" },
    ];

function ScorePanel({
    campaign,
    reduce,
}: {
    campaign: Campaign;
    reduce: boolean;
}) {
    const score = campaign.score;
    const counts = score?.counts ?? {};
    const present = GRADE_META.filter((meta) => (counts[meta.grade] || 0) > 0);
    const totalGraded = present.reduce(
        (sum, meta) => sum + (counts[meta.grade] || 0),
        0,
    );
    const evalLabel = !score
        ? "Sem lances avaliados"
        : score.eval_bar >= 40
            ? "Alvo sólido"
            : score.eval_bar >= 0
                ? "Equilibrado"
                : score.eval_bar >= -40
                    ? "Alvo frágil"
                    : "Alvo muito frágil";

    return (
        <Card className="h-full border-border/60 bg-card/50 backdrop-blur-sm">
            <CardContent className="flex h-full items-stretch gap-4 p-5">

                <div className="flex min-w-0 flex-1 flex-col">
                    <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        <Gauge className="size-4" />
                        Avaliação da penteada
                    </p>
                    <div className="mt-2 flex items-end gap-3">
                        <span className="text-4xl font-bold tabular-nums text-foreground">
                            {score ? score.accuracy.toFixed(1) : "—"}
                        </span>
                        <span className="pb-1 text-xs text-muted-foreground">Accuracy</span>
                        <span className="ml-auto flex flex-col items-end pb-0.5">
                            <span className="font-mono text-sm text-muted-foreground">
                                {score
                                    ? `${score.eval_bar > 0 ? "+" : ""}${score.eval_bar.toFixed(0)}`
                                    : "—"}
                            </span>
                            <span className="text-[10px] text-muted-foreground/80">
                                {evalLabel}
                            </span>
                        </span>
                    </div>

                    {/* distribuição dos lances estilo "placar" */}
                    <div className="mt-4">
                        <div className="flex items-center justify-between text-[10px] uppercase tracking-wider text-muted-foreground">
                            <span>Distribuição dos lances</span>
                            <span className="tabular-nums">
                                {totalGraded} avaliado{totalGraded === 1 ? "" : "s"}
                            </span>
                        </div>
                        <div className="mt-1.5 flex h-2.5 overflow-hidden rounded-full bg-muted/40">
                            {present.map((meta) => {
                                const value = counts[meta.grade] || 0;
                                const pct = totalGraded ? (value / totalGraded) * 100 : 0;
                                return (
                                    <motion.div
                                        key={meta.grade}
                                        className={meta.bar}
                                        title={`${meta.label}: ${value}`}
                                        initial={{ width: 0 }}
                                        animate={{ width: `${pct}%` }}
                                        transition={
                                            reduce
                                                ? { duration: 0 }
                                                : { type: "spring", stiffness: 120, damping: 22 }
                                        }
                                    />
                                );
                            })}
                        </div>
                    </div>

                    <div className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1.5">
                        {(present.length > 0
                            ? present
                            : GRADE_META.filter((m) =>
                                ["best", "inaccuracy", "mistake", "blunder"].includes(
                                    m.grade,
                                ),
                            )
                        ).map((meta) => (
                            <div
                                key={meta.grade}
                                className="flex items-center gap-1.5 text-[11px] text-muted-foreground"
                            >
                                <span className={`size-2 shrink-0 rounded-full ${meta.bar}`} />
                                <span className={`font-semibold tabular-nums ${meta.text}`}>
                                    {counts[meta.grade] || 0}
                                </span>
                                <span className="truncate">{meta.label}</span>
                            </div>
                        ))}
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

/* -------------------------------------------------------------- Progress panel */

function ProgressPanel({
    campaign,
    status,
    state,
    active,
    elapsed,
    moveLimit,
    pendingMoves,
    pendingAction,
    actionError,
    onDecide,
}: {
    campaign: Campaign;
    status: CampaignStatus | null;
    state: Campaign["state"];
    active: boolean;
    elapsed: number;
    moveLimit?: number;
    pendingMoves: CampaignMove[];
    pendingAction: string;
    actionError: string;
    onDecide: (moveNumber: number, decision: "approve" | "deny") => void;
}) {
    const rawProgress = status?.progress ?? { played: 0, total: 0, percent: 0 };
    // Com limite de lances, a barra passa a refletir o alvo escolhido.
    const progress = moveLimit
        ? {
              played: rawProgress.played,
              total: moveLimit,
              percent: Math.min(
                  100,
                  Math.round((rawProgress.played / moveLimit) * 100),
              ),
          }
        : rawProgress;

    return (
        <Card className="border-border/60 bg-card/50 backdrop-blur-sm">
            <CardContent className="p-5">
                <div className="flex items-center justify-between text-xs">
                    <p className="flex items-center gap-2 font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                        <Radio className="size-4" />
                        Progresso
                    </p>
                    <span className="flex items-center gap-1.5">
                        {moveLimit && (
                            <span className="rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 text-[10px] text-primary">
                                limite {moveLimit}
                            </span>
                        )}
                        <span className="rounded-full border border-border/60 bg-muted/30 px-2 py-0.5 text-[10px] text-muted-foreground">
                            {stateLabel(state)}
                        </span>
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
                <ApprovalPrompt
                    pendingMoves={pendingMoves}
                    pendingAction={pendingAction}
                    actionError={actionError}
                    onDecide={onDecide}
                />

                <LiveAgent campaign={campaign} status={status} active={active} />
            </CardContent>
        </Card>
    );
}

/* ---------------------------------------------------------- approval prompt */

function ApprovalPrompt({
    pendingMoves,
    pendingAction,
    actionError,
    onDecide,
}: {
    pendingMoves: CampaignMove[];
    pendingAction: string;
    actionError: string;
    onDecide: (moveNumber: number, decision: "approve" | "deny") => void;
}) {
    const head = pendingMoves[0] ?? null;
    const headNumber = head?.move ?? null;
    const queued = Math.max(0, pendingMoves.length - 1);
    const notified = useRef<number | null>(null);

    useEffect(() => {
        if (headNumber === null) {
            notified.current = null;
            return;
        }
        if (notified.current === headNumber) return;
        notified.current = headNumber;
        playApprovalNotification();
    }, [headNumber]);

    return (
        <AnimatePresence initial={false}>
            {head && (
                <motion.div
                    key="approval"
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: "auto" }}
                    exit={{ opacity: 0, height: 0 }}
                    className="overflow-hidden"
                >
                    <div className="mt-4 rounded-xl border border-amber-400/30 bg-amber-400/[0.06] p-3">
                        <div className="flex items-center justify-between gap-2">
                            <p className="flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-amber-300">
                                <LockKeyhole className="size-3.5" />
                                Precisa da sua autorização
                            </p>
                            {queued > 0 && (
                                <span className="rounded-full border border-amber-400/30 bg-amber-400/10 px-1.5 py-0.5 text-[10px] text-amber-200">
                                    +{queued} na fila
                                </span>
                            )}
                        </div>
                        <div className="mt-2 flex items-center justify-between gap-2">
                            <span className="truncate text-sm font-semibold text-foreground">
                                {head.title}
                            </span>
                            <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                                #{String(head.move).padStart(2, "0")} · {head.test_id}
                            </span>
                        </div>
                        {head.plan?.hypothesis && (
                            <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                                {head.plan.hypothesis}
                            </p>
                        )}
                        <div className="mt-3 grid grid-cols-2 gap-2">
                            <Button
                                variant="outline"
                                size="sm"
                                disabled={Boolean(pendingAction)}
                                onClick={() => onDecide(head.move, "deny")}
                                className="border-border/60 bg-transparent text-foreground/80 hover:bg-foreground/5"
                            >
                                {pendingAction === `deny-${head.move}` ? (
                                    <LoaderCircle className="animate-spin" />
                                ) : (
                                    <X />
                                )}
                                Negar
                            </Button>
                            <Button
                                size="sm"
                                disabled={Boolean(pendingAction)}
                                onClick={() => onDecide(head.move, "approve")}
                                className="bg-primary text-primary-foreground hover:bg-primary/90"
                            >
                                {pendingAction === `approve-${head.move}` ? (
                                    <LoaderCircle className="animate-spin" />
                                ) : (
                                    <ArrowRight />
                                )}
                                Aprovar
                            </Button>
                        </div>
                        {actionError && (
                            <p role="alert" className="mt-2 text-[11px] text-rose-300">
                                {actionError}
                            </p>
                        )}
                    </div>
                </motion.div>
            )}
        </AnimatePresence>
    );
}

/* ------------------------------------------------------------- live agent */

function LiveAgent({
    campaign,
    status,
    active,
}: {
    campaign: Campaign;
    status: CampaignStatus | null;
    active: boolean;
}) {
    const current = status?.current_move ?? null;
    const currentMove = current
        ? campaign.moves.find((m) => m.move === current.move) ?? null
        : null;
    const agent = currentMove ? agentForMove(currentMove) : null;
    const accent = agent ? ACCENT[agent.accent] : null;
    const Icon = agent?.icon;

    const doingText = !active
        ? "Penteada encerrada — nenhum agente ativo."
        : current
            ? current.stage === "awaiting_approval"
                ? `Aguardando aprovação para: ${current.title}`
                : currentMove?.plan?.action || `Jogando: ${current.title}`
            : "Passando o pente antes do próximo lance...";

    return (
        <div className="mt-4 border-t border-border/50 pt-3">
            <p className="mb-2 flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                <span className="relative flex size-2">
                    {active && (
                        <motion.span
                            className="absolute inline-flex size-full rounded-full bg-emerald-400/70"
                            animate={{ scale: [1, 2.2], opacity: [0.6, 0] }}
                            transition={{ duration: 1.5, repeat: Infinity, ease: "easeOut" }}
                        />
                    )}
                    <span
                        className={`relative inline-flex size-2 rounded-full ${active ? "bg-emerald-400" : "bg-muted-foreground/40"
                            }`}
                    />
                </span>
                Agente ao vivo
            </p>

            <div
                className={`flex items-start gap-2.5 rounded-xl border p-2.5 ${agent && active && accent
                    ? `${accent.border} bg-background/40`
                    : "border-border/50 bg-background/30"
                    }`}
            >
                <span
                    className={`grid size-9 shrink-0 place-items-center rounded-lg border ${agent && active && accent
                        ? `${accent.border} ${accent.soft}`
                        : "border-border/60 bg-muted/30"
                        }`}
                >
                    {Icon ? (
                        <Icon
                            className={`size-[18px] ${active && accent ? accent.text : "text-muted-foreground"
                                }`}
                        />
                    ) : (
                        <Activity className="size-[18px] text-muted-foreground" />
                    )}
                </span>
                <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-1.5">
                        <span className="truncate text-sm font-semibold text-foreground">
                            {agent && active ? agent.name : "—"}
                        </span>
                        {current && active && (
                            <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                                {current.test_id}
                            </span>
                        )}
                    </div>
                    <p className="mt-0.5 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
                        {doingText}
                    </p>
                </div>
            </div>
        </div>
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
