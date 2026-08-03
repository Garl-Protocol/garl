#!/usr/bin/env python3
"""AP2 -> GARL: map an Intent Mandate + Cart Mandate onto a capability-token
delegation chain (intent = parent, cart = attenuated child).

Offline by default (prints the two /capability/issue requests); with
--issue and GARL_API_KEY/GARL_AGENT_ID it mints both tokens for real and
prints their token_hashes. stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

API = os.environ.get("GARL_API_URL", "https://api.garl.ai/api/v1")


def _post(path: str, body: dict, api_key: str) -> dict:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "x-api-key": api_key,
                 "User-Agent": "garl-interop-demo/1.0"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def _seconds_until(iso_ts: str, cap: int) -> int:
    try:
        dt = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
        remaining = int((dt - datetime.now(timezone.utc)).total_seconds())
        return max(60, min(remaining, cap))
    except ValueError:
        return 3600


def build_requests(mandate: dict, agent_id: str) -> tuple[dict, dict]:
    intent = mandate["intent_mandate"]
    cart = mandate["cart_mandate"]

    # Intent Mandate -> parent token: the user's broad, bounded authority.
    intent_req = {
        "agent_id": agent_id,
        "scope": "payment:*",
        "side_effect_class": "irreversible",
        "spend_limit_usd": intent["price_ceiling_usd"],
        "merchant_allowlist": sorted(intent["merchants"]),
        "expires_in_seconds": _seconds_until(intent["intent_expiry"], 7 * 24 * 3600),
        "caveats": [
            {"ap2": "intent", "description": intent["natural_language_description"]},
            {"ap2": "cart_confirmation_required",
             "value": bool(intent.get("user_cart_confirmation_required", True))},
        ],
        "human_delegate": cart.get("user_ref"),
    }

    # Cart Mandate -> child token: attenuated to exactly the approved cart.
    # Every field narrows (spec §5) — the issuer rejects it otherwise.
    cart_req = {
        "agent_id": agent_id,
        "scope": f"payment:{cart['merchant']}",
        "side_effect_class": "irreversible",
        "spend_limit_usd": cart["cart_total_usd"],
        "merchant_allowlist": [cart["merchant"]],
        "expires_in_seconds": _seconds_until(cart["cart_expiry"], 3600),
        "caveats": intent_req["caveats"] + [
            {"ap2": "cart", "items": cart["items"], "total_usd": cart["cart_total_usd"],
             "user_approved": bool(cart.get("user_approved"))},
        ],
        "human_delegate": cart.get("user_ref"),
        # parent_token_hash injected after the parent is issued
    }
    return intent_req, cart_req


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mandate_file")
    ap.add_argument("--issue", action="store_true", help="actually mint both tokens")
    args = ap.parse_args()

    mandate = json.load(open(args.mandate_file))
    api_key = os.environ.get("GARL_API_KEY")
    agent_id = os.environ.get("GARL_AGENT_ID", "<your-agent-uuid>")

    intent_req, cart_req = build_requests(mandate, agent_id)

    if not (args.issue and api_key and agent_id != "<your-agent-uuid>"):
        print("# offline — POST /api/v1/capability/issue (intent mandate -> parent):")
        print(json.dumps(intent_req, indent=2))
        print("\n# then (cart mandate -> child; add parent_token_hash from the response):")
        print(json.dumps(cart_req, indent=2))
        return 0

    parent = _post("/capability/issue", intent_req, api_key)
    print(f"intent token: {parent['token_hash']}", file=sys.stderr)

    cart_req["parent_token_hash"] = parent["token_hash"]
    child = _post("/capability/issue", cart_req, api_key)
    print(f"cart token:   {child['token_hash']} (parent={parent['token_hash'][:16]}…)",
          file=sys.stderr)

    print(json.dumps({
        "intent_token_hash": parent["token_hash"],
        "cart_token_hash": child["token_hash"],
        "use_in_receipt": {"capability_token_hash": child["token_hash"]},
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
