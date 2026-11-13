export type CampaignState =
  | "created"
  | "running"
  | "waiting_approval"
  | "stopped"
  | "finished"
  | "failed";

export type MoveStatus = "pass" | "warning" | "fail" | "inconclusive";

export type MoveGrade =
  | "brilliant"
  | "great"
  | "best"
  | "good"
  | "inaccuracy"
  | "mistake"
  | "miss"
  | "blunder"
  | "inconclusive";

export interface MovePlan {
  hypothesis: string;
  action: string;
  expected_result: string;
  stop_condition: string;
  rationale: string | null;
  source: "ai" | "rules";
}

export interface Evidence {
  id: string;
  request: string;
  response_status: number | null;
  response_headers: Record<string, string>;
  response_sha256: string | null;
  note: string | null;
}

export interface CampaignMove {
  move: number;
  test_id: string;
  title: string;
  phase: "opening" | "middlegame" | "endgame";
  profile: string;
  approval: "not_required" | "pending" | "approved" | "denied";
  status: MoveStatus | null;
  severity: "low" | "medium" | "high";
  grade: MoveGrade | null;
  confidence: "low" | "medium" | "high" | null;
  evidence: Evidence[];
  explanation: string | null;
  ai_explanation: string | null;
  recommendation: string | null;
  plan: MovePlan | null;
  verdict: "confirmed" | "discarded" | "inconclusive" | null;
  impact: string | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface CampaignScore {
  accuracy: number;
  eval_bar: number;
  counts: Partial<Record<MoveGrade, number>>;
}

export interface Campaign {
  id: string;
  config: {
    origin: string;
    authorized_by: string;
    authorized_at: string;
    unattended?: boolean;
  };
  state: CampaignState;
  created_at: string;
  finished_at: string | null;
  score: CampaignScore | null;
  moves: CampaignMove[];
}

export interface CampaignStatus {
  id: string;
  state: CampaignState;
  origin: string;
  progress: { played: number; total: number; percent: number };
  pending_approvals: {
    move: number;
    test_id: string;
    title: string;
    hypothesis: string | null;
  }[];
  score: CampaignScore | null;
  last_seq: number;
  elapsed_s: number;
}

export interface Scope {
  authorized_targets: string[];
  local_only: boolean;
  allowed_methods: string[];
  allowed_profiles?: string[];
  blocked_profiles?: string[];
  limits: {
    max_requests_per_second: number;
    max_total_requests: number;
    request_timeout_s?: number;
  };
  preapproval?: {
    tests: string[];
    approved_by: string | null;
    valid_until: string | null;
    active: string[];
  };
}

export interface GameReview {
  executive_summary: string | null;
  key_moments: { move: number; summary: string }[];
  audit: {
    at: string;
    method: string;
    url: string;
    allowed: boolean;
    reason: string | null;
    status_code: number | null;
    actor: string;
  }[];
}

export interface TimelineEntry {
  at: string;
  kind:
    | "campaign"
    | "decision"
    | "approval_requested"
    | "approval"
    | "command"
    | "blocked"
    | "result"
    | "score"
    | "stop";
  move: number | null;
  summary: string;
  details: Record<string, unknown>;
}

export interface CreateCampaignBody {
  config: {
    origin: string;
    authorized_by: string;
    authorized_at: string;
  };
}
