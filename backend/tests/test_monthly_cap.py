"""Monthly receipt cap tests.

Pure logic tests — month-boundary math, the 429 path. The Supabase count
queries are mocked; production behavior is the integration concern.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.monthly_cap import (
    DEFAULT_MONTHLY_CAP,
    _month_end,
    _month_start,
    enforce_monthly_cap,
    get_monthly_usage,
)


# ──────────────────────────────────────────────────────────────────────
# Month boundary math
# ──────────────────────────────────────────────────────────────────────

def test_month_start_zeroes_time_components():
    now = datetime(2026, 4, 27, 14, 22, 36, 123, tzinfo=timezone.utc)
    s = _month_start(now)
    assert s == datetime(2026, 4, 1, 0, 0, 0, 0, tzinfo=timezone.utc)


def test_month_end_rolls_to_next_month_first_second():
    s = _month_start(datetime(2026, 4, 15, tzinfo=timezone.utc))
    e = _month_end(datetime(2026, 4, 15, tzinfo=timezone.utc))
    assert e.year == 2026 and e.month == 5 and e.day == 1
    assert e.hour == 0 and e.minute == 0 and e.second == 0


def test_month_end_handles_december_year_rollover():
    e = _month_end(datetime(2026, 12, 15, tzinfo=timezone.utc))
    assert e.year == 2027 and e.month == 1 and e.day == 1


# ──────────────────────────────────────────────────────────────────────
# Helpers — minimal Supabase double for count queries
# ──────────────────────────────────────────────────────────────────────

class _CountResult:
    def __init__(self, count):
        self.count = count
        self.data = []


def _stub_supabase(traces_count, receipts_count):
    """Return a MagicMock that, when chained .table(name).select(...,count='exact').
    eq(...).gte(...).lt(...).execute(), returns the right count for each table."""
    sb = MagicMock()

    def make_table(name):
        chain = MagicMock()
        chain.select.return_value = chain
        chain.eq.return_value = chain
        chain.gte.return_value = chain
        chain.lt.return_value = chain
        if name == "traces":
            chain.execute.return_value = _CountResult(traces_count)
        elif name == "receipts":
            chain.execute.return_value = _CountResult(receipts_count)
        else:
            chain.execute.return_value = _CountResult(0)
        return chain

    sb.table.side_effect = make_table
    return sb


# ──────────────────────────────────────────────────────────────────────
# get_monthly_usage
# ──────────────────────────────────────────────────────────────────────

def test_usage_sums_traces_and_receipts():
    sb = _stub_supabase(traces_count=200, receipts_count=300)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        usage = get_monthly_usage("11111111-1111-1111-1111-111111111111")
    assert usage["used"] == 500
    assert usage["cap"] == DEFAULT_MONTHLY_CAP
    assert usage["remaining"] == DEFAULT_MONTHLY_CAP - 500
    assert "T" in usage["period_end"]


def test_usage_handles_null_count_gracefully():
    """Some Supabase responses return count=None when the table is empty."""
    sb = _stub_supabase(traces_count=None, receipts_count=None)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        usage = get_monthly_usage("22222222-2222-2222-2222-222222222222")
    assert usage["used"] == 0
    assert usage["remaining"] == DEFAULT_MONTHLY_CAP


def test_usage_remaining_clamped_to_zero_when_over():
    """If the cap was lowered or env-overridden lower than current usage,
    remaining must not go negative."""
    sb = _stub_supabase(traces_count=DEFAULT_MONTHLY_CAP + 500, receipts_count=0)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        usage = get_monthly_usage("33333333-3333-3333-3333-333333333333")
    assert usage["used"] == DEFAULT_MONTHLY_CAP + 500
    assert usage["remaining"] == 0


# ──────────────────────────────────────────────────────────────────────
# enforce_monthly_cap
# ──────────────────────────────────────────────────────────────────────

def test_under_cap_does_not_raise():
    sb = _stub_supabase(traces_count=10, receipts_count=20)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        # Should silently return None
        assert enforce_monthly_cap("44444444-4444-4444-4444-444444444444") is None


def test_at_cap_raises_429_with_retry_after():
    sb = _stub_supabase(traces_count=DEFAULT_MONTHLY_CAP, receipts_count=0)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as exc:
            enforce_monthly_cap("55555555-5555-5555-5555-555555555555")
    e = exc.value
    assert e.status_code == 429
    assert "Monthly receipt cap reached" in e.detail
    headers = e.headers or {}
    assert headers["X-RateLimit-Remaining"] == "0"
    assert headers["X-RateLimit-Scope"] == "monthly-receipts"
    assert int(headers["Retry-After"]) >= 1


def test_over_cap_still_raises():
    sb = _stub_supabase(traces_count=DEFAULT_MONTHLY_CAP + 100, receipts_count=0)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as exc:
            enforce_monthly_cap("66666666-6666-6666-6666-666666666666")
    assert exc.value.status_code == 429


def test_retry_after_smaller_than_a_month():
    """A cap hit always resets at the start of the next month — Retry-After
    must be at most ~31 days. Sanity guard against unit confusion."""
    sb = _stub_supabase(traces_count=DEFAULT_MONTHLY_CAP, receipts_count=0)
    with patch("app.services.monthly_cap._get_supabase", return_value=sb):
        with pytest.raises(HTTPException) as exc:
            enforce_monthly_cap("77777777-7777-7777-7777-777777777777")
    retry = int((exc.value.headers or {})["Retry-After"])
    assert 0 < retry <= 31 * 24 * 3600
