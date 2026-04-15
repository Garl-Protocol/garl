"""One-shot backfill: re-sign pre-v0.3 traces (certificate={} or NULL).

Writes an in-toto-style envelope into the `certificate` JSONB column so
downstream consumers see `signing_epoch == "backfilled"` and can treat
these receipts differently from original-sign chain-of-custody records.

Run from repo root with canonical signing key set:

    SUPABASE_URL=... \\
    SUPABASE_SERVICE_ROLE_KEY=... \\
    SIGNING_PRIVATE_KEY_HEX=... \\
    python3.11 scripts/backfill_unsigned_traces.py --limit 1000 --dry-run

Drop `--dry-run` to write. The script skips rows that already have a
non-empty certificate — safe to re-run.

NOTE: the traces table has BEFORE UPDATE triggers that reject DML
updates to the certificate column once it's written. This backfill
requires temporarily lowering the trigger via a coordinated Supabase
migration, or running it BEFORE the trigger was added (which is no
longer possible). On production, prefer running as the `service_role`
bypass — Supabase's service role owns the table and the trigger raises
only for non-owner sessions. If that still fails, the migration path
below spells out the one-shot unlock.

    -- one_shot_backfill_unlock.sql (apply, backfill, re-apply)
    ALTER TABLE public.traces DISABLE TRIGGER traces_immutable_update;
    -- run this script
    ALTER TABLE public.traces ENABLE TRIGGER traces_immutable_update;
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Import backend app modules by adding backend/ to sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND = REPO_ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.signing import sign_trace, derive_key_id, get_public_key_hex  # noqa: E402
from app.core.supabase_client import get_supabase  # noqa: E402


def build_backfill_cert(row: dict) -> dict:
    """Construct a fresh certificate honestly labelled as backfilled."""
    payload = {
        "trace_id": row.get("id"),
        "agent_id": row.get("agent_id"),
        "task_description": row.get("task_description") or "",
        "status": row.get("status") or "",
        "duration_ms": row.get("duration_ms") or 0,
        "category": row.get("category") or "other",
    }
    cert = sign_trace(payload)
    # Overlay a backfill marker inside proof. Verifiers can drop records
    # with this marker from strict chain-of-custody calculations.
    cert["proof"]["signing_epoch"] = "backfilled"
    cert["proof"]["backfilled_at"] = int(time.time())
    return cert


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill unsigned GARL traces")
    parser.add_argument("--limit", type=int, default=1000, help="max rows per pass")
    parser.add_argument("--dry-run", action="store_true", help="report only, do not write")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    db = get_supabase()
    public_key_hex = get_public_key_hex()
    key_id = derive_key_id(public_key_hex)
    print(f"active signer key_id={key_id}")
    print(f"dry_run={args.dry_run} limit={args.limit}")

    res = (
        db.table("traces")
        .select("id,agent_id,task_description,status,duration_ms,category,trace_hash,certificate")
        .or_("certificate.is.null,certificate.eq.{}")
        .limit(args.limit)
        .execute()
    )
    rows = res.data or []
    print(f"rows_to_backfill={len(rows)}")
    if not rows:
        return 0

    updated = 0
    skipped = 0
    failed = 0
    for row in rows:
        cert = row.get("certificate") or {}
        if isinstance(cert, dict) and cert.get("proof"):
            skipped += 1
            continue
        new_cert = build_backfill_cert(row)
        if args.verbose:
            print(json.dumps({"id": row["id"], "trace_hash": row.get("trace_hash"), "new_key_id": key_id}))
        if args.dry_run:
            updated += 1
            continue
        try:
            db.table("traces").update({"certificate": new_cert}).eq("id", row["id"]).execute()
            updated += 1
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"failed id={row['id']}: {e}", file=sys.stderr)

    print(json.dumps({"updated": updated, "skipped": skipped, "failed": failed, "dry_run": args.dry_run}))
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
