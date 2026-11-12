import { useEffect, useRef } from "react";
import type { Dispatch, SetStateAction } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { z } from "zod";
import { api } from "@/lib/api";
import type {
  Campaign,
  CampaignState,
  CampaignStatus,
} from "./types";

const campaignStateSchema = z.enum([
  "created",
  "running",
  "waiting_approval",
  "stopped",
  "finished",
  "failed",
]);

const campaignScoreCountsSchema = z.partialRecord(
  z.enum([
    "brilliant",
    "great",
    "best",
    "good",
    "inaccuracy",
    "mistake",
    "miss",
    "blunder",
    "inconclusive",
  ]),
  z.number(),
);

const campaignScoreSchema = z.object({
  accuracy: z.number(),
  eval_bar: z.number(),
  counts: campaignScoreCountsSchema,
});

const campaignMoveSchema = z.object({
  move: z.number().int(),
  test_id: z.string(),
  title: z.string(),
  phase: z.enum(["opening", "middlegame", "endgame"]),
  profile: z.string(),
  approval: z.enum(["not_required", "pending", "approved", "denied"]),
  status: z.enum(["pass", "warning", "fail", "inconclusive"]).nullable(),
  severity: z.enum(["low", "medium", "high"]),
  grade: z
    .enum([
      "brilliant",
      "great",
      "best",
      "good",
      "inaccuracy",
      "mistake",
      "miss",
      "blunder",
      "inconclusive",
    ])
    .nullable(),
  confidence: z.enum(["low", "medium", "high"]).nullable(),
  evidence: z.array(
    z.object({
      id: z.string(),
      request: z.string(),
      response_status: z.number().nullable(),
      response_headers: z.record(z.string(), z.string()),
      response_sha256: z.string().nullable(),
      note: z.string().nullable(),
    }),
  ),
  explanation: z.string().nullable(),
  ai_explanation: z.string().nullable(),
  recommendation: z.string().nullable(),
  plan: z
    .object({
      hypothesis: z.string(),
      action: z.string(),
      expected_result: z.string(),
      stop_condition: z.string(),
      rationale: z.string().nullable(),
      source: z.enum(["ai", "rules"]),
    })
    .nullable(),
  verdict: z.enum(["confirmed", "discarded", "inconclusive"]).nullable(),
  impact: z.string().nullable(),
  started_at: z.string().nullable(),
  finished_at: z.string().nullable(),
});

const campaignEventSchema = z.object({
  seq: z.number().int().nonnegative(),
  campaign_id: z.string(),
  type: z.string(),
  at: z.string(),
  move: campaignMoveSchema.nullable(),
  data: z.record(z.string(), z.unknown()),
});

type CampaignEvent = z.infer<typeof campaignEventSchema>;
type ParsedCampaignScore = z.infer<typeof campaignScoreSchema>;

export type CampaignWebSocketStatus =
  | "idle"
  | "connecting"
  | "connected"
  | "reconnecting"
  | "polling"
  | "error"
  | "closed";

export interface CampaignWebSocketState {
  status: CampaignWebSocketStatus;
  message: string;
}

interface UseCampaignWebSocketOptions {
  campaignId: string;
  enabled: boolean;
  initialSeq: number;
  onStatusChange: Dispatch<SetStateAction<CampaignWebSocketState>>;
}

function createWebSocketUrl(campaignId: string, since: number) {
  const url = new URL(
    api.defaults.baseURL || "http://127.0.0.1:8000",
  );
  if (url.protocol === "https:") {
    url.protocol = "wss:";
  } else if (url.protocol === "http:") {
    url.protocol = "ws:";
  } else {
    throw new Error("A URL da API precisa usar HTTP ou HTTPS.");
  }

  const basePath = url.pathname.replace(/\/+$/, "");
  url.pathname = `${basePath}/campaigns/${encodeURIComponent(campaignId)}/ws`;
  url.search = "";
  url.searchParams.set("since", String(since));
  return url.toString();
}

