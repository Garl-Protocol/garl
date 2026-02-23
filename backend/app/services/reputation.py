"""
GARL Trust Engine v4 — Sovereign Trust Layer

Five-dimensional EMA-based reputation system:
  reliability      - Success/failure rate, streak bonus (EMA-weighted)
  security         - Permission discipline, tool safety, anomaly history (EMA-weighted)
  speed            - Duration efficiency relative to category benchmark (EMA-weighted)
  cost_efficiency  - Cost efficiency relative to category benchmark (EMA-weighted)
  consistency      - Result consistency (standard deviation based)

Composite score = weighted average:
  reliability: 30%, security: 20%, speed: 15%, cost_efficiency: 10%, consistency: 25%

Certification Tiers:
  Bronze (0-40)     — Beginner / Unverified
  Silver (40-70)    — Trusted / Active
  Gold (70-90)      — High Performance / Verified
  Enterprise (90+)  — Zero Anomalies / SLA Compliant
"""

import math
import statistics
from datetime import datetime, timezone

BASELINE = 50.0
MAX_SCORE = 100.0
MIN_SCORE = 0.0

EMA_ALPHA = 0.3

# v1.0 updated weights (5 dimensions)
WEIGHTS = {
    "reliability": 0.30,
    "security": 0.20,
    "speed": 0.15,
    "cost_efficiency": 0.10,
    "consistency": 0.25,
}

# Certification tier thresholds
TIER_THRESHOLDS = {
    "enterprise": 90.0,
    "gold": 70.0,
    "silver": 40.0,
    "bronze": 0.0,
}

# Tier-based endorsement multipliers (Gold/Enterprise = 10x)
TIER_ENDORSEMENT_MULTIPLIER = {
    "enterprise": 10.0,
    "gold": 10.0,
    "silver": 2.0,
    "bronze": 1.0,
}

BASE_DELTAS = {"success": 2.0, "failure": -3.0, "partial": 0.5}

SPEED_BENCHMARKS = {
    "coding": 10000,
    "research": 15000,
    "sales": 5000,
    "data": 12000,
    "automation": 8000,
    "other": 10000,
}

COST_BENCHMARKS = {
    "coding": 0.05,
    "research": 0.08,
    "sales": 0.03,
    "data": 0.06,
    "automation": 0.04,
    "other": 0.05,
}

# Security dimension: high-risk tools
HIGH_RISK_TOOLS = {
    "shell_exec", "file_write", "file_delete", "system_command",
    "raw_sql", "eval", "exec", "subprocess", "os_command",
}
SENSITIVE_TOOLS = {
    "file_read", "web_request", "db_query", "http_request",
    "api_call", "network_access",
}


def _ema_update(ema_old: float, observation: float, alpha: float = EMA_ALPHA) -> float:
    return round(alpha * observation + (1 - alpha) * ema_old, 4)


def compute_certification_tier(trust_score: float, anomaly_flags: list[dict] | None = None) -> str:
    """Calculate certification tier based on score and anomaly status."""
    active_anomalies = [
        f for f in (anomaly_flags or [])
        if not f.get("archived")
    ]

    # Enterprise tier: zero active anomalies required
    if trust_score >= TIER_THRESHOLDS["enterprise"] and len(active_anomalies) == 0:
        return "enterprise"
    elif trust_score >= TIER_THRESHOLDS["gold"]:
        return "gold"
    elif trust_score >= TIER_THRESHOLDS["silver"]:
        return "silver"
    return "bronze"


def compute_reliability_delta_ema(
    current: float, ema_rel: float, status: str, consecutive_successes: int
) -> tuple[float, float, float]:
    """
    Reliability dimension: EMA-based calculation.
    Returns: (delta, new_score, new_ema)
    """
    base = BASE_DELTAS.get(status, 0.0)

    if status == "success" and consecutive_successes > 1:
        base += min(consecutive_successes * 0.1, 1.0)

    # Diminishing returns (above 80) and diminishing penalty (below 20)
    if base > 0 and current > 80:
        base *= 1.0 - ((current - 80) / 40)
    elif base < 0 and current < 20:
        base *= 1.0 - ((20 - current) / 40)

    delta = round(base, 4)
    raw_new = current + delta

    new_ema = _ema_update(ema_rel, raw_new)
    blended = (raw_new + new_ema) / 2.0
    new_score = clamp_score(blended)

    return delta, new_score, new_ema


