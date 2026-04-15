"""GitHub App REST client for the GARL PR bot.

Responsibilities:
- Mint a short-lived App JWT (RS256 over the App's private key)
- Exchange the JWT for an installation access token
- Fetch the PR commit list
- Upsert a sticky comment (find-by-marker → PATCH, otherwise POST)
- Publish a neutral check-run summary

All credentials come from env vars, never from request input:
- GITHUB_APP_ID              — numeric App id
- GITHUB_APP_PRIVATE_KEY     — PEM private key (multi-line)
- GITHUB_APP_WEBHOOK_SECRET  — webhook HMAC shared secret (read by
                               verify_github_signature, not this module)

The installation id is extracted from the webhook payload by the
handler; this client accepts it as a parameter.

Errors are *logged* and re-raised — the caller decides whether to
retry or swallow. The handler wraps every call in a guard so a broken
App token can never take down the webhook endpoint.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
import jwt as _jwt

logger = logging.getLogger("garl.pr_bot.github_app")

_GH_API = "https://api.github.com"
_USER_AGENT = "garl-pr-bot/1.0 (+https://garl.ai)"


class GitHubAppClient:
    def __init__(
        self,
        app_id: str | int | None = None,
        private_key_pem: str | None = None,
        timeout_s: float = 10.0,
    ) -> None:
        self._app_id = str(app_id or os.environ.get("GITHUB_APP_ID", "")).strip()
        pem = (private_key_pem if private_key_pem is not None else os.environ.get("GITHUB_APP_PRIVATE_KEY", "")).strip()
        # PEM from env usually arrives with \n literals; normalise.
        if "\\n" in pem and "\n" not in pem:
            pem = pem.replace("\\n", "\n")
        self._pem = pem
        self._timeout = timeout_s

    @property
    def configured(self) -> bool:
        return bool(self._app_id and self._pem)

    # --- JWT + installation token -------------------------------------

    def mint_app_jwt(self, now: int | None = None, ttl_s: int = 540) -> str:
        """RS256 App JWT. GitHub caps ttl at 600s; we use 540s for clock
        skew headroom. `now` override exists for deterministic tests."""
        if not self.configured:
            raise RuntimeError("GitHub App is not configured (missing APP_ID / PRIVATE_KEY)")
        iat = now if now is not None else int(time.time())
        payload = {"iat": iat - 60, "exp": iat + ttl_s, "iss": self._app_id}
        return _jwt.encode(payload, self._pem, algorithm="RS256")

    def installation_token(self, installation_id: int) -> str:
        """Exchange the App JWT for an installation access token. Token
        is valid for 1 hour; callers should obtain a fresh one per
        event rather than cache across invocations."""
        app_jwt = self.mint_app_jwt()
        resp = httpx.post(
            f"{_GH_API}/app/installations/{installation_id}/access_tokens",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {app_jwt}",
                "User-Agent": _USER_AGENT,
            },
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"installation_token failed: {resp.status_code} {resp.text[:200]}")
        return resp.json()["token"]

    # --- REST helpers ------------------------------------------------

    def _headers(self, token: str) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": _USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def list_pr_commits(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        pr_number: int,
        limit: int = 250,
    ) -> list[dict[str, Any]]:
        """GET /repos/{owner}/{repo}/pulls/{pr}/commits. GitHub caps at
        250 commits per PR; we surface whatever the page returns."""
        resp = httpx.get(
            f"{_GH_API}/repos/{owner}/{repo}/pulls/{pr_number}/commits",
            headers=self._headers(token),
            params={"per_page": min(100, limit)},
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"list_pr_commits: {resp.status_code} {resp.text[:200]}")
        data = resp.json()
        return data if isinstance(data, list) else []

    def list_issue_comments(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> list[dict[str, Any]]:
        # PRs share the Issues comments endpoint for discussion comments.
        resp = httpx.get(
            f"{_GH_API}/repos/{owner}/{repo}/issues/{pr_number}/comments",
            headers=self._headers(token),
            params={"per_page": 100},
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"list_issue_comments: {resp.status_code} {resp.text[:200]}")
        return resp.json() if isinstance(resp.json(), list) else []

    def post_comment(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        pr_number: int,
        body: str,
    ) -> dict[str, Any]:
        resp = httpx.post(
            f"{_GH_API}/repos/{owner}/{repo}/issues/{pr_number}/comments",
            headers=self._headers(token),
            json={"body": body},
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"post_comment: {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def patch_comment(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        comment_id: int,
        body: str,
    ) -> dict[str, Any]:
        resp = httpx.patch(
            f"{_GH_API}/repos/{owner}/{repo}/issues/comments/{comment_id}",
            headers=self._headers(token),
            json={"body": body},
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"patch_comment: {resp.status_code} {resp.text[:200]}")
        return resp.json()

    def publish_check_run(
        self,
        *,
        token: str,
        owner: str,
        repo: str,
        head_sha: str,
        title: str,
        summary: str,
        conclusion: str = "neutral",
    ) -> dict[str, Any]:
        resp = httpx.post(
            f"{_GH_API}/repos/{owner}/{repo}/check-runs",
            headers=self._headers(token),
            json={
                "name": "GARL PR Bot",
                "head_sha": head_sha,
                "status": "completed",
                "conclusion": conclusion,
                "output": {"title": title, "summary": summary},
            },
            timeout=self._timeout,
        )
        if resp.status_code >= 300:
            raise RuntimeError(f"publish_check_run: {resp.status_code} {resp.text[:200]}")
        return resp.json()
