#!/usr/bin/env python3
"""Execute seed SQL files via Supabase REST API (service role)."""
import httpx
import os
import sys

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")

if not SUPABASE_URL or not SERVICE_KEY:
    print("ERROR: Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY environment variables.")
    sys.exit(1)

FILES = [
    "/tmp/garl_seed_agents.sql",
    "/tmp/garl_seed_traces.sql",
    "/tmp/garl_seed_history.sql",
]

def run_sql_batch(sql: str, label: str):
    """Run SQL via Supabase's pg REST endpoint."""
    headers = {
        "apikey": SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }
    resp = httpx.post(
        f"{SUPABASE_URL}/rest/v1/rpc/",
        headers=headers,
        json={"query": sql},
        timeout=60.0,
    )
    if resp.status_code < 300:
        print(f"  ✓ {label}")
    else:
        print(f"  ✗ {label}: {resp.status_code} {resp.text[:200]}")

def main():
    for filepath in FILES:
        print(f"\nProcessing: {filepath}")
        with open(filepath) as f:
            lines = f.readlines()
        
        batch_size = 10
        for i in range(0, len(lines), batch_size):
            batch = "".join(lines[i:i+batch_size])
            label = f"  rows {i+1}-{min(i+batch_size, len(lines))}"
            
            headers = {
                "apikey": SERVICE_KEY,
                "Authorization": f"Bearer {SERVICE_KEY}",
                "Content-Type": "text/plain",
            }
            resp = httpx.post(
                f"{SUPABASE_URL}/pg",
                headers=headers,
                content=batch,
                timeout=60.0,
            )
            if resp.status_code < 300:
                print(f"  ✓ rows {i+1}-{min(i+batch_size, len(lines))}")
            else:
                print(f"  ✗ rows {i+1}-{min(i+batch_size, len(lines))}: {resp.status_code}")
                print(f"    {resp.text[:300]}")
                return False
        
        print(f"  Done: {len(lines)} rows")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
