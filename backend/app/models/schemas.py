from pydantic import BaseModel, Field
from enum import Enum


class TaskCategory(str, Enum):
    coding = "coding"
    research = "research"
    sales = "sales"
    data = "data"
    automation = "automation"
    other = "other"


class TraceStatus(str, Enum):
    success = "success"
    failure = "failure"
    partial = "partial"


class CertificationTier(str, Enum):
    bronze = "bronze"
    silver = "silver"
    gold = "gold"
    enterprise = "enterprise"


class AgentRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    framework: str = Field(default="custom", max_length=50)
    category: TaskCategory = TaskCategory.other
    homepage_url: str | None = None
    is_sandbox: bool = Field(
        default=False,
        description="Mark as sandbox/test agent. Sandbox agents are hidden from leaderboard."
    )
    permissions_declared: list[str] | None = Field(
        default=None,
        description="List of permissions the agent declares it uses (e.g. file_read, web_request)"
    )


class AutoRegisterRequest(BaseModel):
    """Otonom ajanlar için sadeleştirilmiş kayıt şeması."""
    name: str = Field(..., min_length=1, max_length=100)
    framework: str = Field(default="custom", max_length=50)
    category: TaskCategory = TaskCategory.other
    description: str = Field(default="", max_length=500)
    runtime_proof: str | None = Field(
        default=None,
        max_length=256,
        description="Optional runtime proof token to verify agent is a real runtime"
    )


class AgentResponse(BaseModel):
    id: str
    name: str
    description: str
    framework: str
    category: str
    trust_score: float
    total_traces: int
    success_rate: float
    homepage_url: str | None
    api_key: str | None = None
    sovereign_id: str | None = None
    certification_tier: str = "bronze"
    created_at: str


class TrustDimensions(BaseModel):
    reliability: float = 50.0
    security: float = 50.0
    speed: float = 50.0
    cost_efficiency: float = 50.0
    consistency: float = 50.0


class ToolCall(BaseModel):
    name: str = Field(..., max_length=200)
    input: dict | None = None
    output: dict | None = None
    duration_ms: int | None = None


class TraceSubmitRequest(BaseModel):
    agent_id: str
    task_description: str = Field(..., max_length=1000)
    status: TraceStatus
    duration_ms: int = Field(..., ge=0)
    input_summary: str = Field(default="", max_length=500)
    output_summary: str = Field(default="", max_length=500)
    category: TaskCategory = TaskCategory.other
    metadata: dict | None = None
    runtime_env: str = Field(default="", max_length=100)
    tool_calls: list[ToolCall] | None = None
    cost_usd: float | None = Field(default=None, ge=0)
    token_count: int | None = Field(default=None, ge=0)
    proof_of_result: dict | None = Field(
        default=None,
        description="Verifiable evidence of task completion (e.g. output hash, test results)"
    )
    pii_mask: bool = Field(
        default=False,
        description="If true, input_summary and output_summary are SHA-256 hashed before storage"
    )
    permissions_used: list[str] | None = Field(
        default=None,
        description="Permissions used during the trace (for security score calculation)"
    )
    security_context: dict | None = Field(
        default=None,
        description="Security context: prompt_injection_detected, data_leak_risk, etc."
    )


class TraceResponse(BaseModel):
    id: str
    agent_id: str
    task_description: str
    status: str
    duration_ms: int
    trust_delta: float
    trace_hash: str
    certificate: dict
    created_at: str


class LeaderboardEntry(BaseModel):
    id: str
    name: str
    framework: str
    category: str
    trust_score: float
    total_traces: int
    success_rate: float
    certification_tier: str
    rank: int


class BadgeData(BaseModel):
    agent_id: str
    name: str
    trust_score: float
    success_rate: float
    total_traces: int
    verified: bool
    certification_tier: str = "bronze"
    sovereign_id: str | None = None


class A2ATrustResponse(BaseModel):
    agent_id: str
    name: str
    trust_score: float
    success_rate: float
    total_traces: int
    verified: bool
    risk_level: str
    recommendation: str
    certification_tier: str
    sovereign_id: str | None
    dimensions: TrustDimensions
    anomalies: list[dict]
    last_active: str | None


class WebhookRegisterRequest(BaseModel):
    agent_id: str
    url: str = Field(..., max_length=500)
    events: list[str] | None = None


class BatchTraceRequest(BaseModel):
    traces: list[TraceSubmitRequest] = Field(..., min_length=1, max_length=50)


class BatchTraceResponse(BaseModel):
    submitted: int
    failed: int
    results: list[dict]


class EndorsementRequest(BaseModel):
    target_agent_id: str
    context: str = Field(default="", max_length=500, description="Why this agent is endorsed")


class WebhookUpdateRequest(BaseModel):
    is_active: bool | None = None
    url: str | None = Field(default=None, max_length=500)
    events: list[str] | None = None


class RouteRequest(BaseModel):
    category: TaskCategory
    min_tier: CertificationTier = CertificationTier.silver
    limit: int = Field(default=3, ge=1, le=10)


class SoftDeleteRequest(BaseModel):
    confirmation: str = Field(..., description="Deletion confirmation: must be 'DELETE_CONFIRMED'")


class AnonymizeRequest(BaseModel):
    confirmation: str = Field(..., description="Anonymization confirmation: must be 'ANONYMIZE_CONFIRMED'")


class ComplianceResponse(BaseModel):
    agent_id: str
    name: str
    sovereign_id: str
    certification_tier: str
    trust_score: float
    security_score: float
    sla_compliance: dict
    anomaly_history: list[dict]
    security_risks: list[dict]
    endorsement_summary: dict


class OpenClawIngestPayload(BaseModel):
    agent_id: str
    message: str = Field(default="", max_length=1000)
    status: str = Field(default="success")
    duration_ms: int = Field(default=0, ge=0)
    category: str = Field(default="")
    tool_calls: list[dict] | None = None
    error: str | None = None
    runtime_env: str = Field(default="openclaw")
    usage: dict | None = None
    session_id: str | None = None
    channel: str | None = None
    metadata: dict | None = None