function nextCampaignState(
  event: CampaignEvent,
  current: CampaignState,
  hasPendingApprovals?: boolean,
): CampaignState {
  if (event.type === "campaign_started" || event.type === "test_started") {
    return "running";
  }
  if (event.type === "approval_requested") return "waiting_approval";
  if (event.type === "approval_resolved") {
    if (hasPendingApprovals !== undefined) {
      return hasPendingApprovals ? "waiting_approval" : "running";
    }
    if (current === "waiting_approval") return "running";
  }
  if (event.type === "campaign_finished") {
    const state = campaignStateSchema.safeParse(event.data.state);
    if (state.success) return state.data;
  }
  return current;
}

function parseEventScore(
  event: CampaignEvent,
  currentScore: ParsedCampaignScore | null,
) {
  const fullScore = campaignScoreSchema.safeParse(event.data.score);
  if (fullScore.success) return fullScore.data;

  const eventCounts = campaignScoreCountsSchema.safeParse(event.data.score);
  const eventScore = campaignScoreSchema.safeParse({
    accuracy: event.data.accuracy,
    eval_bar: event.data.eval_bar,
    counts:
      (eventCounts.success ? eventCounts.data : null) ??
      currentScore?.counts ??
      {},
  });
  return eventScore.success ? eventScore.data : null;
}

function applyCampaignEvent(
  campaign: Campaign | undefined,
  event: CampaignEvent,
): Campaign | undefined {
  if (!campaign) return campaign;

  const moves = event.move
    ? [
        ...campaign.moves.filter((move) => move.move !== event.move?.move),
        event.move,
      ].sort((a, b) => a.move - b.move)
    : campaign.moves;
  const state = nextCampaignState(
    event,
    campaign.state,
    moves.some((move) => move.approval === "pending"),
  );
  const score =
    event.type === "score_updated"
      ? parseEventScore(event, campaign.score)
      : null;

  return {
    ...campaign,
    state,
    moves,
    score: score ?? campaign.score,
    finished_at:
      event.type === "campaign_finished" ? event.at : campaign.finished_at,
  };
}

function applyStatusEvent(
  status: CampaignStatus | undefined,
  campaign: Campaign | undefined,
  event: CampaignEvent,
): CampaignStatus | undefined {
  if (!status) return status;

  let pendingApprovals = status.pending_approvals;
  let progress = status.progress;

  if (event.move) {
    pendingApprovals = pendingApprovals.filter(
      (pending) => pending.move !== event.move?.move,
    );
    if (event.move.approval === "pending") {
      pendingApprovals = [
        ...pendingApprovals,
        {
          move: event.move.move,
          test_id: event.move.test_id,
          title: event.move.title,
          hypothesis: event.move.plan?.hypothesis ?? null,
        },
      ].sort((a, b) => a.move - b.move);
    }

    const previousMove = campaign?.moves.find(
      (move) => move.move === event.move?.move,
    );
    if (
      event.type === "finding_created" &&
      !previousMove?.finished_at &&
      progress.total > 0
    ) {
      const played = Math.min(progress.total, progress.played + 1);
      progress = {
        ...progress,
        played,
        percent: Math.round((played / progress.total) * 100),
      };
    }
  }

  const score =
    event.type === "score_updated"
      ? parseEventScore(event, status.score)
      : null;
  const nextState = nextCampaignState(
    event,
    status.state,
    pendingApprovals.length > 0,
  );
  const eventTime = Date.parse(event.at);
  const campaignStartTime = campaign?.created_at
    ? Date.parse(campaign.created_at)
    : Number.NaN;
  const elapsed =
    Number.isFinite(eventTime) && Number.isFinite(campaignStartTime)
      ? Math.max(
          status.elapsed_s,
          Math.floor((eventTime - campaignStartTime) / 1000),
        )
      : status.elapsed_s;

  return {
    ...status,
    state: nextState,
    last_seq: event.seq,
    pending_approvals: pendingApprovals,
    progress,
    score: score ?? status.score,
    elapsed_s: elapsed,
  };
}

