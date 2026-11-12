from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AgentStatus(str, Enum):
    COMPLETED = "completed"
    BLOCKED_BY_SCOPE = "blocked_by_scope"
    FAILED = "failed"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ScopeConfig(BaseModel):
    authorized: bool = False
    allowed_domains: List[str] = Field(default_factory=list)
    allowed_methods: List[str] = Field(default_factory=lambda: ["GET", "OPTIONS"])


class AgentTask(BaseModel):
    campaign_id: str
    target: str
    task_description: str
    scope: ScopeConfig
    context: Dict[str, Any] = Field(default_factory=dict)


class Finding(BaseModel):
    title: str
    technique_id: str
    technique_name: str
    severity: Severity
    description: str
    evidence: Dict[str, Any] = Field(default_factory=dict)
    recommendation: str


class AgentResult(BaseModel):
    agent: str
    tactic_id: str
    tactic_name: str
    status: AgentStatus
    findings: List[Finding] = Field(default_factory=list)
    techniques_used: List[str] = Field(default_factory=list)
    summary: str = ""
    error: Optional[str] = None
    executed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
