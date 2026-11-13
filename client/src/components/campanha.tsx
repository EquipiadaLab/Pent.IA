import { api, getApiErrorMessage } from "@/lib/api";
import {
    useMutation,
    useQuery,
    useQueryClient,
} from "@tanstack/react-query";
import {
    Activity,
    AlertTriangle,
    Check,
    LoaderCircle,
    Play,
    RefreshCw,
    ShieldAlert,
    X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiErrorState } from "./campanha/api-error-state";
import { CampaignBoard } from "./campanha/campaign-board";
import {
    CampaignCreateForm,
    type CampaignFormValues,
} from "./campanha/campaign-create-form";
import {
    CampaignReport,
    CampaignReportError,
} from "./campanha/campaign-report";
import {
    ACTIVE_STATES,
    stateLabel,
} from "./campanha/helpers";
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
import { DashboardHeader } from "./dashboard.header";
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
    const visibleError = error;

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

    useEffect(() => {
        const handleCreate = () => setShowCreate(true);
        window.addEventListener("campaign:refresh", refreshCampaignScreen);
        window.addEventListener("campaign:create", handleCreate);
        return () => {
            window.removeEventListener("campaign:refresh", refreshCampaignScreen);
            window.removeEventListener("campaign:create", handleCreate);
        };
    }, [refreshCampaignScreen]);

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

    function decideMove(
        moveNumber: number,
        decision: "approve" | "deny",
    ) {
        if (!campaign) {
            return;
        }
        setPendingAction(`${decision}-${moveNumber}`);
        setError("");
        setNotice("");
        decideMoveMutation.mutate(
            {
                campaignId: campaign.id,
                moveNumber,
                decision,
            },
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

    return (
        <main className="mx-auto w-full max-w-[1500px] pb-10">
            <DashboardHeader
                title="Campanha em execução"
                description="Acompanhe a validação do escopo autorizado, lance a lance."
                actions={
                    <div className="flex flex-wrap items-center justify-end gap-2">
                        {campaignIsActive && (
                            <span
                                role="status"
                                aria-live="polite"
                                title={webSocketState.message || undefined}
                                className="hidden items-center gap-2 text-xs text-zinc-400 sm:flex"
                            >
                                <span
                                    className={`size-2 rounded-full ${webSocketState.status === "connected"
                                            ? "bg-emerald-400"
                                            : webSocketState.status === "error"
                                                ? "bg-rose-400"
                                                : "bg-amber-400"
                                        }`}
                                />
                                {webSocketState.status === "connected"
                                    ? "Atualizações ao vivo"
                                    : webSocketState.status === "polling"
                                        ? "Polling ativo"
                                        : webSocketState.status === "error"
                                            ? "WebSocket indisponível"
                                            : "Conectando ao vivo"}
                            </span>
                        )}
                        {campaigns.length > 0 && (
                            <Select
                                value={campaignId || null}
                                onValueChange={(value) => setSelectedId(value ?? "")}
                            >
                                <SelectTrigger
                                    aria-label="Selecionar campanha"
                                    className="h-9 w-48 max-w-48 rounded-lg text-xs"
                                >
                                    <SelectValue className="min-w-0 flex-1 truncate" />
                                </SelectTrigger>
                                <SelectContent>
                                    {campaigns.map((item) => (
                                        <SelectItem key={item.id} value={item.id}>
                                            {item.config.origin} · {stateLabel(item.state)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        )}
                        <Button
                            aria-label="Atualizar campanhas"
                            variant="outline"
                            size="icon-sm"
                            className="border-white/10 bg-white/[0.03] text-zinc-400 hover:bg-white/10 hover:text-white"
                            disabled={isRefreshing}
                            onClick={refreshCampaignScreen}
                        >
                            <RefreshCw className={isRefreshing ? "animate-spin" : ""} />
                        </Button>
                        <Button
                            size="sm"
                            className="bg-rose-600 text-white hover:bg-rose-500"
                            onClick={() => {
                                setShowCreate((current) => !current);
                                window.setTimeout(
                                    () =>
                                        document
                                            .getElementById("campaign-create")
                                            ?.scrollIntoView({ behavior: "smooth", block: "center" }),
                                    0,
                                );
                            }}
                        >
                            <Play />
                            Nova campanha
                        </Button>
                    </div>
                }
            />

            {campaignsQuery.isError && campaigns.length > 0 && (
                <div className="mt-4">
                    <ApiErrorState
                        compact
                        message={getApiErrorMessage(campaignsQuery.error)}
                        onRetry={() => void campaignsQuery.refetch()}
                    />
                </div>
            )}

            {(visibleError || notice) && (
                <div
                    role={visibleError ? "alert" : "status"}
                    className={`mt-4 flex items-start gap-2 rounded-xl border px-4 py-3 text-sm ${visibleError
                        ? "border-rose-500/30 bg-rose-500/10 text-rose-200"
                        : "border-emerald-500/25 bg-emerald-500/[0.08] text-emerald-200"
                        }`}
                >
                    {visibleError ? (
                        <ShieldAlert className="mt-0.5 size-4 shrink-0" />
                    ) : (
                        <Check className="mt-0.5 size-4 shrink-0" />
                    )}
                    <span>{visibleError || notice}</span>
                    <button
                        className="ml-auto text-current/70 hover:text-current"
                        aria-label="Fechar mensagem"
                        onClick={() => {
                            setError("");
                            setNotice("");
                        }}
                    >
                        <X className="size-4" />
                    </button>
                </div>
            )}

            {showCreate &&
                (scopeQuery.isPending ? (
                    <Card className="mt-5 border-white/10 bg-zinc-950/80">
                        <CardContent className="flex min-h-40 items-center justify-center text-zinc-500">
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
                ))}

            {!campaign && !showCreate && (
                <Card className="mt-5 border-white/10 bg-zinc-950/80">
                    <CardContent className="flex min-h-64 flex-col items-center justify-center gap-3 text-center">
                        {campaignsQuery.isError || campaignQuery.isError ? (
                            <AlertTriangle className="size-8 text-rose-400" />
                        ) : campaignsQuery.isPending ? (
                            <LoaderCircle className="size-7 animate-spin text-rose-400" />
                        ) : (
                            <Activity className="size-8 text-rose-400" />
                        )}
                        <h2 className="text-lg font-medium text-zinc-100">
                            {campaignsQuery.isError || campaignQuery.isError
                                ? "Falha ao carregar campanha"
                                : campaigns.length
                                    ? "Carregando campanha..."
                                    : campaignsQuery.isSuccess
                                        ? "Nenhuma campanha selecionada"
                                        : "Conectando à API..."}
                        </h2>
                        <p className="max-w-md text-sm text-zinc-500">
                            {campaignsQuery.isError
                                ? getApiErrorMessage(campaignsQuery.error)
                                : campaignQuery.isError
                                    ? getApiErrorMessage(campaignQuery.error)
                                    : campaigns.length
                                        ? "Sincronizando estado, progresso e lances com a API."
                                        : "Inicie uma campanha no ambiente local de treino para acompanhar o tabuleiro ao vivo."}
                        </p>
                        {(campaignsQuery.isError || campaignQuery.isError) && (
                            <Button
                                variant="outline"
                                size="sm"
                                onClick={refreshCampaignScreen}
                                className="border-white/10 bg-transparent text-zinc-300 hover:bg-white/5"
                            >
                                <RefreshCw />
                                Tentar novamente
                            </Button>
                        )}
                        {campaigns.length === 0 && (
                            <Button
                                className="mt-2 bg-rose-600 text-white hover:bg-rose-500"
                                onClick={() => setShowCreate(true)}
                            >
                                <Play />
                                Configurar campanha
                            </Button>
                        )}
                    </CardContent>
                </Card>
            )}

            {campaign && (
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
            )}

            {campaign && campaignIsTerminal && showReport && (
                <>
                    {reportQuery.isError ? (
                        <CampaignReportError
                            message={getApiErrorMessage(reportQuery.error)}
                            onRetry={() => void reportQuery.refetch()}
                        />
                    ) : reportQuery.isPending || !reportQuery.data ? (
                        <Card className="mt-3 border-white/10 bg-zinc-950/80">
                            <CardContent className="flex min-h-40 flex-col items-center justify-center gap-3 text-zinc-500">
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
                </>
            )}
        </main>
    );
}
