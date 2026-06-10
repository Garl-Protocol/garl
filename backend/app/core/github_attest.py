"""Independent re-verification of GitHub check-run attestations.

A receipt can carry a ``github-check-run`` attestation:
``{type, repo, commit_sha, conclusion}``. By itself that's a re-checkable claim
(anyone can call GitHub with repo+sha and confirm it). When
``ENABLE_GITHUB_ATTESTATION_CHECK`` is truthy AND a token is available, the
backend ALSO re-verifies it server-side and stamps ``witnessed`` — upgrading the
attestation from "claimed" to "witnessed by GARL".

Fails OPEN: if the flag is off, no token is set, or GitHub is slow/down, the
attestation is returned unchanged (no ``witnessed`` stamp) and the submission is
never blocked. A signed receipt should never depend on GitHub's availability.
"""
from __future__ import annotations

import os

import httpx

_GH_API = "https://api.github.com"
_ENABLE_ENV = "ENABLE_GITHUB_ATTESTATION_CHECK"


def _token() -> str:
    return os.environ.get("GARL_GITHUB_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""


def is_enabled() -> bool:
    return (
        os.environ.get(_ENABLE_ENV, "").strip().lower() in ("1", "true", "yes", "on")
        and bool(_token())
    )


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _combined_conclusion(repo: str, sha: str, timeout_s: float) -> str | None:
    """The commit's overall CI conclusion, or None if the commit does not exist.

    GARL's own neutral check-run is excluded so we read the repo's REAL CI, not
    our own marker. Returns one of: pending | failure | success | neutral | none.
    """
    # 1) commit must exist in the repo
    r = httpx.get(
        f"{_GH_API}/repos/{repo}/commits/{sha}",
        headers=_headers(), timeout=timeout_s, follow_redirects=False,
    )
    if r.status_code == 404:
        return None
    r.raise_for_status()

    # 2) aggregate the commit's check-runs (excluding ourselves)
    cr = httpx.get(
        f"{_GH_API}/repos/{repo}/commits/{sha}/check-runs",
        headers=_headers(), timeout=timeout_s, follow_redirects=False,
    )
    cr.raise_for_status()
    runs = [
        c for c in (cr.json().get("check_runs") or [])
        if "garl" not in (c.get("name") or "").lower()
    ]
    if not runs:
        return "none"
    statuses = {c.get("status") for c in runs}
    conclusions = {c.get("conclusion") for c in runs}
    if statuses & {"queued", "in_progress"} or None in conclusions:
        return "pending"
    if conclusions & {"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"}:
        return "failure"
    if "success" in conclusions:
        return "success"
    return "neutral"


def verify_check_run(att: dict, timeout_s: float = 4.0) -> dict:
    """Return a copy of ``att`` augmented with ``witnessed`` (and, on mismatch,
    ``actual_conclusion`` + ``witness_reason``). Never raises; fails open."""
    out = dict(att)
    if att.get("type") != "github-check-run":
        return out
    repo, sha = att.get("repo"), att.get("commit_sha")
    if not (is_enabled() and repo and sha):
        return out
    try:
        actual = _combined_conclusion(repo, sha, timeout_s)
    except Exception:
        return out  # GitHub slow/down — never block a submission
    if actual is None:
        out["witnessed"] = False
        out["witness_reason"] = "commit-not-found"
        return out
    claimed = (att.get("conclusion") or "").strip().lower()
    out["actual_conclusion"] = actual
    out["witnessed"] = (claimed == actual) if claimed else True
    if claimed and claimed != actual:
        out["witness_reason"] = "conclusion-mismatch"
    return out
