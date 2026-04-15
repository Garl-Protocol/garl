import re
from pydantic import BaseModel, Field, field_validator
from enum import Enum

_HTML_TAG_RE = re.compile(r"<[^>]+>")


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
    homepage_url: str | None = Field(default=None, max_length=500)

    @field_validator("homepage_url", mode="before")
    @classmethod
    def validate_url_scheme(cls, v: str | None) -> str | None:
        if v and not v.startswith(("https://", "http://")):
            return None
        return v
    is_sandbox: bool = Field(
        default=False,
        description="Mark as sandbox/test agent. Sandbox agents are hidden from leaderboard."
    )
    permissions_declared: list[str] | None = Field(
        default=None,
        description="List of permissions the agent declares it uses (e.g. file_read, web_request)"
    )
    developer_handle: str | None = Field(
        default=None,
        max_length=200,
        description="Opaque developer identifier (GitHub handle, email, org slug). Stored as a SHA-256 hash — plaintext is never persisted.",
    )

    @field_validator("description", "framework", mode="before")
    @classmethod
    def strip_html(cls, v: str) -> str:
        if isinstance(v, str) and v:
            return _HTML_TAG_RE.sub("", v).strip()
        return v


class AutoRegisterRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    framework: str = Field(default="custom", max_length=50)
    category: TaskCategory = TaskCategory.other
    description: str = Field(default="", max_length=500)
    runtime_proof: str | None = Field(
        default=None,
        max_length=256,
        description="Optional runtime proof token to verify agent is a real runtime"
    )
    developer_handle: str | None = Field(
        default=None,
        max_length=200,
        description="Opaque developer identifier, hashed on write.",
    )

    @field_validator("description", "framework", mode="before")
    @classmethod
    def strip_html(cls, v: str) -> str:
        if isinstance(v, str) and v:
            return _HTML_TAG_RE.sub("", v).strip()
        return v


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


class ModelAttestation(BaseModel):
    """One AI model that contributed to this execution.

    Optional — multiple entries allow a single receipt to attest that
    a PR was co-authored by e.g. Claude Code + Copilot + Cursor."""
    name: str = Field(..., max_length=100)
    version: str | None = Field(default=None, max_length=100)
    detection_confidence: float | None = Field(default=None, ge=0, le=1)
    role: str | None = Field(
        default=None,
        max_length=40,
        description="e.g. 'primary-author', 'reviewer', 'test-generator'",
    )


class TraceSubmitRequest(BaseModel):
    agent_id: str
    task_description: str = Field(..., max_length=1000)
    status: TraceStatus
    duration_ms: int = Field(..., ge=0)
    input_summary: str = Field(default="", max_length=500)
    output_summary: str = Field(default="", max_length=500)
    models: list[ModelAttestation] | None = Field(
        default=None,
        description="AI models that co-authored this execution (for multi-model PR attestation).",
    )

    @field_validator("task_description", "input_summary", "output_summary", mode="before")
    @classmethod
    def strip_html_tags(cls, v: str) -> str:
        if isinstance(v, str) and v:
            return _HTML_TAG_RE.sub("", v).strip()
        return v
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
    receipt_url: str | None = None
    short_hash: str | None = None


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


def _validate_public_webhook_url(value: str) -> str:
    """Reject webhook URLs that could target internal infrastructure (SSRF).

    Checks, in order: HTTPS scheme, hostname present, blocked hostname
    list (localhost + cloud metadata endpoints), and — when the hostname
    is an IP literal — ipaddress-module classification (loopback, link-
    local, private, reserved, multicast, unspecified). DNS names are
    allowed since we also guard at delivery time via `_fire_webhooks_sync`."""
    import ipaddress
    from urllib.parse import urlparse

    if not isinstance(value, str) or not value.startswith("https://"):
        raise ValueError("Webhook URL must use HTTPS scheme")
    parsed = urlparse(value)
    host = (parsed.hostname or "").strip().lower()
    if not host:
        raise ValueError("Webhook URL must include a hostname")

    _BLOCKED_HOSTS = {
        "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
        "metadata.google.internal",           # GCP metadata
        "metadata.goog",                      # GCP metadata (new)
        "instance-data",                      # AWS metadata classic
        "metadata.azure.com",                 # Azure metadata
    }
    if host in _BLOCKED_HOSTS or host.endswith(".localhost"):
        raise ValueError("Webhook URL must not point to a loopback or metadata host")

    # IP-literal hosts: canonicalise then apply full classification.
    try:
        ip = ipaddress.ip_address(host.strip("[]"))
    except ValueError:
        # hostname is a domain name — accept (delivery-time guard also runs)
        return value

    if (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    ):
        raise ValueError("Webhook URL must not target a private/reserved IP address")
    return value


class WebhookRegisterRequest(BaseModel):
    agent_id: str
    url: str = Field(..., max_length=500)
    events: list[str] | None = None

    @field_validator("url", mode="before")
    @classmethod
    def validate_webhook_url(cls, v: str) -> str:
        return _validate_public_webhook_url(v)


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

    @field_validator("url", mode="before")
    @classmethod
    def validate_webhook_url(cls, v):
        if v is None:
            return v
        return _validate_public_webhook_url(v)


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
