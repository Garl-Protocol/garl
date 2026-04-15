"""Detect which commits in a PR were authored or co-authored by an AI tool.

Inputs are GitHub's commit list shape (list of dicts with at least
``sha`` and ``commit.message``). Output is one ``AttributionResult`` per
commit with a best-guess model name and a confidence score. Downstream
renderers aggregate to "X of N commits AI-authored".

Conservative by design — false positives undermine the whole
narrative. When nothing matches we return ``model=None, confidence=0.0``
and the commit counts as human-authored.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class AttributionResult:
    sha: str
    model: str | None
    confidence: float  # 0.0 = human, 1.0 = cryptographic certainty (e.g. signed receipt)
    signals: tuple[str, ...]  # which rules fired


# Co-author trailers — RFC 2821/5322 style, case-insensitive matching. Each
# pattern maps a detected trailer to a canonical model name. Order matters:
# Claude Code's trailer is distinct from Aider's even though both cite
# "Claude" — we match the most specific signal first.
_TRAILER_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"Co-Authored-By:\s*Claude\s*<noreply@anthropic\.com>", re.I), "claude-code"),
    (re.compile(r"Generated with \[Claude Code\]", re.I), "claude-code"),
    (re.compile(r"Co-Authored-By:\s*Cursor\s*<", re.I), "cursor"),
    (re.compile(r"Cursor\s*<agent@cursor\.sh>", re.I), "cursor"),
    (re.compile(r"Co-Authored-By:\s*aider\b", re.I), "aider"),
    (re.compile(r"Co-Authored-By:\s*Copilot\b", re.I), "github-copilot"),
    (re.compile(r"Co-Authored-By:\s*github-copilot\[bot\]", re.I), "github-copilot"),
    (re.compile(r"Co-Authored-By:\s*Codex\s*<", re.I), "codex"),
    (re.compile(r"Co-Authored-By:\s*OpenAI Codex", re.I), "codex"),
)

# Weaker message-body patterns. Fire only when no trailer matched, and
# attribute lower confidence. Each tuple is (pattern, model, confidence).
_BODY_PATTERNS: tuple[tuple[re.Pattern[str], str, float], ...] = (
    (re.compile(r"^🤖\s*Generated with \[Claude Code\]", re.I | re.M), "claude-code", 0.85),
    (re.compile(r"\bClaude Code\b", re.I), "claude-code", 0.55),
    (re.compile(r"\bCursor Agent\b", re.I), "cursor", 0.55),
    (re.compile(r"\baider\b", re.I), "aider", 0.4),
    (re.compile(r"\bGitHub Copilot\b", re.I), "github-copilot", 0.45),
)

_TRAILER_CONFIDENCE = 0.95  # any trailer match → high confidence


def _extract_commit_message(commit: dict) -> str:
    """Accept both the GitHub REST shape (commit.commit.message) and the
    flattened shape we use internally (commit.message)."""
    inner = commit.get("commit")
    if isinstance(inner, dict) and isinstance(inner.get("message"), str):
        return inner["message"]
    return commit.get("message", "") or ""


def detect_ai_commits(commits: list[dict]) -> list[AttributionResult]:
    results: list[AttributionResult] = []
    for c in commits:
        sha = c.get("sha") or c.get("id") or ""
        message = _extract_commit_message(c)
        signals: list[str] = []
        model: str | None = None
        confidence = 0.0

        for pattern, canonical_model in _TRAILER_PATTERNS:
            if pattern.search(message):
                model = canonical_model
                confidence = _TRAILER_CONFIDENCE
                signals.append(f"trailer:{canonical_model}")
                break

        if model is None:
            for pattern, canonical_model, conf in _BODY_PATTERNS:
                if pattern.search(message):
                    model = canonical_model
                    confidence = conf
                    signals.append(f"body:{canonical_model}")
                    break

        results.append(
            AttributionResult(
                sha=str(sha),
                model=model,
                confidence=confidence,
                signals=tuple(signals),
            )
        )
    return results


def summarize(results: list[AttributionResult], min_confidence: float = 0.5) -> dict:
    """Aggregate attribution results into a shape the sticky comment
    renderer will consume. ``min_confidence`` guards the AI percentage —
    below that threshold a commit counts as human-authored."""
    total = len(results)
    ai_commits = [r for r in results if r.confidence >= min_confidence]
    model_counts: dict[str, int] = {}
    for r in ai_commits:
        if r.model:
            model_counts[r.model] = model_counts.get(r.model, 0) + 1
    ai_pct = round(100 * len(ai_commits) / total, 1) if total else 0.0
    return {
        "total_commits": total,
        "ai_commits": len(ai_commits),
        "ai_percentage": ai_pct,
        "model_counts": model_counts,
    }