def compute_security_score(
    current: float,
    ema_sec: float,
    status: str,
    tool_calls: list[dict] | None,
    permissions_used: list[str] | None,
    permissions_declared: list[str] | None,
    pii_mask: bool,
    security_context: dict | None,
    total_traces: int,
) -> tuple[float, float]:
    """
    Security dimension: permission discipline, tool safety, and data protection.
    Returns: (new_score, new_ema)
    """
    # Base delta: successful trace +1.0, failed -2.0
    base = 1.0 if status == "success" else (-2.0 if status == "failure" else 0.3)

    # Permission bonus: within declared permissions?
    if permissions_used and permissions_declared:
        undeclared = set(permissions_used) - set(permissions_declared)
        if undeclared:
            base -= min(len(undeclared) * 0.5, 2.0)
        elif len(permissions_used) <= 3:
            base += 0.5

    # High-risk tool penalty
    if tool_calls:
        tool_names = {tc.get("name", "").lower() for tc in tool_calls if isinstance(tc, dict)}
        high_risk_count = len(tool_names & HIGH_RISK_TOOLS)
        sensitive_count = len(tool_names & SENSITIVE_TOOLS)
        base -= high_risk_count * 0.8
        base -= sensitive_count * 0.2

    # PII masking bonus
    if pii_mask:
        base += 0.3

    # Security context analysis
    if security_context:
        if security_context.get("prompt_injection_detected"):
            base -= 3.0
        if security_context.get("data_leak_risk"):
            base -= 2.0
        if security_context.get("sandboxed"):
            base += 0.5

    # Damping for the first 5 traces
    if total_traces < 5:
        base *= 0.5

    # Diminishing returns
    if base > 0 and current > 80:
        base *= 1.0 - ((current - 80) / 40)
    elif base < 0 and current < 20:
        base *= 1.0 - ((20 - current) / 40)

    raw_new = current + base
    new_ema = _ema_update(ema_sec, raw_new)
    blended = (raw_new + new_ema) / 2.0

    return round(clamp_score(blended), 2), new_ema


def compute_speed_score(
    current: float, ema_spd: float, duration_ms: int, category: str, total_traces: int
) -> tuple[float, float]:
    benchmark = SPEED_BENCHMARKS.get(category, 10000)
    ratio = duration_ms / benchmark

    if ratio <= 0.5:
        delta = 1.5
    elif ratio <= 1.0:
        delta = 0.8
    elif ratio <= 2.0:
        delta = -0.5
    else:
        delta = -1.5

    if total_traces < 5:
        delta *= 0.5

    raw_new = current + delta
    new_ema = _ema_update(ema_spd, raw_new)
    blended = (raw_new + new_ema) / 2.0

    return round(clamp_score(blended), 2), new_ema


def compute_cost_score(
    current: float, ema_cst: float, cost_usd: float, category: str, total_traces: int
) -> tuple[float, float]:
    if cost_usd <= 0:
        return current, ema_cst

    benchmark = COST_BENCHMARKS.get(category, 0.05)
    ratio = cost_usd / benchmark

    if ratio <= 0.5:
        delta = 1.2
    elif ratio <= 1.0:
        delta = 0.5
    elif ratio <= 2.0:
        delta = -0.5
    else:
        delta = -1.2

    if total_traces < 5:
        delta *= 0.5

    raw_new = current + delta
    new_ema = _ema_update(ema_cst, raw_new)
    blended = (raw_new + new_ema) / 2.0

    return round(clamp_score(blended), 2), new_ema


def compute_consistency_score(
    current: float, recent_deltas: list[float]
) -> float:
    if len(recent_deltas) < 3:
        return current

    stdev = statistics.stdev(recent_deltas) if len(recent_deltas) > 1 else 0

    if stdev < 0.5:
        delta = 1.0
    elif stdev < 1.5:
        delta = 0.3
    elif stdev < 3.0:
        delta = -0.5
    else:
        delta = -1.5

    return round(clamp_score(current + delta), 2)


