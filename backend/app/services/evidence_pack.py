"""
Evidence Pack exporter (garl/evidence-pack/v0.1).

One self-contained, signed bundle per receipt: the receipt envelope, the
capability chain that authorized it, the Merkle inclusion proof + on-chain
anchor coordinates, any session alerts around the action, the key registry
needed to verify all of it offline, and human-readable verification steps.

This is the exportable log unit for EU AI Act Article 12 (automatic event
recording) and Article 19 (log retention) evidence — see
docs/compliance/eu-ai-act.md for the field-by-field mapping and the honest
limitations (no harmonized logging standard exists yet; this is a candidate
format, not a conformity assessment).

The pack itself is signed with the same canonical-JSON + ECDSA-secp256k1
pipeline as receipts: signature over the pack-without-signature fields,
``verification_key_id`` resolving against the public key registry.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from app.core.signing import get_active_key_id, get_key_registry, sign_payload
from app.core.supabase_client import get_supabase as _get_supabase
from app.services.merkle_batch import build_inclusion_proof

logger = logging.getLogger(__name__)

EVIDENCE_PACK_VERSION = "garl/evidence-pack/v0.1"

# Hard cap on capability-chain walk depth. Combined with the seen-set below
# it guarantees termination even on a corrupted parent graph (cycles).
_MAX_CHAIN_DEPTH = 32

_ALERT_WINDOW_HOURS = 24
_MAX_ALERTS = 200


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _now_rfc3339z() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_hex64(s: str) -> bool:
    return len(s) == 64 and all(c in "0123456789abcdef" for c in s.lower())


def _parse_ts(raw: str | None) -> datetime:
    """Best-effort RFC 3339 parse; falls back to now (UTC) so the alert
    window degrades gracefully instead of failing the whole pack."""
    if raw:
        try:
            dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except (ValueError, TypeError):
            pass
    return datetime.now(timezone.utc)


def _decode_jwt_claims(jwt_form: str | None) -> dict | None:
    """Decode (NOT verify) the payload segment of a capability token.
    Reuses the token service's decoder so the two can never drift."""
    if not jwt_form:
        return None
    try:
        from app.services.capability_tokens import _decode_payload
        return _decode_payload(jwt_form)
    except Exception:
        return None


