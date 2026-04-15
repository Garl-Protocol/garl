"""High-level PR webhook handler.

Given a validated `pull_request` event payload and a configured
GitHubAppClient, this module:

  1. Rate-limits per-(owner,repo) to prevent fork-author webhook spam
  2. Fetches the commit list for the PR
  3. Runs attribution + summarisation
  4. Renders the sticky comment (minimal v1 format)
  5. Upserts the comment (PATCH if a prior bot comment exists)
  6. Publishes a neutral Check Run with the same summary

All errors are logged and swallowed — the webhook endpoint must
always 204 within the GitHub 10-second SLA so the event isn't queued
for retry. Retries are handled idempotently thanks to the sticky
marker.
"""
from __future__ import annotations

import logging

from app.services.pr_bot.commit_attribution import detect_ai_commits, summarize
from app.services.pr_bot.github_app import GitHubAppClient
from app.services.pr_bot.rate_limiter import PerRepoRateLimiter
from app.services.pr_bot.renderer import (
    extract_sticky_comment_id,
    render_check_run_summary,
    render_sticky_comment,
)

logger = logging.getLogger("garl.pr_bot.handler")


class PrBotHandler:
    def __init__(
        self,
        app_client: GitHubAppClient,
        rate_limiter: PerRepoRateLimiter | None = None,
    ) -> None:
        self._app = app_client
        self._rate = rate_limiter or PerRepoRateLimiter()

    def handle_pull_request_event(self, payload: dict) -> dict:
        """Return a result dict {status, reason?, summary?} describing
        what happened. Callers ignore the return in the webhook path
        but tests inspect it."""
        action = payload.get("action")
        if action not in ("opened", "synchronize", "reopened", "ready_for_review"):
            return {"status": "skipped", "reason": f"action={action}"}

        repo = payload.get("repository") or {}
        owner = (repo.get("owner") or {}).get("login", "")
        name = repo.get("name", "")
        pr = payload.get("pull_request") or {}
        pr_number = pr.get("number")
        head_sha = (pr.get("head") or {}).get("sha", "")
        installation_id = (payload.get("installation") or {}).get("id")

        if not (owner and name and pr_number and head_sha and installation_id):
            return {"status": "skipped", "reason": "missing required payload fields"}

        if not self._rate.allow(owner, name):
            return {"status": "dropped", "reason": "rate_limited"}

        if not self._app.configured:
            return {"status": "skipped", "reason": "github_app_not_configured"}

        try:
            token = self._app.installation_token(int(installation_id))
            commits = self._app.list_pr_commits(
                token=token, owner=owner, repo=name, pr_number=pr_number,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("fetch_commits failed for %s/%s#%s: %s", owner, name, pr_number, e)
            return {"status": "error", "reason": "fetch_commits_failed"}

        attribution = detect_ai_commits(commits)
        summary = summarize(attribution)

        body = render_sticky_comment(
            owner=owner,
            repo=name,
            pr_number=pr_number,
            ai_percentage=summary["ai_percentage"],
            ai_commits=summary["ai_commits"],
            total_commits=summary["total_commits"],
            model_counts=summary["model_counts"] or None,
        )

        try:
            existing = self._app.list_issue_comments(
                token=token, owner=owner, repo=name, pr_number=pr_number,
            )
            comment_id = extract_sticky_comment_id(existing)
            if comment_id:
                self._app.patch_comment(
                    token=token, owner=owner, repo=name,
                    comment_id=comment_id, body=body,
                )
            else:
                self._app.post_comment(
                    token=token, owner=owner, repo=name,
                    pr_number=pr_number, body=body,
                )
        except Exception as e:  # noqa: BLE001
            logger.warning("comment upsert failed for %s/%s#%s: %s", owner, name, pr_number, e)
            return {"status": "error", "reason": "comment_failed", "summary": summary}

        try:
            title, check_summary = render_check_run_summary(
                ai_percentage=summary["ai_percentage"],
                ai_commits=summary["ai_commits"],
                total_commits=summary["total_commits"],
                model_counts=summary["model_counts"] or None,
            )
            self._app.publish_check_run(
                token=token, owner=owner, repo=name,
                head_sha=head_sha, title=title, summary=check_summary,
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("check_run failed for %s/%s@%s: %s", owner, name, head_sha, e)
            # Check Run failure is non-fatal — the comment already posted.

        return {"status": "ok", "summary": summary}