def compute_composite_score(dimensions: dict[str, float]) -> float:
    """Weighted average of five dimensions."""
    total = sum(
        dimensions.get(dim, BASELINE) * weight
        for dim, weight in WEIGHTS.items()
    )
    return round(clamp_score(total), 2)


def apply_time_decay(score: float, hours_since_last: float) -> float:
    """Score decay: pulled toward baseline at 0.1% per day."""
    if hours_since_last <= 0:
        return score

    days = hours_since_last / 24.0
    decay_rate = 0.001
    decay = (score - BASELINE) * (1 - math.pow(1 - decay_rate, days))
    return round(clamp_score(score - decay), 2)


def detect_anomalies(
    agent: dict, new_status: str, duration_ms: int, cost_usd: float
) -> list[dict]:
    flags = []
    total = int(agent.get("total_traces", 0))
    if total < 10:
        return flags

    success_rate = float(agent.get("success_rate", 0))
    avg_dur = int(agent.get("avg_duration_ms", 0) or 0)

    if new_status == "failure" and success_rate > 90:
        flags.append({
            "type": "unexpected_failure",
            "severity": "warning",
            "message": f"Failure from agent with {success_rate}% success rate",
        })

    if avg_dur > 0 and duration_ms > avg_dur * 5:
        flags.append({
            "type": "duration_spike",
            "severity": "warning",
            "message": f"Duration {duration_ms}ms is 5x+ above average {avg_dur}ms",
        })

    prev_cost = float(agent.get("total_cost_usd", 0) or 0)
    if total > 0 and cost_usd > 0:
        avg_cost = prev_cost / total
        if avg_cost > 0 and cost_usd > avg_cost * 10:
            flags.append({
                "type": "cost_spike",
                "severity": "critical",
                "message": f"Cost ${cost_usd:.4f} is 10x+ above average ${avg_cost:.4f}",
            })

    return flags


ANOMALY_CLEAR_THRESHOLD = 50


def auto_clear_anomalies(existing_flags: list[dict], consecutive_clean: int) -> list[dict]:
    """Archive warning-level anomalies after consecutive clean traces."""
    if consecutive_clean < ANOMALY_CLEAR_THRESHOLD or not existing_flags:
        return existing_flags

    cleared = []
    for flag in existing_flags:
        if flag.get("severity") == "warning":
            flag = {**flag, "archived": True, "archived_reason": f"auto_cleared_after_{consecutive_clean}_clean_traces"}
            cleared.append(flag)
        else:
            cleared.append(flag)

    active = [f for f in cleared if not f.get("archived")]
    archived = [f for f in cleared if f.get("archived")]
    return active + archived[-5:]


ENDORSEMENT_MULTIPLIER_BASE = 0.05
ENDORSEMENT_MULTIPLIER_CAP = 2.5  # v1.0: higher cap with Gold/Enterprise multiplier


def compute_endorsement_bonus(
    endorser_score: float,
    endorser_traces: int,
    endorser_tier: str = "bronze",
) -> float:
    """Sybil-resistant endorsement bonus. Tier-based weighting.

    Endorsements from Gold/Enterprise tier agents are 10x more effective.
    Bronze agents endorsing each other has near-zero impact.
    """
    if endorser_traces < 10 or endorser_score < 60:
        return 0.0

    credibility = min((endorser_score - 50) / 50.0, 1.0)
    volume_factor = min(endorser_traces / 100.0, 1.0)

    # Tier multiplier
    tier_multiplier = TIER_ENDORSEMENT_MULTIPLIER.get(endorser_tier, 1.0)

    bonus = ENDORSEMENT_MULTIPLIER_BASE * credibility * volume_factor * tier_multiplier

    return round(min(bonus, ENDORSEMENT_MULTIPLIER_CAP), 4)


def compute_success_rate(successes: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(successes / total * 100, 2)


def clamp_score(score: float) -> float:
    return max(MIN_SCORE, min(MAX_SCORE, round(score, 2)))


def project_decay(current_score: float, days: list[int]) -> list[dict]:
    projections = []
    for d in days:
        projected = apply_time_decay(current_score, d * 24.0)
        projections.append({"days": d, "projected_score": projected})
    return projections
