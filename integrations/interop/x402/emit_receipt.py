#!/usr/bin/env python3
"""x402 -> GARL: emit a payment Action Receipt usable as proofOfPayment.

Runnable two ways:
  online : GARL_API_KEY + GARL_AGENT_ID set -> issues a scoped capability
           token, submits the receipt, prints the proofOfPayment block.
  offline: no credentials (or --offline) -> builds the same envelope shape
           locally and prints it without submitting.

stdlib only (urllib); no SDK required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import urllib.request
import uuid
from datetime import datetime, timezone

API = os.environ.get("GARL_API_URL", "https://api.garl.ai/api/v1")


def _post(path: str, body: dict, api_key: str | None = None) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "garl-interop-demo/1.0",
            **({"x-api-key": api_key} if api_key else {}),
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def sha256_canonical(obj: dict) -> str:
    """Plain content hash of a canonical-JSON payload (canonical-json-v0.1).
    Used here for the x402 settlement metadata, which is non-personal
    machine data — hence the explicit non_personal_payload declaration.
    For personal payloads use the keyed hash instead (GET /agents/{id}/hash-key)."""
    canonical = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--merchant", required=True, help="merchant host, e.g. api.example-seller.com")
    ap.add_argument("--amount-usd", type=float, required=True)
    ap.add_argument("--offline", action="store_true", help="build only, don't submit")
    args = ap.parse_args()

    api_key = os.environ.get("GARL_API_KEY")
    agent_id = os.environ.get("GARL_AGENT_ID")
    offline = args.offline or not (api_key and agent_id)

    # The x402 settlement we are receipting (in a real integration this is
    # the settlement response you got from the x402 facilitator).
    settlement = {
        "x402_version": 1,
        "merchant": args.merchant,
        "amount_usd": args.amount_usd,
        "settled_at": datetime.now(timezone.utc).isoformat(),
        "settlement_ref": str(uuid.uuid4()),
    }
    payment_request = {"merchant": args.merchant, "max_amount_usd": args.amount_usd}

    receipt_body = {
        "agent_id": agent_id or "<your-agent-uuid>",
        "runtime": "custom",
        "protocol": "x402",
        "action_type": "payment",
        "tool_server": f"https://{args.merchant}",
        "input_hash": sha256_canonical(payment_request),
        "output_hash": sha256_canonical(settlement),
        "side_effect": "irreversible",
        "cost": {"usd": args.amount_usd},
        "hash_scheme": {"input": "sha256", "output": "sha256"},
        "non_personal_payload": True,  # machine settlement metadata only
    }

    if offline:
        print("# offline mode — envelope request that WOULD be submitted:")
        print(json.dumps(receipt_body, indent=2))
        proof_of_payment = {
            "type": "garl/action-receipt/v0.1",
            "uri": f"{API}/receipts/{receipt_body['output_hash']}/cert.json",
            "hash": receipt_body["output_hash"],
            "proof_uri": f"{API}/receipts/<receipt_id>/proof",
        }
        print("\n# proofOfPayment block (ERC-8004 validation record / x402 metadata):")
        print(json.dumps(proof_of_payment, indent=2))
        return 0

    # 1. scope a capability token to exactly this payment
    token = _post("/capability/issue", {
        "agent_id": agent_id,
        "scope": f"payment:{args.merchant}",
        "side_effect_class": "irreversible",
        "spend_limit_usd": args.amount_usd,
        "merchant_allowlist": [args.merchant],
        "expires_in_seconds": 900,
    }, api_key)
    receipt_body["capability_token_hash"] = token["token_hash"]
    print(f"capability token: {token['token_hash'][:16]}… scope=payment:{args.merchant} "
          f"limit=${args.amount_usd}", file=sys.stderr)

    # 2. the signed receipt
    envelope = _post("/receipts", receipt_body, api_key)
    print(f"receipt: {envelope['receipt_id']} signed by key {envelope['verification_key_id']}",
          file=sys.stderr)

    # 3. the proofOfPayment object
    proof_of_payment = {
        "type": "garl/action-receipt/v0.1",
        "uri": f"{API}/receipts/{envelope['output_hash']}/cert.json",
        "hash": envelope["output_hash"],
        "proof_uri": f"{API}/receipts/{envelope['receipt_id']}/proof",
    }
    print(json.dumps(proof_of_payment, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
