"""
Reversibility primitives — UETA §10(b) friendly.

Workflow:
  1. At receipt-creation time: if `side_effect == "reversible"`, the agent
     records a *compensation* — the action that would undo this one. The
     compensation lives in the `compensations` table with status='recorded'.
  2. Some time later, a consumer (or the agent itself) decides to undo.
     They call trigger_undo(receipt_id) — status becomes 'pending', the
     undo_payload is returned to the caller, who actually runs it.
  3. The caller marks the compensation as 'succeeded' or 'failed' once the
     undo action completes (via mark_compensation_result).

Note on `irreversible` receipts: trigger_undo refuses. There is no
auto-undo path; the only recourse is operator + dispute mechanisms.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

VALID_STATUSES = ("recorded", "pending", "succeeded", "failed")


class ReversibilityError(ValueError):
    """Caller asked for an undo that the policy/state machine refuses."""


def record_compensation(
    *,
    receipt_id: str,
    agent_id: str,
    undo_payload: dict,
    reason: str = "recorded-at-receipt-time",
) -> dict:
    """Attach a compensation to a reversible receipt.

    Caller MUST have already verified the receipt's side_effect class.
    This function does *not* re-validate the receipt to keep the persistence
    layer thin; misuse fails at insert with a foreign-key violation.
    """
    sb = _get_supabase()
    row = {
        "receipt_id": receipt_id,
        "agent_id": agent_id,
        "undo_payload": undo_payload,
        "reason": reason,
        "status": "recorded",
    }
    res = sb.table("compensations").insert(row).execute()
    return res.data[0] if res.data else row


def trigger_undo(receipt_id: str, reason: str) -> dict:
    """Move a compensation from 'recorded' to 'pending' and return the
    payload the caller needs to actually run.

    UETA §10(b) consumers call this with reason='consumer-initiated-undo'.

    Raises:
        ReversibilityError if no compensation is recorded, or the receipt
        was irreversible, or the compensation already succeeded.
    """
    sb = _get_supabase()
    receipt_res = (
        sb.table("receipts")
        .select("side_effect")
        .eq("receipt_id", receipt_id)
        .limit(1)
        .execute()
    )
    if not receipt_res.data:
        raise ReversibilityError(f"Receipt {receipt_id} not found")
    side_effect = receipt_res.data[0].get("side_effect")
    if side_effect == "irreversible":
        raise ReversibilityError(
            "Receipt is classified irreversible; no undo path exists. "
            "File a dispute via the operator instead."
        )
    if side_effect == "none":
        raise ReversibilityError(
            "Receipt has no side effect to reverse (side_effect=none)"
        )

    comp_res = (
        sb.table("compensations")
        .select("*")
        .eq("receipt_id", receipt_id)
        .order("triggered_at", desc=True)
        .limit(1)
        .execute()
    )
    if not comp_res.data:
        raise ReversibilityError(
            f"No compensation recorded for receipt {receipt_id}; "
            "the agent did not register an undo at receipt time"
        )

    comp = comp_res.data[0]
    if comp["status"] == "succeeded":
        raise ReversibilityError("Already undone")
    if comp["status"] == "pending":
        # Idempotent — another caller already triggered. Return the same
        # payload rather than rejecting; consumers can poll safely.
        return {
            "compensation_id": comp["id"],
            "receipt_id": receipt_id,
            "status": "pending",
            "undo_payload": comp["undo_payload"],
            "message": "Undo already pending — execute undo_payload yourself",
        }

    sb.table("compensations").update(
        {
            "status": "pending",
            "reason": reason,
            "triggered_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", comp["id"]).execute()

    return {
        "compensation_id": comp["id"],
        "receipt_id": receipt_id,
        "status": "pending",
        "undo_payload": comp["undo_payload"],
        "message": (
            "Undo recorded. Execute the undo_payload (e.g. POST /v1/refunds, "
            "DELETE /v1/events/{id}) and then call mark_compensation_result "
            "with status='succeeded' or 'failed'."
        ),
    }


def mark_compensation_result(
    compensation_id: str,
    status: str,
    result_receipt_id: str | None = None,
) -> dict:
    """Close out a triggered undo: succeeded or failed."""
    if status not in ("succeeded", "failed"):
        raise ReversibilityError(
            f"Result status must be 'succeeded' or 'failed', got {status!r}"
        )
    sb = _get_supabase()
    update: dict[str, Any] = {"status": status}
    if result_receipt_id:
        update["result_receipt_id"] = result_receipt_id
    res = (
        sb.table("compensations")
        .update(update)
        .eq("id", compensation_id)
        .execute()
    )
    return res.data[0] if res.data else update


def get_compensation_for_receipt(receipt_id: str) -> dict | None:
    """Most-recent compensation for a receipt, regardless of status."""
    sb = _get_supabase()
    res = (
        sb.table("compensations")
        .select("*")
        .eq("receipt_id", receipt_id)
        .order("triggered_at", desc=True)
        .limit(1)
        .execute()
    )
    return res.data[0] if res.data else None
