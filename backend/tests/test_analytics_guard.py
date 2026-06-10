"""Analytics must never emit to the real PostHog project during tests/CI.

On 2026-06-09 a test run pushed fixture UUIDs (11111111-...) into the live
PostHog project because capture() fired unconditionally. These tests lock the
guard in place.
"""
import os
from unittest.mock import patch

from app.core import analytics


def test_disabled_under_pytest():
    # PYTEST_CURRENT_TEST is set by pytest for the duration of every test, so
    # the guard must report disabled right now.
    assert analytics._analytics_disabled() is True


def test_capture_does_not_post_in_tests():
    # Even if some code path calls capture(), no HTTP request may be made.
    with patch.object(analytics.httpx, "post", side_effect=AssertionError("analytics fired in a test!")) as m:
        analytics.capture("agent_registered", "11111111-1111-1111-1111-111111111111", {"x": 1})
        assert m.call_count == 0


def test_guard_env_signals():
    with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "", "CI": "", "GARL_DISABLE_ANALYTICS": "1"}, clear=False):
        assert analytics._analytics_disabled() is True
    with patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "", "CI": "true", "GARL_DISABLE_ANALYTICS": ""}, clear=False):
        assert analytics._analytics_disabled() is True
