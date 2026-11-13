export type CampaignState =
  | "created"
  | "running"
  | "waiting_approval"
  | "stopped"
  | "finished"
  | "failed";

export type MoveStatus = "pass" | "warning" | "fail" | "inconclusive";

export type Profile = "passive" | "active_light" | "intrusive";

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

export type Verdict = "confirmed" | "discarded" | "inconclusive";

export interface MovePlan {
  hypothesis: string;
  action: string;
  expected_result: string;
  stop_condition: string;
  rationale: string | null;
  source: "ai" | "rules";
  planned_at?: string | null;
}

export interface Evidence {
  id: string;
  request: string;
  response_status: number | null;
  response_headers: Record<string, string>;
  response_sha256: string | null;
  note: string | null;
}

export interface MoveReview {
  verdict: "approved" | "rejected";
  issues: string[];
}

export interface CampaignMove {
  move: number;
  test_id: string;
  title: string;
  phase: "opening" | "middlegame" | "endgame";
  profile: string;
  wstg: string | null;
  owasp_top10: string | null;
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
  verdict: Verdict | null;
  impact: string | null;
  reproduce: string[];
  ai_review: MoveReview | null;
  recommended_by: string | null;
  attack_tactic_id: string | null;
  attack_tactic_name: string | null;
  attack_technique_id: string | null;
  attack_technique_name: string | null;
  attack_url: string | null;
  exploitation_scenario?: string | null;
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
    only_tests?: string[] | null;
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
  unattended?: boolean;
  progress: { played: number; total: number; percent: number };
  current_move?: {
    move: number;
    test_id: string;
    title: string;
    stage: "awaiting_approval" | "running";
  } | null;
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
  locked_target: string | null;
  authorized_targets: string[];
  accepts_any_target: boolean;
  default_target: string | null;
  blocks_private_targets: boolean;
  allowed_methods: string[];
  allowed_profiles?: Profile[];
  blocked_profiles?: Profile[];
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

export interface CatalogTest {
  test_id: string;
  title: string;
  phase: "opening" | "middlegame" | "endgame";
  profile: Profile;
  severity: "low" | "medium" | "high";
  wstg: string;
  owasp_top10: string;
  needs_approval: boolean;
  hypothesis: string;
  expected: string;
  impact: string;
}

export interface AuditEntry {
  campaign_id?: string;
  at: string;
  method: string;
  url: string;
  allowed: boolean;
  reason: string | null;
  status_code: number | null;
  response_sha256?: string | null;
  actor: string;
}

export interface ExecutiveSummary {
  headline: string;
  risk_level: "critico" | "alto" | "medio" | "baixo";
  plain_language: string;
  top_risks: { move: number; title: string; why: string }[];
  next_steps: string[];
  source: "ai" | "rules";
}

export interface Comparison {
  previous_campaign_id: string;
  previous_accuracy: number | null;
  accuracy_delta: number | null;
  fixed: string[];
  new: string[];
  still_failing: string[];
}

export interface GameReview {
  campaign?: Campaign;
  executive_summary: string | null;
  key_moments: { move: number; summary: string }[];
  audit: AuditEntry[];
  summary?: ExecutiveSummary | null;
  comparison?: Comparison | null;
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

export interface AgentParticipation {
  agent: string;
  tactic_id: string | null;
  tactic_name: string | null;
  moves_recommended: number;
  moves_approved: number;
  moves_denied: number;
  findings: number;
  techniques_used: string[];
}

export interface AgentsParticipationResponse {
  campaign_id: string;
  agents: AgentParticipation[];
}

export interface CveExploit {
  url: string;
  source: string | null;
}

export interface CveItem {
  cve_id: string;
  description: string | null;
  cvss_score: number | null;
  cvss_severity: string | null;
  cvss_vector: string | null;
  cwe_ids: string[];
  published: string | null;
  nvd_url: string | null;
  exploits: CveExploit[];
}

export interface CveMatch {
  search_term: string;
  move: number | null;
  cves: CveItem[];
  queried_at: string | null;
  source: string | null;
  error: string | null;
}

export interface CvesResponse {
  campaign_id: string;
  matches: CveMatch[];
}

export interface CreateCampaignBody {
  config: {
    authorized_by: string;
    authorized_at: string;
    unattended?: boolean;
  };
  revalidate_from?: string;
}
