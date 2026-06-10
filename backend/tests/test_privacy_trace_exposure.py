"""Regression: public agent surfaces must not leak an agent's private I/O.

/agents/{id}/detail returned raw trace rows (select *), exposing
input_summary / output_summary and the arbitrary client-supplied metadata blob
on an unauthenticated endpoint — real operational data of other agents (SMTP
servers, outreach targets, internal notes) was publicly visible, contradicting
the privacy policy ("never surface input_summary / output_summary").
"""
from app.services.agents import _public_trace_view


def _raw_trace():
    return {
        "id": "t1",
        "agent_id": "a1",
        "task_description": "AI-authored commit abc123: fix X",
        "status": "success",
        "duration_ms": 1,
        "category": "coding",
        "trust_delta": 1.5,
        "trace_hash": "a" * 64,
        "certificate": {"proof": {"signature": "sig"}},
        "created_at": "2026-06-10T00:00:00Z",
        # private / sensitive:
        "input_summary": "6 newsletter editors targeted; SMTP mail.example.com:465",
        "output_summary": "Emails sent from agent@example.com",
        "metadata": {
            "github_repo": "owner/repo",
            "commit_sha": "abc123",
            "ai_tool": "Claude",
            "files_changed": 3,
            "secret_token": "ghp_SHOULD_NOT_LEAK",
            "internal_note": "private",
        },
    }


def test_strips_input_output_summary():
    out = _public_trace_view(_raw_trace())
    assert "input_summary" not in out
    assert "output_summary" not in out


def test_metadata_whitelisted_to_provenance():
    out = _public_trace_view(_raw_trace())
    md = out["metadata"]
    # provenance keys kept
    assert md["github_repo"] == "owner/repo"
    assert md["commit_sha"] == "abc123"
    assert md["ai_tool"] == "Claude"
    assert md["files_changed"] == 3
    # arbitrary / sensitive keys dropped
    assert "secret_token" not in md
    assert "internal_note" not in md


def test_safe_public_fields_preserved():
    out = _public_trace_view(_raw_trace())
    for k in ("task_description", "status", "category", "trace_hash", "certificate", "created_at"):
        assert k in out


def test_handles_missing_or_nondict_metadata():
    t = _raw_trace()
    t["metadata"] = None
    out = _public_trace_view(t)
    assert "input_summary" not in out  # still stripped
    # metadata None -> left as-is (no crash)
    t2 = _raw_trace(); del t2["metadata"]
    out2 = _public_trace_view(t2)
    assert "input_summary" not in out2