def _capability_chain(sb, leaf_token_hash: str | None) -> list[dict]:
    """Walk the capability chain leaf-to-root via parent_token_hash.

    Each link carries the stored authorization facts (scope, side-effect
    class, spend limit, allowlist, expiry) plus revocation status and the
    decoded (unverified) JWT claims. Cycle-safe: a revisited hash or a
    depth over _MAX_CHAIN_DEPTH terminates the walk. A token_hash that is
    not in the registry is reported as found=False rather than silently
    dropped — an auditor should see the gap.
    """
    chain: list[dict] = []
    seen: set[str] = set()
    cursor = leaf_token_hash
    while cursor and cursor not in seen and len(chain) < _MAX_CHAIN_DEPTH:
        seen.add(cursor)
        res = (
            sb.table("capability_tokens")
            .select(
                "token_hash, jwt_form, parent_token_hash, revoked_at, scope,"
                " spend_limit_usd, merchant_allowlist, side_effect_class,"
                " issued_at, expires_at"
            )
            .eq("token_hash", cursor)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        if not rows:
            chain.append({"token_hash": cursor, "found": False})
            break
        t = rows[0]
        chain.append(
            {
                "token_hash": t.get("token_hash"),
                "found": True,
                "jwt_form": t.get("jwt_form"),
                "claims": _decode_jwt_claims(t.get("jwt_form")),
                "scope": t.get("scope"),
                "side_effect_class": t.get("side_effect_class"),
                "spend_limit_usd": t.get("spend_limit_usd"),
                "merchant_allowlist": t.get("merchant_allowlist"),
                "issued_at": t.get("issued_at"),
                "expires_at": t.get("expires_at"),
                "revoked": t.get("revoked_at") is not None,
                "revoked_at": t.get("revoked_at"),
                "parent_token_hash": t.get("parent_token_hash"),
            }
        )
        cursor = t.get("parent_token_hash")
    return chain


def _session_alerts(sb, agent_id: str | None, around: datetime) -> list[dict]:
    """Signed session-alert envelopes for the same agent within ±24h of the
    receipt timestamp. Optional context — best-effort, never fails the pack."""
    if not agent_id:
        return []
    try:
        start = (around - timedelta(hours=_ALERT_WINDOW_HOURS)).isoformat()
        end = (around + timedelta(hours=_ALERT_WINDOW_HOURS)).isoformat()
        res = (
            sb.table("session_alerts")
            .select("envelope_json, created_at")
            .eq("agent_id", agent_id)
            .gte("created_at", start)
            .lte("created_at", end)
            .order("created_at")
            .limit(_MAX_ALERTS)
            .execute()
        )
        return [r["envelope_json"] for r in (res.data or []) if r.get("envelope_json")]
    except Exception:
        logger.warning("evidence_pack: session_alerts lookup failed (agent=%s)", agent_id)
        return []


_OFFLINE_STEPS = [
    "1. Verify the pack signature: remove the 'signature' and "
    "'verification_key_id' fields from this document, serialize the remainder "
    "as canonical JSON (keys sorted, separators ',' and ':', ASCII-escaped), "
    "SHA-256 the UTF-8 bytes, and verify the ECDSA-secp256k1 signature "
    "against the public key whose key_id equals verification_key_id in the "
    "embedded key_registry.",
    "2. Verify the receipt signature the same way: remove 'signature' and "
    "'verification_key_id' from the 'receipt' object, canonicalize, SHA-256, "
    "and verify against the same key registry.",
    "3. If merkle_proof is present, recompute the leaf as "
    "SHA-256(0x00 || output_hash bytes) and fold the proof upward with "
    "node = SHA-256(0x01 || left || right) per the recorded positions; the "
    "result must equal merkle_proof.merkle_root.",
    "4. Check the root on-chain without trusting GARL: call "
    "MerkleAnchor.verifyProof with merkle_proof.verify_proof_args at "
    "anchor.contract_address on anchor.chain_id (Base mainnet = 8453), or "
    "read roots(batchId) and compare to anchor.merkle_root; cross-check "
    "anchor.tx_hash on the block explorer (anchor.explorer_url).",
    "5. Cross-check the embedded key_registry against the live registry at "
    "https://api.garl.ai/.well-known/garl-keys.json — a mismatch means keys "
    "rotated after export (retired keys remain listed) or the pack was "
    "tampered with.",
]


# ──────────────────────────────────────────────────────────────────────
# Pack builder
# ──────────────────────────────────────────────────────────────────────

def build_evidence_pack(receipt_id_or_hash: str) -> dict | None:
    """Build and sign an Evidence Pack for one receipt.

    Accepts a receipt_id (UUID) or an output_hash (64-hex). Returns None if
    the receipt is unknown. merkle_proof/anchor are null for receipts not
    yet anchored on-chain — the pack states what is true at export time.
    """
    rid = (receipt_id_or_hash or "").strip()
    if not rid:
        return None

    sb = _get_supabase()
    col = "output_hash" if _is_hex64(rid) else "receipt_id"
    val = rid.lower() if col == "output_hash" else rid

    res = (
        sb.table("receipts")
        .select(
            "receipt_id, agent_id, envelope_json, capability_token_hash,"
            " merkle_batch_id, anchored_at, created_at"
        )
        .eq(col, val)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        return None
    row = rows[0]
    envelope = row.get("envelope_json") or {}

    proof = build_inclusion_proof(row["receipt_id"])
    anchor = None
    if proof:
        anchor = {
            "chain_id": proof.get("chain_id"),
            "contract_address": proof.get("contract_address"),
            "tx_hash": proof.get("tx_hash"),
            "merkle_root": proof.get("merkle_root"),
            "anchored_at": proof.get("anchored_at"),
            "explorer_url": (
                f"https://basescan.org/tx/{proof['tx_hash']}"
                if proof.get("chain_id") == 8453 and proof.get("tx_hash")
                else None
            ),
        }

    receipt_ts = _parse_ts(envelope.get("timestamp") or row.get("created_at"))

    pack: dict = {
        "version": EVIDENCE_PACK_VERSION,
        "generated_at": _now_rfc3339z(),
        "issuer": "https://api.garl.ai",
        "receipt": envelope,
        "capability_chain": _capability_chain(sb, row.get("capability_token_hash")),
        "merkle_proof": proof,
        "anchor": anchor,
        "session_alerts": _session_alerts(sb, row.get("agent_id"), receipt_ts),
        "key_registry": get_key_registry(),
        "verification": {"offline_steps": list(_OFFLINE_STEPS)},
        "retention": {
            "policy": (
                "receipts and packs are append-only; retain the exported pack "
                ">= 6 months per Art. 19(1)"
            ),
            "exported_by": None,
        },
    }

    # Sign the pack-without-signature, then attach (same pattern as receipts).
    signature, _digest = sign_payload(pack)
    pack["signature"] = signature
    pack["verification_key_id"] = get_active_key_id()
    return pack


# ──────────────────────────────────────────────────────────────────────
# PDF rendering
# ──────────────────────────────────────────────────────────────────────

def _t(value) -> str:
    """Latin-1-safe text for fpdf2 core fonts. None -> '-'."""
    if value is None or value == "":
        return "-"
    s = str(value)
    return s.encode("latin-1", "replace").decode("latin-1")


def _short(h, keep: int = 16) -> str:
    """Truncated hash for the summary tables; full values go in the appendix."""
    if not h or not isinstance(h, str):
        return "-"
    return h if len(h) <= keep else h[:keep] + "..."


def render_evidence_pack_pdf(pack: dict) -> bytes:
    """Render a pack as a clean, factual A4 PDF. Labels and values only —
    no marketing copy. Returns raw PDF bytes."""
    from fpdf import FPDF

    receipt = pack.get("receipt") or {}
    chain = pack.get("capability_chain") or []
    proof = pack.get("merkle_proof") or {}
    anchor = pack.get("anchor") or {}
    alerts = pack.get("session_alerts") or []
    steps = (pack.get("verification") or {}).get("offline_steps") or []
    retention = pack.get("retention") or {}

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_title("GARL Evidence Pack")
    pdf.add_page()

    def heading(text: str):
        pdf.set_font("Helvetica", "B", 11)
        pdf.ln(3)
        pdf.cell(0, 6, _t(text), new_x="LMARGIN", new_y="NEXT")
        pdf.set_draw_color(120, 120, 120)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
        pdf.ln(1.5)

    def kv(label: str, value):
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(50, 4.6, _t(label))
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.6, _t(value), new_x="LMARGIN", new_y="NEXT")

    def mono_block(label: str, value):
        pdf.set_font("Helvetica", "B", 8)
        pdf.cell(0, 4.6, _t(label), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Courier", "", 7)
        pdf.multi_cell(0, 3.8, _t(value), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    # ── Title ──
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 9, "GARL Evidence Pack", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 8)
    pdf.cell(0, 4.6, _t(f"{pack.get('version', '')}  -  generated {pack.get('generated_at', '')}  -  issuer {pack.get('issuer', '')}"),
             new_x="LMARGIN", new_y="NEXT")

    # ── Receipt summary ──
    heading("Receipt")
    kv("receipt_id", receipt.get("receipt_id"))
    kv("agent DID", receipt.get("agent_identity"))
    kv("human_delegate", receipt.get("human_delegate"))
    kv("action_type", receipt.get("action_type"))
    kv("side_effect", receipt.get("side_effect"))
    kv("runtime / protocol", f"{receipt.get('runtime', '-')} / {receipt.get('protocol', '-')}")
    kv("tool_server", receipt.get("tool_server"))
    kv("policy_decision", receipt.get("policy_decision"))
    kv("timestamp", receipt.get("timestamp"))
    kv("input_hash", _short(receipt.get("input_hash")))
    kv("output_hash", _short(receipt.get("output_hash")))
    if receipt.get("previous_receipt_hash"):
        kv("previous_receipt_hash", _short(receipt.get("previous_receipt_hash")))
    if receipt.get("hash_scheme"):
        hs = receipt["hash_scheme"]
        kv("hash_scheme", f"input={hs.get('input', '-')} output={hs.get('output', '-')}")
    if receipt.get("attestations"):
        kv("attestations", "; ".join(str(a) for a in receipt["attestations"]))
    kv("receipt signature", _short(receipt.get("signature"), 24))
    kv("verification_key_id", receipt.get("verification_key_id"))

    # ── Authorization (capability chain) ──
    heading("Authorization - capability chain (leaf to root)")
    if not chain:
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(0, 4.6, "No capability token recorded for this receipt.",
                       new_x="LMARGIN", new_y="NEXT")
    else:
        for i, link in enumerate(chain):
            pdf.set_font("Helvetica", "B", 8)
            pdf.cell(0, 4.6, _t(f"Link {i} - token {_short(link.get('token_hash'))}"),
                     new_x="LMARGIN", new_y="NEXT")
            if not link.get("found", True):
                pdf.set_font("Helvetica", "", 8)
                pdf.multi_cell(0, 4.6, "Token hash not present in the capability registry.",
                               new_x="LMARGIN", new_y="NEXT")
                continue
            allow = link.get("merchant_allowlist")
            kv("  scope", link.get("scope"))
            kv("  side_effect_class", link.get("side_effect_class"))
            kv("  spend_limit_usd", link.get("spend_limit_usd"))
            kv("  merchant_allowlist", ", ".join(allow) if allow else None)
            kv("  issued_at / expires_at", f"{link.get('issued_at') or '-'} / {link.get('expires_at') or '-'}")
            kv("  revoked", f"yes ({link.get('revoked_at')})" if link.get("revoked") else "no")

    # ── Anchoring ──
    heading("On-chain anchoring")
    if anchor:
        kv("merkle_root", _short(anchor.get("merkle_root"), 24))
        kv("chain_id", anchor.get("chain_id"))
        kv("contract_address", anchor.get("contract_address"))
        kv("tx_hash", _short(anchor.get("tx_hash"), 24))
        kv("anchored_at", anchor.get("anchored_at"))
        kv("explorer_url", anchor.get("explorer_url"))
        if proof:
            kv("leaf_index / batch size", f"{proof.get('leaf_index', '-')} / {proof.get('receipt_count', '-')}")
    else:
        pdf.set_font("Helvetica", "", 8)
        pdf.multi_cell(
            0, 4.6,
            "Not anchored on-chain at export time. The receipt signature above "
            "still verifies offline; the Merkle inclusion proof becomes "
            "available after the next anchoring batch.",
            new_x="LMARGIN", new_y="NEXT",
        )

    # ── Session alerts ──
    heading("Session alerts (same agent, +/- 24h)")
    pdf.set_font("Helvetica", "", 8)
    if not alerts:
        pdf.multi_cell(0, 4.6, "None recorded in the window.",
                       new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.multi_cell(0, 4.6, _t(f"{len(alerts)} signed alert envelope(s) included in the JSON pack:"),
                       new_x="LMARGIN", new_y="NEXT")
        for a in alerts[:20]:
            if isinstance(a, dict):
                pdf.multi_cell(
                    0, 4.6,
                    _t(f"  - {a.get('rule', 'unknown')} [{a.get('severity', '-')}] {a.get('created_at') or a.get('timestamp') or ''}"),
                    new_x="LMARGIN", new_y="NEXT",
                )

    # ── Verification instructions ──
    heading("Offline verification steps")
    pdf.set_font("Helvetica", "", 8)
    for step in steps:
        pdf.multi_cell(0, 4.4, _t(step), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(0.6)

    # ── Retention ──
    heading("Retention")
    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4.6, _t(retention.get("policy")), new_x="LMARGIN", new_y="NEXT")

    # ── Appendix: full values ──
    pdf.add_page()
    heading("Appendix - full values")
    if receipt.get("input_hash"):
        mono_block("receipt.input_hash", receipt.get("input_hash"))
    if receipt.get("output_hash"):
        mono_block("receipt.output_hash", receipt.get("output_hash"))
    if receipt.get("previous_receipt_hash"):
        mono_block("receipt.previous_receipt_hash", receipt.get("previous_receipt_hash"))
    if receipt.get("signature"):
        mono_block("receipt.signature", receipt.get("signature"))
    for i, link in enumerate(chain):
        if link.get("token_hash"):
            mono_block(f"capability_chain[{i}].token_hash", link.get("token_hash"))
    if anchor:
        mono_block("anchor.merkle_root", anchor.get("merkle_root"))
        mono_block("anchor.tx_hash", anchor.get("tx_hash"))
    if proof.get("leaf"):
        mono_block("merkle_proof.leaf", proof.get("leaf"))

    # ── Footer: pack signature ──
    heading("Pack signature")
    mono_block(
        f"ECDSA-secp256k1 over canonical pack (key_id {pack.get('verification_key_id', '-')})",
        pack.get("signature"),
    )

    out = pdf.output()
    return bytes(out)
