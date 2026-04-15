"""Pure rendering helpers for the PR bot sticky comment + check-run summary.

Day-1 comment is deliberately minimal — one line of AI percentage, one
line linking to the canonical 'verify all' page. Full per-commit
breakdown ships in v2 once we have a reader's feedback loop.

Kept pure so tests can snapshot-match without mocking httpx.
"""
from __future__ import annotations

# Hidden HTML marker used by the handler to detect its own previous
# comment on a PR and PATCH in place rather than POST a fresh one.
STICKY_MARKER = "<!-- garl-pr-bot:v1 -->"


def render_sticky_comment(
    *,
    owner: str,
    repo: str,
    pr_number: int,
    ai_percentage: float,
    ai_commits: int,
    total_commits: int,
    model_counts: dict[str, int] | None = None,
    verify_url: str | None = None,
) -> str:
    """Markdown body for the sticky comment."""
    if verify_url is None:
        verify_url = f"https://garl.ai/pr/{owner}/{repo}/{pr_number}"
    models_line = ""
    if model_counts:
        parts = [f"`{name}`×{n}" for name, n in sorted(model_counts.items())]
        models_line = "\n" + "Models: " + ", ".join(parts)
    pct_block = f"**{ai_percentage:.0f}%** AI-authored ({ai_commits} of {total_commits} commits)"
    return (
        f"{STICKY_MARKER}\n"
        f"### 🔐 GARL Verified AI Code\n\n"
        f"{pct_block}{models_line}\n\n"
        f"[Verify all →]({verify_url})"
    )


def render_check_run_summary(
    *,
    ai_percentage: float,
    ai_commits: int,
    total_commits: int,
    model_counts: dict[str, int] | None = None,
) -> tuple[str, str]:
    """Return (title, summary_markdown) suitable for the GitHub Check Run
    body. Conclusion is always 'neutral' — this is informational, not a
    gate. Policy gates live behind /api/v1/policy/check and are opt-in
    per repo."""
    title = f"{ai_percentage:.0f}% AI-authored ({ai_commits}/{total_commits})"
    lines = [
        f"**{ai_percentage:.0f}%** AI-authored · {ai_commits}/{total_commits} commits",
    ]
    if model_counts:
        lines.append("")
        lines.append("| Model | Count |")
        lines.append("|---|---|")
        for name, n in sorted(model_counts.items()):
            lines.append(f"| `{name}` | {n} |")
    lines.append("")
    lines.append("Informational · non-blocking · open-source at [Garl-Protocol/garl](https://github.com/Garl-Protocol/garl).")
    return title, "\n".join(lines)


def extract_sticky_comment_id(existing_comments: list[dict]) -> int | None:
    """Find the id of a prior bot comment on a PR, if any. Matches the
    hidden STICKY_MARKER inside the comment body."""
    for c in existing_comments or []:
        body = c.get("body") or ""
        if STICKY_MARKER in body and c.get("id"):
            return int(c["id"])
    return None
