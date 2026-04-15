"""Renderer + handler orchestration tests for the PR bot."""
from unittest.mock import MagicMock

import pytest

from app.services.pr_bot import (
    GitHubAppClient,
    PerRepoRateLimiter,
    PrBotHandler,
    STICKY_MARKER,
    extract_sticky_comment_id,
    render_check_run_summary,
    render_sticky_comment,
)


class TestStickyComment:
    def test_minimal_v1_format(self):
        body = render_sticky_comment(
            owner="acme", repo="widgets", pr_number=42,
            ai_percentage=73.0, ai_commits=8, total_commits=11,
            model_counts={"claude-code": 6, "cursor": 2},
        )
        assert STICKY_MARKER in body
        assert "🔐 GARL Verified AI Code" in body
        assert "73%" in body
        assert "8 of 11 commits" in body
        assert "[Verify all →]" in body
        assert "https://garl.ai/pr/acme/widgets/42" in body
        assert "`claude-code`×6" in body
        assert "`cursor`×2" in body

    def test_models_line_omitted_when_none(self):
        body = render_sticky_comment(
            owner="a", repo="b", pr_number=1,
            ai_percentage=0.0, ai_commits=0, total_commits=3,
        )
        assert "Models:" not in body
        assert "0%" in body

    def test_custom_verify_url_override(self):
        body = render_sticky_comment(
            owner="a", repo="b", pr_number=1,
            ai_percentage=50.0, ai_commits=1, total_commits=2,
            verify_url="https://example.com/custom",
        )
        assert "https://example.com/custom" in body


class TestCheckRunSummary:
    def test_title_and_summary_shape(self):
        title, summary = render_check_run_summary(
            ai_percentage=60.0, ai_commits=3, total_commits=5,
            model_counts={"claude-code": 3},
        )
        assert title == "60% AI-authored (3/5)"
        assert "| Model | Count |" in summary
        assert "`claude-code` | 3" in summary
        assert "Informational" in summary
        assert "non-blocking" in summary


class TestStickyDetection:
    def test_finds_marker_in_prior_comment(self):
        comments = [
            {"id": 1, "body": "Nice PR"},
            {"id": 99, "body": f"{STICKY_MARKER}\n### 🔐 GARL Verified AI Code\n\n50% AI-authored"},
            {"id": 2, "body": "Later note"},
        ]
        assert extract_sticky_comment_id(comments) == 99

    def test_returns_none_when_no_prior(self):
        comments = [{"id": 1, "body": "Nice PR"}]
        assert extract_sticky_comment_id(comments) is None


class TestPrBotHandler:
    """Full handle_pull_request_event wiring with a mocked app client."""

    def _payload(self, action="opened"):
        return {
            "action": action,
            "installation": {"id": 1111},
            "repository": {"owner": {"login": "acme"}, "name": "widgets"},
            "pull_request": {
                "number": 42,
                "head": {"sha": "deadbeef"},
            },
        }

    def _configured_mock_client(self):
        m = MagicMock(spec=GitHubAppClient)
        m.configured = True
        m.installation_token.return_value = "tok_xyz"
        m.list_pr_commits.return_value = [
            {"sha": "c1", "commit": {"message": "feat: X\n\nCo-Authored-By: Claude <noreply@anthropic.com>"}},
            {"sha": "c2", "commit": {"message": "human commit"}},
            {"sha": "c3", "commit": {"message": "refactor\n\nCo-Authored-By: Cursor <agent@cursor.sh>"}},
        ]
        m.list_issue_comments.return_value = []  # no prior bot comment
        m.post_comment.return_value = {"id": 777}
        m.patch_comment.return_value = {"id": 777}
        m.publish_check_run.return_value = {"id": 888}
        return m

    def test_happy_path_posts_fresh_comment_and_check(self):
        client = self._configured_mock_client()
        h = PrBotHandler(client, rate_limiter=PerRepoRateLimiter(max_events=100))
        out = h.handle_pull_request_event(self._payload())
        assert out["status"] == "ok"
        assert out["summary"]["ai_commits"] == 2
        assert out["summary"]["total_commits"] == 3
        client.post_comment.assert_called_once()
        client.patch_comment.assert_not_called()
        client.publish_check_run.assert_called_once()
        body = client.post_comment.call_args.kwargs["body"]
        assert STICKY_MARKER in body

    def test_patches_existing_sticky_comment(self):
        client = self._configured_mock_client()
        client.list_issue_comments.return_value = [
            {"id": 555, "body": f"{STICKY_MARKER}\nstale"},
        ]
        h = PrBotHandler(client, rate_limiter=PerRepoRateLimiter(max_events=100))
        out = h.handle_pull_request_event(self._payload("synchronize"))
        assert out["status"] == "ok"
        client.patch_comment.assert_called_once()
        client.post_comment.assert_not_called()
        assert client.patch_comment.call_args.kwargs["comment_id"] == 555

    def test_skips_irrelevant_actions(self):
        h = PrBotHandler(self._configured_mock_client())
        out = h.handle_pull_request_event({**self._payload(), "action": "labeled"})
        assert out["status"] == "skipped"

    def test_missing_fields_skipped(self):
        client = self._configured_mock_client()
        h = PrBotHandler(client)
        bad = {"action": "opened", "pull_request": {"number": 1}}
        out = h.handle_pull_request_event(bad)
        assert out["status"] == "skipped"
        client.installation_token.assert_not_called()

    def test_rate_limited(self):
        client = self._configured_mock_client()
        lim = PerRepoRateLimiter(max_events=1, window_seconds=60)
        h = PrBotHandler(client, rate_limiter=lim)
        first = h.handle_pull_request_event(self._payload())
        second = h.handle_pull_request_event(self._payload("synchronize"))
        assert first["status"] == "ok"
        assert second["status"] == "dropped"

    def test_unconfigured_app_skipped(self):
        client = MagicMock(spec=GitHubAppClient)
        client.configured = False
        h = PrBotHandler(client)
        out = h.handle_pull_request_event(self._payload())
        assert out["status"] == "skipped"
        assert "not_configured" in out["reason"]

    def test_check_run_failure_is_non_fatal(self):
        client = self._configured_mock_client()
        client.publish_check_run.side_effect = RuntimeError("check down")
        h = PrBotHandler(client, rate_limiter=PerRepoRateLimiter(max_events=100))
        out = h.handle_pull_request_event(self._payload())
        # Comment still posted — overall status remains ok despite check error
        assert out["status"] == "ok"
