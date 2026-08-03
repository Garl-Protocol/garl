#!/usr/bin/env python3
"""ERC-8004 <-> GARL format-compat demo. Read-only against the live API.

    python3 compat_demo.py <agent-uuid>

Fetches the agent's ERC-8004 metadata + feedback from GARL, validates the
shapes, and prints the write-side payloads an ERC-8004 integrator would
submit to the Identity/Reputation registries. stdlib only.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request

API = os.environ.get("GARL_API_URL", "https://api.garl.ai/api/v1")


def _get(path: str) -> dict:
    req = urllib.request.Request(
        f"{API}{path}", headers={"User-Agent": "garl-interop-demo/1.0"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.load(resp)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    agent_id = sys.argv[1]

    # ---- read side: identity ------------------------------------------------
    meta = _get(f"/agents/{agent_id}/erc8004")
    for key in ("type", "name", "services", "supportedTrust", "garl"):
        assert key in meta, f"erc8004 metadata missing {key!r}"
    print("== ERC-8004 agent metadata (identity shape) ==")
    print(json.dumps(meta, indent=2)[:1200], "…\n")

    # ---- read side: reputation ----------------------------------------------
    feedback = _get(f"/agents/{agent_id}/erc8004/feedback")
    assert feedback.get("format") == "erc8004-reputation-v1", feedback.get("format")
    print("== ERC-8004 reputation feedback ==")
    print(json.dumps(feedback, indent=2)[:1200], "…\n")

    # ---- write side: payloads an integrator would submit --------------------
    garl = meta.get("garl", {})
    identity_registration = {
        "_target": "ERC-8004 Identity Registry (register/update)",
        "agentId": garl.get("sovereign_id", f"did:garl:{agent_id}"),
        "agentURI": f"{API}/agents/{agent_id}/erc8004",
    }
    reputation_feedback = {
        "_target": "ERC-8004 Reputation Registry (giveFeedback shape)",
        "agentId": garl.get("sovereign_id", f"did:garl:{agent_id}"),
        "score": garl.get("trust_score"),
        "tag": garl.get("certification_tier"),
        # Evidence over assertion: point at a re-verifiable signed receipt,
        # not a bare number (see README — the anti-farming rationale).
        "evidenceURI": f"{API}/receipts/{{output_hash}}/cert.json",
        "proofURI": f"{API}/receipts/{{receipt_id}}/proof",
    }
    print("== write-side payloads ==")
    print(json.dumps(identity_registration, indent=2))
    print(json.dumps(reputation_feedback, indent=2))
    print("\nformat compatibility: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