export function useCampaignWebSocket({
  campaignId,
  enabled,
  initialSeq,
  onStatusChange,
}: UseCampaignWebSocketOptions) {
  const queryClient = useQueryClient();
  const initialSeqRef = useRef(initialSeq);

  useEffect(() => {
    initialSeqRef.current = initialSeq;
  }, [initialSeq]);

  useEffect(() => {
    if (!enabled || !campaignId) {
      onStatusChange({ status: "idle", message: "" });
      return;
    }

    let disposed = false;
    let usingPollingFallback = false;
    let attempts = 0;
    let lastSeq = initialSeqRef.current;
    let socket: WebSocket | null = null;
    let retryTimer: number | undefined;

    const setState = (
      status: CampaignWebSocketStatus,
      message = "",
    ) => onStatusChange({ status, message });

    const invalidateCampaign = () => {
      void queryClient.invalidateQueries({
        queryKey: ["campaign", campaignId],
      });
      void queryClient.invalidateQueries({
        queryKey: ["campaign-status", campaignId],
      });
    };

    const switchToPollingFallback = (message: string) => {
      if (disposed || usingPollingFallback) return;
      usingPollingFallback = true;
      setState("polling", message);
      socket?.close();
    };

    const connect = () => {
      if (disposed || usingPollingFallback) return;

      try {
        socket = new WebSocket(createWebSocketUrl(campaignId, lastSeq));
      } catch {
        switchToPollingFallback(
          "Não foi possível iniciar o WebSocket; usando polling.",
        );
        return;
      }

      socket.onopen = () => {
        if (!disposed) setState("connected");
      };

      socket.onmessage = (message) => {
        let payload: unknown;
        try {
          payload = JSON.parse(String(message.data));
        } catch {
          switchToPollingFallback(
            "A API enviou um evento inválido; usando polling.",
          );
          return;
        }

        const parsedEvent = campaignEventSchema.safeParse(payload);
        if (
          !parsedEvent.success ||
          parsedEvent.data.campaign_id !== campaignId
        ) {
          switchToPollingFallback(
            "A API enviou um evento inválido; usando polling.",
          );
          return;
        }

        const event = parsedEvent.data;
        if (event.seq <= lastSeq) return;

        lastSeq = event.seq;
        attempts = 0;
        const previousCampaign = queryClient.getQueryData<Campaign>([
          "campaign",
          campaignId,
        ]);
        queryClient.setQueryData<Campaign>(
          ["campaign", campaignId],
          (current) => applyCampaignEvent(current, event),
        );
        queryClient.setQueryData<CampaignStatus>(
          ["campaign-status", campaignId],
          (current) => applyStatusEvent(current, previousCampaign, event),
        );

        if (event.type === "campaign_finished") {
          invalidateCampaign();
        }
      };

      socket.onerror = () => {
        if (!disposed) {
          setState("reconnecting", "Conexão WebSocket instável.");
        }
      };

      socket.onclose = (event) => {
        if (disposed || usingPollingFallback) return;

        if (event.code === 1000) {
          setState("closed");
          invalidateCampaign();
          return;
        }
        if (event.code === 1008) {
          setState(
            "error",
            "Origem da tela não autorizada; confira CORS_ORIGINS na API.",
          );
          return;
        }
        if (event.code === 4404) {
          setState("error", "A API não encontrou esta campanha.");
          return;
        }
        if (event.code === 1013) {
          switchToPollingFallback("Servidor WebSocket ocupado; usando polling.");
          return;
        }

        attempts += 1;
        if (attempts > 5) {
          switchToPollingFallback(
            "WebSocket indisponível após várias tentativas; usando polling.",
          );
          return;
        }

        setState("reconnecting", "Reconectando ao WebSocket...");
        retryTimer = window.setTimeout(connect, attempts * 1000);
      };
    };

    setState("connecting");
    connect();

    return () => {
      disposed = true;
      if (retryTimer !== undefined) window.clearTimeout(retryTimer);
      socket?.close(1000, "Campaign view changed");
    };
  }, [campaignId, enabled, initialSeqRef, onStatusChange, queryClient]);
}
