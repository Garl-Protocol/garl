"""Unit tests for PR bot helpers (commit attribution, HMAC, rate limit)."""
import hashlib
import hmac as _hmac
import time
from unittest.mock import patch

import pytest

from app.services.pr_bot import (
    AttributionResult,
    PerRepoRateLimiter,
    detect_ai_commits,
    verify_github_signature,
)
from app.services.pr_bot.commit_attribution import summarize


def _commit(sha, message):
    return {"sha": sha, "commit": {"message": message}}


class TestAttributionTrailers:
    def test_claude_code_trailer_high_confidence(self):
        r = detect_ai_commits([_commit("a1", "fix: X\n\nCo-Authored-By: Claude <noreply@anthropic.com>")])
        assert r[0].model == "claude-code"
        assert r[0].confidence >= 0.9

    def test_claude_code_generated_line_also_detected(self):
        r = detect_ai_commits([_commit("a2", "feat: Y\n\n🤖 Generated with [Claude Code](https://claude.com/claude-code)")])
        assert r[0].model == "claude-code"
        assert r[0].confidence >= 0.9

    def test_cursor_trailer(self):
        r = detect_ai_commits([_commit("b1", "refactor\n\nCo-Authored-By: Cursor <agent@cursor.sh>")])
        assert r[0].model == "cursor"

    def test_aider_trailer(self):
        r = detect_ai_commits([_commit("c1", "docs\n\nCo-Authored-By: aider <noreply@paulgauthier.github.com>")])
        assert r[0].model == "aider"

    def test_copilot_trailer(self):
        r = detect_ai_commits([_commit("d1", "feat\n\nCo-Authored-By: github-copilot[bot] <bot@github.com>")])
        assert r[0].model == "github-copilot"

    def test_codex_trailer(self):
        r = detect_ai_commits([_commit("e1", "patch\n\nCo-Authored-By: Codex <codex@openai.com>")])
        assert r[0].model == "codex"

    def test_human_commit_no_attribution(self):
        r = detect_ai_commits([_commit("h1", "fix: vanilla bug")])
        assert r[0].model is None
        assert r[0].confidence == 0.0

    def test_body_match_weaker_than_trailer(self):
        # plain body reference → lower confidence
        r = detect_ai_commits([_commit("b2", "used aider to write this")])
        assert r[0].model == "aider"
        assert 0 < r[0].confidence < 0.9


class TestAttributionSummarize:
    def test_percentage_rounds_correctly(self):
        results = [
            AttributionResult("a1", "claude-code", 0.95, ("trailer:claude-code",)),
            AttributionResult("a2", None, 0.0, ()),
            AttributionResult("a3", "cursor", 0.95, ("trailer:cursor",)),
        ]
        s = summarize(results)
        assert s["total_commits"] == 3
        assert s["ai_commits"] == 2
        assert s["ai_percentage"] == pytest.approx(66.7, abs=0.1)
        assert s["model_counts"] == {"claude-code": 1, "cursor": 1}

    def test_low_confidence_excluded_by_default(self):
        results = [
            AttributionResult("a1", "aider", 0.4, ("body:aider",)),  # below default 0.5
            AttributionResult("a2", "claude-code", 0.95, ()),
        ]
        s = summarize(results)
        assert s["ai_commits"] == 1
        assert s["ai_percentage"] == 50.0

    def test_empty_commits(self):
        assert summarize([])["ai_percentage"] == 0.0


class TestGithubHmac:
    _secret = "webhook-secret-xyz"

    def _sig(self, body: bytes) -> str:
        return "sha256=" + _hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()

    def test_valid_signature_passes(self):
        body = b'{"action":"opened"}'
        assert verify_github_signature(body, self._sig(body), self._secret) is True

    def test_bare_hex_also_accepted(self):
        body = b"data"
        hex_only = _hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest()
        assert verify_github_signature(body, hex_only, self._secret) is True

    def test_tampered_body_fails(self):
        good_sig = self._sig(b"hello")
        assert verify_github_signature(b"hell0", good_sig, self._secret) is False

    def test_wrong_secret_fails(self):
        body = b"x"
        assert verify_github_signature(body, self._sig(body), "other-secret") is False

    def test_missing_header_or_secret(self):
        assert verify_github_signature(b"x", None, self._secret) is False
        assert verify_github_signature(b"x", self._sig(b"x"), "") is False

    def test_non_hex_signature_rejected(self):
        assert verify_github_signature(b"x", "sha256=not-hex-at-all-just-letters!!", self._secret) is False

    def test_wrong_length_rejected(self):
        assert verify_github_signature(b"x", "sha256=abcd", self._secret) is False

    def test_uppercase_hex_accepted(self):
        body = b"payload"
        expected = _hmac.new(self._secret.encode(), body, hashlib.sha256).hexdigest().upper()
        assert verify_github_signature(body, "sha256=" + expected, self._secret) is True


class TestRateLimiter:
    def test_allows_up_to_limit(self):
        lim = PerRepoRateLimiter(max_events=3, window_seconds=60)
        assert all(lim.allow("a", "repo") for _ in range(3))
        assert lim.allow("a", "repo") is False
        assert lim.dropped[("a", "repo")] == 1

    def test_separate_repos_independent(self):
        lim = PerRepoRateLimiter(max_events=1, window_seconds=60)
        assert lim.allow("a", "r1") is True
        assert lim.allow("a", "r2") is True
        assert lim.allow("a", "r1") is False

    def test_window_rollover_re_allows(self):
        lim = PerRepoRateLimiter(max_events=1, window_seconds=60)
        base = 1000.0
        calls = [base, base + 0.1, base + 120]
        idx = {"n": 0}

        def fake_monotonic():
            v = calls[idx["n"]]
            idx["n"] += 1
            return v

        with patch.object(time, "monotonic", side_effect=fake_monotonic):
            assert lim.allow("a", "r") is True
            assert lim.allow("a", "r") is False
            assert lim.allow("a", "r") is True  # window rolled over
