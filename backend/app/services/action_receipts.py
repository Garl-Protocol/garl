"""
Action Receipt v0.1 service.

Persists Action Receipt v0.1 envelopes (any tool call, not just commits)
into the new `receipts` table. Wraps the same canonical-JSON + ECDSA-
secp256k1 + RFC 6979 pipeline used by the legacy /verify (traces) path,
but emits the new envelope shape declared in
protocol/spec/action-receipt-v0.1.md.

The legacy `traces` table stays the home for git-commit flavored traces
(GitHub Action, PR Bot). New generic submissions land here.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.core.signing import (
    derive_key_id,
    get_active_key_id,
    get_public_key_hex,
    sign_payload,
)
from app.core.supabase_client import get_supabase as _get_supabase

logger = logging.getLogger(__name__)

ACTION_RECEIPT_VERSION = "garl/action-receipt/v0.1"

ACTION_TYPES = {"code_write", "api_call", "payment", "browser_action", "file_op", "tool_call"}
SIDE_EFFECTS = {"none", "reversible", "irreversible"}
RUNTIMES = {
    "claude-code", "cursor", "copilot", "aider", "codex",
    "mcp-client", "langchain", "crewai", "llamaindex",
    "semantic-kernel", "custom",
}
PROTOCOLS = {"github", "mcp", "a2a", "acp", "ap2", "x402", "raw-http"}
POLICY_DECISIONS = {"allowed", "denied", "requires_human"}


class ActionReceiptValidationError(ValueError):
    """Caller-supplied input doesn't match the v0.1 envelope contract."""


def _hash_canonical(obj: dict | str) -> str:
    """SHA-256 of canonical JSON (sorted keys, no whitespace, UTF-8). For
    string inputs this hashes the UTF-8 bytes directly — useful when the
    caller already has a canonical body."""
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode("utf-8")).hexdigest()
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_input(req: dict) -> None:
    """Lightweight validation matching the JSON Schema in
    protocol/schema/action-receipt-v0.1.json. Pydantic would be more
    rigorous but is overkill here — the schema is the source of truth and
    consumers can run jsonschema validation themselves."""
    required = ("agent_id", "runtime", "protocol", "action_type",
                "input_hash", "output_hash", "side_effect")
    for f in required:
        if f not in req or req[f] in (None, ""):
            raise ActionReceiptValidationError(f"Field {f!r} is required")
    if req["runtime"] not in RUNTIMES:
        raise ActionReceiptValidationError(f"Unknown runtime: {req['runtime']!r}")
    if req["protocol"] not in PROTOCOLS:
        raise ActionReceiptValidationError(f"Unknown protocol: {req['protocol']!r}")
    if req["action_type"] not in ACTION_TYPES:
        raise ActionReceiptValidationError(f"Unknown action_type: {req['action_type']!r}")
    if req["side_effect"] not in SIDE_EFFECTS:
        raise ActionReceiptValidationError(f"Unknown side_effect: {req['side_effect']!r}")
    if req.get("policy_decision") and req["policy_decision"] not in POLICY_DECISIONS:
        raise ActionReceiptValidationError(
            f"Unknown policy_decision: {req['policy_decision']!r}"
        )
    for h_field in ("input_hash", "output_hash"):
        h = req[h_field]
        if not (isinstance(h, str) and len(h) == 64 and all(c in "0123456789abcdef" for c in h.lower())):
            raise ActionReceiptValidationError(f"{h_field} must be 64 lowercase hex chars")
    if req.get("previous_receipt_hash") is not None:
        h = req["previous_receipt_hash"]
        if not (isinstance(h, str) and len(h) == 64):
            raise ActionReceiptValidationError("previous_receipt_hash must be 64 hex chars")
    if req.get("capability_token_hash") is not None:
        h = req["capability_token_hash"]
        if not (isinstance(h, str) and len(h) == 64):
            raise ActionReceiptValidationError("capability_token_hash must be 64 hex chars")


