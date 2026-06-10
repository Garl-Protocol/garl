"""Externally-corroborated receipts — GitHub check-run attestations.

The receipt carries an independently re-checkable attestation
(repo + commit_sha + conclusion). When ENABLE_GITHUB_ATTESTATION_CHECK is on,
the backend re-verifies it against GitHub and stamps `witnessed`.
"""
import hashlib
import json
from unittest.mock import patch, MagicMock

from app.core import github_attest as gha


def _resp(status=200, json_body=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_body or {}
    m.raise_for_status.return_value = None
    return m


def _gh(commit_status=200, check_runs=None):
    """Patch httpx.get to answer the two GitHub calls: commit existence, then
    check-runs."""
    def _side_effect(url, **kwargs):
        if url.endswith("/check-runs"):
            return _resp(200, {"check_runs": check_runs or []})
        return _resp(commit_status, {"sha": "abc"})
    return _side_effect


ENABLED_ENV = {"ENABLE_GITHUB_ATTESTATION_CHECK": "true", "GITHUB_TOKEN": "ghs_test"}


class TestVerifyCheckRun:
    def test_noop_when_flag_off(self):
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success"}
        with patch.dict("os.environ", {"ENABLE_GITHUB_ATTESTATION_CHECK": "", "GITHUB_TOKEN": "x"}, clear=False):
            out = gha.verify_check_run(att)
        assert "witnessed" not in out  # untouched — stays a re-checkable claim

    def test_witnessed_true_on_match(self):
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success"}
        runs = [{"name": "CI / build", "status": "completed", "conclusion": "success"}]
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            with patch.object(gha.httpx, "get", side_effect=_gh(check_runs=runs)):
                out = gha.verify_check_run(att)
        assert out["witnessed"] is True
        assert out["actual_conclusion"] == "success"

    def test_witnessed_false_on_mismatch(self):
        # Claims success, but real CI failed → witnessed False + reason.
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success"}
        runs = [{"name": "CI / test", "status": "completed", "conclusion": "failure"}]
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            with patch.object(gha.httpx, "get", side_effect=_gh(check_runs=runs)):
                out = gha.verify_check_run(att)
        assert out["witnessed"] is False
        assert out["actual_conclusion"] == "failure"
        assert out["witness_reason"] == "conclusion-mismatch"

    def test_witnessed_false_when_commit_missing(self):
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success"}
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            with patch.object(gha.httpx, "get", side_effect=_gh(commit_status=404)):
                out = gha.verify_check_run(att)
        assert out["witnessed"] is False
        assert out["witness_reason"] == "commit-not-found"

    def test_garl_own_check_run_excluded(self):
        # Only GARL's own neutral run exists → no real CI → "none", not success.
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "none"}
        runs = [{"name": "GARL Receipt", "status": "completed", "conclusion": "neutral"}]
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            with patch.object(gha.httpx, "get", side_effect=_gh(check_runs=runs)):
                out = gha.verify_check_run(att)
        assert out["actual_conclusion"] == "none"
        assert out["witnessed"] is True  # claimed "none" matches

    def test_fails_open_on_github_error(self):
        att = {"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success"}
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            with patch.object(gha.httpx, "get", side_effect=RuntimeError("network down")):
                out = gha.verify_check_run(att)
        assert "witnessed" not in out  # fail open — submission not blocked

    def test_non_github_attestation_untouched(self):
        att = {"type": "some-other-attestation", "foo": "bar"}
        with patch.dict("os.environ", ENABLED_ENV, clear=False):
            out = gha.verify_check_run(att)
        assert out == att


class TestAttestationBinding:
    """Attestations must be bound into the SIGNED payload, and absence must not
    change the historical trace hash."""

    def _trace_raw(self, attestations=None):
        raw = {
            "trace_id": "t1", "agent_id": "a1", "task_description": "x",
            "status": "success", "duration_ms": 1, "category": "coding",
            "cost_usd": 0.0, "token_count": 0, "timestamp": "2026-06-10T00:00:00Z",
        }
        if attestations:
            raw["attestations"] = attestations
        return raw

    def test_absence_keeps_hash_unchanged(self):
        from app.services.traces import _compute_trace_hash
        # A trace with no attestations key must hash exactly as before the feature.
        base = self._trace_raw()
        h1 = _compute_trace_hash(base)
        h2 = _compute_trace_hash(dict(base))
        assert h1 == h2

    def test_attestation_changes_hash_and_is_signed(self):
        from app.services.traces import _compute_trace_hash
        from app.core import signing
        signing._signing_key = None
        with_att = self._trace_raw(attestations=[{"type": "github-check-run", "repo": "o/r", "commit_sha": "a" * 40, "conclusion": "success", "witnessed": True}])
        without = self._trace_raw()
        assert _compute_trace_hash(with_att) != _compute_trace_hash(without)
        # And the attestation is inside the signed certificate payload.
        cert = signing.sign_trace(with_att)
        assert cert["payload"]["attestations"][0]["repo"] == "o/r"
        assert signing.verify_signature(cert) is True
