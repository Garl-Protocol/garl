#!/usr/bin/env python3
"""Run the session-level behavioral scan (session_anomaly rules) over every
agent active in the last 24h and print a summary.

Operator-/cron-driven (see .github/workflows/session-scan.yml). Reads config
from env:
  SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY  — DB access (read receipts/tokens,
                                             write session_alerts)
  SIGNING_PRIVATE_KEY_HEX                  — alert envelopes are SIGNED with
                                             the production receipt key; an
                                             unsigned alert is worthless as
                                             evidence, so this is required.

Idempotency: alerts dedupe per (agent_id, rule) inside a 6h window, so
re-runs do not spam duplicates. Exits 0 when there is nothing to flag.
"""
from __future__ import annotations

import os
import sys

# Make the FastAPI backend importable so the scan uses the exact same rule +
# signing code the API serves (no divergence between cron and API results).
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))


def _require(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        sys.exit(f"Missing required env var: {name}")
    return v


def main() -> int:
    _require("SUPABASE_URL")
    _require("SUPABASE_SERVICE_ROLE_KEY")
    _require("SIGNING_PRIVATE_KEY_HEX")

    from app.services.session_anomaly import run_session_scan  # noqa: E402

    result = run_session_scan()
    alerts = result["alerts"]
    print(
        f"Scanned {result['scanned']} active agent(s) over the last "
        f"{result['window_hours']}h — {len(alerts)} alert(s) minted."
    )
    for a in alerts:
        print(f"  [{a['severity']}] {a['rule']} {a['agent_identity']}: {a['summary']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