def submit_action_receipt(req: dict) -> dict:
    """Submit a v0.1 Action Receipt.

    Required fields per the spec; optional fields are accepted and stored.
    Returns the canonical envelope (with signature + verification_key_id)
    as it will appear at /api/v1/receipts/{id}/cert.json.
    """
    _validate_input(req)

    agent_id = req["agent_id"]

    # Silent abuse guard: per-agent monthly cap. Raises 429 with
    # Retry-After if exceeded. The cap is high enough (10K/month default)
    # that legitimate workflows never see this.
    from app.services.monthly_cap import enforce_monthly_cap
    enforce_monthly_cap(agent_id)

    # The envelope is what we sign; the DB row mirrors it for indexing.
    envelope: dict[str, Any] = {
        "receipt_id": str(uuid.uuid4()),
        "version": ACTION_RECEIPT_VERSION,
        "issuer": "https://api.garl.ai",
        "agent_identity": f"did:garl:{agent_id}",
        "human_delegate": req.get("human_delegate"),
        "runtime": req["runtime"],
        "protocol": req["protocol"],
        "action_type": req["action_type"],
        "tool_server": req.get("tool_server"),
        "input_hash": req["input_hash"].lower(),
        "output_hash": req["output_hash"].lower(),
        "side_effect": req["side_effect"],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    if req.get("capability_token_hash"):
        envelope["capability_request"] = {
            "token_hash": req["capability_token_hash"],
            "side_effect_class": req["side_effect"],
        }
    if req.get("policy_decision"):
        envelope["policy_decision"] = req["policy_decision"]
    if req.get("cost") is not None:
        envelope["cost"] = req["cost"]
    if req.get("previous_receipt_hash"):
        envelope["previous_receipt_hash"] = req["previous_receipt_hash"]
    if req.get("attestations"):
        envelope["attestations"] = list(req["attestations"])
    if req.get("redaction_policy") is not None:
        envelope["redaction_policy"] = req["redaction_policy"]

    # Sign the envelope-without-signature, then attach.
    signature, _digest = sign_payload(envelope)
    envelope["signature"] = signature
    envelope["verification_key_id"] = get_active_key_id()

    # Persist a row that mirrors the envelope and indexes the bits we
    # query by (agent_id, action_type, side_effect, output_hash).
    sb = _get_supabase()
    row = {
        "receipt_id": envelope["receipt_id"],
        "agent_id": agent_id,
        "human_delegate": envelope.get("human_delegate"),
        "runtime": envelope["runtime"],
        "protocol": envelope["protocol"],
        "action_type": envelope["action_type"],
        "tool_server": envelope.get("tool_server"),
        "capability_token_hash": req.get("capability_token_hash"),
        "policy_decision": envelope.get("policy_decision"),
        "input_hash": envelope["input_hash"],
        "output_hash": envelope["output_hash"],
        "side_effect": envelope["side_effect"],
        "cost": envelope.get("cost"),
        "attestations": envelope.get("attestations"),
        "redaction_policy": envelope.get("redaction_policy"),
        "previous_receipt_hash": envelope.get("previous_receipt_hash"),
        "signature": envelope["signature"],
        "verification_key_id": envelope["verification_key_id"],
        "envelope_json": envelope,
    }
    sb.table("receipts").insert(row).execute()
    return envelope


def get_action_receipt(receipt_id: str) -> dict | None:
    """Fetch the canonical envelope for a receipt by its receipt_id (UUID)
    or by its output_hash (64-hex). Returns None if not found."""
    sb = _get_supabase()
    if len(receipt_id) == 64 and all(c in "0123456789abcdef" for c in receipt_id.lower()):
        # caller passed an output hash
        res = (
            sb.table("receipts")
            .select("envelope_json, redaction_policy")
            .eq("output_hash", receipt_id.lower())
            .limit(1)
            .execute()
        )
    else:
        res = (
            sb.table("receipts")
            .select("envelope_json, redaction_policy")
            .eq("receipt_id", receipt_id)
            .limit(1)
            .execute()
        )
    if not res.data:
        return None
    row = res.data[0]
    envelope = row.get("envelope_json")
    return envelope


def build_envelope_for_signing(req: dict) -> dict:
    """Helper exposed for tests + offline tooling: build the envelope
    *without* signing or persisting. Validates inputs and stamps a fresh
    receipt_id + timestamp, but returns the dict pre-signature so callers
    can hash it themselves."""
    _validate_input(req)
    agent_id = req["agent_id"]
    return {
        "receipt_id": str(uuid.uuid4()),
        "version": ACTION_RECEIPT_VERSION,
        "issuer": "https://api.garl.ai",
        "agent_identity": f"did:garl:{agent_id}",
        "human_delegate": req.get("human_delegate"),
        "runtime": req["runtime"],
        "protocol": req["protocol"],
        "action_type": req["action_type"],
        "tool_server": req.get("tool_server"),
        "input_hash": req["input_hash"].lower(),
        "output_hash": req["output_hash"].lower(),
        "side_effect": req["side_effect"],
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
