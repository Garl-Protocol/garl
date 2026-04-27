"""
Capability Gate — pre-flight evaluation that turns a Trust Vector + the
agent's intended action into a {decision, optional capability token}.

Strategy:
  1. Look up the agent's Trust Vector (Wave 1 service).
  2. Pick the dimension that best maps to the requested action_type.
  3. Compare against a side_effect_class threshold. None → permissive.
     Reversible → moderate. Irreversible → strict.
  4. If the agent clears, mint a fresh capability token scoped to the
     action and hand it back. The agent presents the token to the tool
     server; the tool server can verify offline against
     /.well-known/garl-keys.json.

Decisions are logged to the receipts envelope (`policy_decision` field)
when the action runs, so the gate's verdict becomes part of the immutable
record. This is the load-bearing primitive that lets the project make the
"agents under capability gates" claim concrete.
"""

from __future__ import annotations

import logging
from typing import Any

from app.services.agents import get_agent
from app.services.capability_tokens import (
    SIDE_EFFECT_CLASSES,
    issue_capability_token,
)
from app.services.trust_vector import compute_trust_vector

logger = logging.getLogger(__name__)


# Threshold by side-effect class. Numbers are the minimum dimension score
# (0..1) required to issue a token. Reversible actions trade safety for
# friction — so we let lower-confidence agents through. Irreversible needs
# real demonstrated trust.
DEFAULT_THRESHOLDS: dict[str, float] = {
    "none": 0.0,
    "reversible": 0.40,
    "irreversible": 0.70,
}


# Map action_type → which Trust Vector dimension to evaluate. When a fully
# tracked dimension exists for the action, use it; otherwise fall back to
# the breadth-of-trust signal (`agent_identity_assurance`).
ACTION_DIMENSION_MAP: dict[str, str] = {
    "code_write":      "code_task_reliability",
    "tool_call":       "code_task_reliability",
    "api_call":        "code_task_reliability",
    "browser_action":  "code_task_reliability",
    "file_op":         "code_task_reliability",
    "payment":         "agent_identity_assurance",  # until payment_dispute_rate has data
}


class GateError(ValueError):
    """Inputs the gate refuses to evaluate (unknown action, bad agent id)."""


def evaluate_request(
    *,
    agent_id: str,
    action_type: str,
    side_effect_class: str,
    target: str | None = None,
    requested_scope: str | None = None,
    expires_in_seconds: int = 3600,
    spend_limit_usd: float | None = None,
    merchant_allowlist: list[str] | None = None,
    threshold_override: float | None = None,
) -> dict:
    """Pre-flight: should this agent be allowed to perform this action?

    Returns:
        {
          "decision": "allowed" | "denied" | "requires_human",
          "reason": "...",
          "score": float | None,
          "threshold": float,
          "dimension": str,
          "token": "..." | None,
          "token_hash": str | None,
          "expires_at": str | None
        }
    """
    if side_effect_class not in SIDE_EFFECT_CLASSES:
        raise GateError(f"Unknown side_effect_class: {side_effect_class!r}")

    agent = get_agent(agent_id)
    if not agent:
        return {
            "decision": "denied",
            "reason": f"Agent {agent_id} not found in canonical registry",
            "score": None,
            "threshold": threshold_override or DEFAULT_THRESHOLDS[side_effect_class],
            "dimension": None,
            "token": None,
            "token_hash": None,
            "expires_at": None,
        }

    vector = compute_trust_vector(agent)
    dimension = ACTION_DIMENSION_MAP.get(action_type, "agent_identity_assurance")
    score = vector["dimensions"].get(dimension)
    if score is None:
        # Dimension not yet measurable for this agent (e.g. payment with no
        # payment receipts). Fall back to identity assurance as the floor.
        score = vector["dimensions"].get("agent_identity_assurance", 0.0)
        dimension = "agent_identity_assurance"

    threshold = threshold_override if threshold_override is not None else DEFAULT_THRESHOLDS[side_effect_class]

    if score < threshold:
        # For irreversible action below threshold, escalate to human review
        # rather than flat-out deny — gives the operator a path.
        decision = "requires_human" if side_effect_class == "irreversible" else "denied"
        return {
            "decision": decision,
            "reason": (
                f"{dimension}={score:.3f} below threshold {threshold:.3f} "
                f"for side_effect={side_effect_class}"
            ),
            "score": score,
            "threshold": threshold,
            "dimension": dimension,
            "token": None,
            "token_hash": None,
            "expires_at": None,
        }

    scope = requested_scope or _default_scope(action_type, target)
    token = issue_capability_token(
        agent_id=agent_id,
        scope=scope,
        side_effect_class=side_effect_class,
        expires_in_seconds=expires_in_seconds,
        spend_limit_usd=spend_limit_usd,
        merchant_allowlist=merchant_allowlist,
    )
    return {
        "decision": "allowed",
        "reason": (
            f"{dimension}={score:.3f} ≥ threshold {threshold:.3f} "
            f"for side_effect={side_effect_class}"
        ),
        "score": score,
        "threshold": threshold,
        "dimension": dimension,
        "token": token["token"],
        "token_hash": token["token_hash"],
        "expires_at": token["expires_at"],
    }


def _default_scope(action_type: str, target: str | None) -> str:
    if target:
        return f"{action_type}:{target}"
    return f"{action_type}:*"
