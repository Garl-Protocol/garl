"""HTTP endpoints for the GARL PR Bot.

Two surfaces:

1. ``POST /api/v1/pr-bot/webhook`` — the one endpoint GitHub's App
   installation points at. Every request is gated by HMAC validation
   (webhook secret) + per-repo rate limit. The handler runs in a
   daemon thread so we can ACK GitHub's 10-second SLA immediately
   while commit fetch + GitHub API calls proceed in the background.
   Every round persists a summary row to ``pr_bot_summaries`` so the
   ``/pr`` landing page can render without calling back into GitHub.

2. ``GET /api/v1/pr-bot/summary/{owner}/{repo}/{pr_number}`` — public
   JSON endpoint the Next.js ``/pr/{owner}/{repo}/{pr}`` page (and the
   sticky comment's "Verify all →" link) read from. Returns the last
   stored summary or 404.
"""
from __future__ import annotations

import logging
import os
import threading
from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException, Request

from app.core.supabase_client import get_supabase
from app.services.pr_bot import (
    GitHubAppClient,
    PerRepoRateLimiter,
    PrBotHandler,
    verify_github_signature,
)

logger = logging.getLogger("garl.pr_bot.routes")

pr_bot_router = APIRouter(prefix="/api/v1/pr-bot", tags=["PR Bot"])

_rate_limiter = PerRepoRateLimiter(max_events=30, window_seconds=60)
_app_client_singleton: GitHubAppClient | None = None


def _get_app_client() -> GitHubAppClient:
    global _app_client_singleton
    if _app_client_singleton is None:
        _app_client_singleton = GitHubAppClient()
    return _app_client_singleton


def _persist_summary(owner: str, repo: str, pr_number: int, summary: dict) -> None:
    try:
        db = get_supabase()
        now = datetime.now(timezone.utc).isoformat()
        db.table("pr_bot_summaries").upsert(
            {
                "owner": owner.lower(),
                "repo": repo.lower(),
                "pr_number": pr_number,
                "ai_percentage": float(summary.get("ai_percentage", 0.0)),
                "ai_commits": int(summary.get("ai_commits", 0)),
                "total_commits": int(summary.get("total_commits", 0)),
                "model_counts": summary.get("model_counts") or {},
                "updated_at": now,
            },
            on_conflict="owner,repo,pr_number",
        ).execute()
    except Exception as e:  # noqa: BLE001
        logger.warning("pr_bot_summaries upsert failed for %s/%s#%s: %s", owner, repo, pr_number, e)


def _run_handler_in_background(payload: dict) -> None:
    try:
        handler = PrBotHandler(_get_app_client(), rate_limiter=_rate_limiter)
        result = handler.handle_pull_request_event(payload)
        if result.get("status") == "ok":
            repo = payload.get("repository") or {}
            owner = (repo.get("owner") or {}).get("login", "")
            name = repo.get("name", "")
            pr_number = (payload.get("pull_request") or {}).get("number")
            if owner and name and pr_number:
                _persist_summary(owner, name, int(pr_number), result["summary"])
    except Exception as e:  # noqa: BLE001
        logger.exception("pr_bot handler crashed: %s", e)


@pr_bot_router.post("/webhook", summary="GitHub App webhook receiver")
async def pr_bot_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(default=None),
    x_github_event: str | None = Header(default=None),
) -> dict:
    """GitHub App webhook endpoint. Validates HMAC, dispatches handler
    off-thread, ACKs within milliseconds."""
    secret = os.environ.get("GITHUB_APP_WEBHOOK_SECRET", "")
    if not secret:
        # In production we refuse to process webhooks without a secret;
        # in dev/debug we still 202 so the endpoint can be exercised.
        logger.warning("pr-bot webhook received but GITHUB_APP_WEBHOOK_SECRET is not set")
        raise HTTPException(status_code=503, detail="PR bot webhook secret not configured")

    body = await request.body()
    if not verify_github_signature(body, x_hub_signature_256, secret):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    if x_github_event == "ping":
        return {"ok": True, "event": "ping"}

    if x_github_event != "pull_request":
        return {"ok": True, "event": x_github_event, "ignored": True}

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="invalid JSON payload")

    threading.Thread(
        target=_run_handler_in_background,
        args=(payload,),
        daemon=True,
    ).start()

    return {"ok": True, "queued": True}


@pr_bot_router.get(
    "/summary/{owner}/{repo}/{pr_number}",
    summary="Latest stored AI-authorship summary for a PR",
)
async def pr_bot_summary(owner: str, repo: str, pr_number: int) -> dict:
    db = get_supabase()
    res = (
        db.table("pr_bot_summaries")
        .select("*")
        .eq("owner", owner.lower())
        .eq("repo", repo.lower())
        .eq("pr_number", pr_number)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="No summary stored for this PR yet")
    row = rows[0]
    return {
        "owner": row["owner"],
        "repo": row["repo"],
        "pr_number": row["pr_number"],
        "ai_percentage": float(row["ai_percentage"]),
        "ai_commits": int(row["ai_commits"]),
        "total_commits": int(row["total_commits"]),
        "model_counts": row.get("model_counts") or {},
        "updated_at": row.get("updated_at"),
        "verify_url": f"https://garl.ai/pr/{row['owner']}/{row['repo']}/{row['pr_number']}",
    }
