"""Move stale zero-trace agents to sandbox.

Zero-trace agents registered more than N days ago almost always belong
to one of two classes:
  1. Test fixtures we (or an integrator) forgot to clean up.
  2. Speculative auto-registrations that never submitted a trace.
Either way they shouldn't fill the public leaderboard. This script
flips `is_sandbox=true` on any such row. Sandbox agents are already
filtered out by `get_leaderboard`, `search_agents`, and `get_stats`.

Usage:

    set -a && source backend/.env && set +a
    python3.11 scripts/mark_stale_as_sandbox.py --older-than-days 7 --dry-run
    python3.11 scripts/mark_stale_as_sandbox.py --older-than-days 7

Idempotent: rows already `is_sandbox=true` are skipped. Deleted agents
are untouched. Agents with at least one trace are untouched regardless
of registration date.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.supabase_client import get_supabase  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="Mark stale zero-trace agents as sandbox")
    p.add_argument("--older-than-days", type=int, default=7)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=args.older_than_days)).isoformat()
    db = get_supabase()

    res = (
        db.table("agents")
        .select("id,name,created_at,total_traces,is_sandbox,is_deleted")
        .eq("is_deleted", False)
        .eq("is_sandbox", False)
        .eq("total_traces", 0)
        .lt("created_at", cutoff)
        .execute()
    )
    rows = res.data or []
    print(json.dumps({"candidates": len(rows), "cutoff": cutoff, "dry_run": args.dry_run}))

    if args.dry_run:
        for r in rows:
            print(json.dumps({"id": r["id"], "name": r["name"], "created_at": r["created_at"]}))
        return 0

    moved = 0
    for r in rows:
        try:
            db.table("agents").update({"is_sandbox": True}).eq("id", r["id"]).execute()
            moved += 1
        except Exception as e:  # noqa: BLE001
            print(f"failed id={r['id']}: {e}", file=sys.stderr)
    print(json.dumps({"moved": moved, "total_candidates": len(rows)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
