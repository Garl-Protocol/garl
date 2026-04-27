"""Action Receipt v0.1 service — validation + envelope shape tests.

These tests cover the pure validation + envelope-build path. The persisted
submit_action_receipt path is exercised via route integration tests.
"""

from __future__ import annotations

import pytest

from app.services.action_receipts import (
    ACTION_RECEIPT_VERSION,
    ActionReceiptValidationError,
    _validate_input,
    build_envelope_for_signing,
)


def _valid_request(**overrides):
    base = {
        "agent_id": "11111111-1111-1111-1111-111111111111",
        "runtime": "claude-code",
        "protocol": "mcp",
        "action_type": "tool_call",
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "side_effect": "reversible",
    }
    base.update(overrides)
    return base


# ──────────────────────────────────────────────────────────────────────
# Required field validation
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("missing_field", [
    "agent_id", "runtime", "protocol", "action_type",
    "input_hash", "output_hash", "side_effect",
])
def test_missing_required_field_rejected(missing_field):
    req = _valid_request()
    del req[missing_field]
    with pytest.raises(ActionReceiptValidationError, match=missing_field):
        _validate_input(req)


@pytest.mark.parametrize("missing_field", [
    "agent_id", "runtime", "protocol", "action_type",
    "input_hash", "output_hash", "side_effect",
])
def test_empty_string_required_field_rejected(missing_field):
    req = _valid_request()
    req[missing_field] = ""
    with pytest.raises(ActionReceiptValidationError, match=missing_field):
        _validate_input(req)


# ──────────────────────────────────────────────────────────────────────
# Enum constraints
# ──────────────────────────────────────────────────────────────────────

def test_unknown_runtime_rejected():
    with pytest.raises(ActionReceiptValidationError, match="runtime"):
        _validate_input(_valid_request(runtime="my-custom-runtime"))


def test_unknown_protocol_rejected():
    with pytest.raises(ActionReceiptValidationError, match="protocol"):
        _validate_input(_valid_request(protocol="grpc"))


def test_unknown_action_type_rejected():
    with pytest.raises(ActionReceiptValidationError, match="action_type"):
        _validate_input(_valid_request(action_type="quantum_compute"))


def test_unknown_side_effect_rejected():
    with pytest.raises(ActionReceiptValidationError, match="side_effect"):
        _validate_input(_valid_request(side_effect="catastrophic"))


def test_unknown_policy_decision_rejected():
    with pytest.raises(ActionReceiptValidationError, match="policy_decision"):
        _validate_input(_valid_request(policy_decision="maybe"))


# ──────────────────────────────────────────────────────────────────────
# Hash format checks
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("field", ["input_hash", "output_hash"])
def test_hash_must_be_64_hex(field):
    # Too short
    with pytest.raises(ActionReceiptValidationError, match=field):
        _validate_input(_valid_request(**{field: "abc123"}))
    # Too long
    with pytest.raises(ActionReceiptValidationError, match=field):
        _validate_input(_valid_request(**{field: "a" * 65}))
    # Non-hex character
    with pytest.raises(ActionReceiptValidationError, match=field):
        _validate_input(_valid_request(**{field: "z" * 64}))


def test_previous_receipt_hash_optional_but_validated():
    # Optional → unset is fine
    _validate_input(_valid_request())
    # Wrong length when set
    with pytest.raises(ActionReceiptValidationError, match="previous_receipt_hash"):
        _validate_input(_valid_request(previous_receipt_hash="short"))


def test_capability_token_hash_optional_but_validated():
    _validate_input(_valid_request())
    with pytest.raises(ActionReceiptValidationError, match="capability_token_hash"):
        _validate_input(_valid_request(capability_token_hash="not-64-hex"))


# ──────────────────────────────────────────────────────────────────────
# Envelope build
# ──────────────────────────────────────────────────────────────────────

def test_envelope_for_signing_has_required_fields():
    envelope = build_envelope_for_signing(_valid_request())
    expected = {
        "receipt_id", "version", "issuer", "agent_identity",
        "human_delegate", "runtime", "protocol", "action_type",
        "tool_server", "input_hash", "output_hash", "side_effect",
        "timestamp",
    }
    assert expected.issubset(set(envelope.keys()))


def test_envelope_version_locked_to_v01():
    envelope = build_envelope_for_signing(_valid_request())
    assert envelope["version"] == ACTION_RECEIPT_VERSION
    assert envelope["version"] == "garl/action-receipt/v0.1"


def test_envelope_agent_identity_uses_did_garl():
    envelope = build_envelope_for_signing(_valid_request(
        agent_id="22222222-2222-2222-2222-222222222222"
    ))
    assert envelope["agent_identity"] == "did:garl:22222222-2222-2222-2222-222222222222"


def test_envelope_normalizes_hashes_to_lowercase():
    envelope = build_envelope_for_signing(_valid_request(
        input_hash="A" * 64,
        output_hash="B" * 64,
    ))
    assert envelope["input_hash"] == "a" * 64
    assert envelope["output_hash"] == "b" * 64


def test_envelope_timestamp_is_z_suffixed_iso():
    envelope = build_envelope_for_signing(_valid_request())
    assert envelope["timestamp"].endswith("Z")
    # Loosely verify ISO-8601 shape
    assert "T" in envelope["timestamp"]


def test_envelope_optional_fields_omitted_when_not_provided():
    envelope = build_envelope_for_signing(_valid_request())
    # The build_envelope_for_signing helper includes None for human_delegate,
    # but should not include capability_request/policy_decision/cost.
    assert "capability_request" not in envelope
    assert "policy_decision" not in envelope
    assert "cost" not in envelope
    assert "previous_receipt_hash" not in envelope
    assert "attestations" not in envelope


# ──────────────────────────────────────────────────────────────────────
# Acceptance: every enum the spec advertises round-trips
# ──────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("runtime", [
    "claude-code", "cursor", "copilot", "aider", "codex",
    "mcp-client", "langchain", "crewai", "llamaindex",
    "semantic-kernel", "custom",
])
def test_all_advertised_runtimes_accepted(runtime):
    _validate_input(_valid_request(runtime=runtime))


@pytest.mark.parametrize("protocol", [
    "github", "mcp", "a2a", "acp", "ap2", "x402", "raw-http",
])
def test_all_advertised_protocols_accepted(protocol):
    _validate_input(_valid_request(protocol=protocol))


@pytest.mark.parametrize("action_type", [
    "code_write", "api_call", "payment", "browser_action",
    "file_op", "tool_call",
])
def test_all_advertised_action_types_accepted(action_type):
    _validate_input(_valid_request(action_type=action_type))


@pytest.mark.parametrize("side_effect", ["none", "reversible", "irreversible"])
def test_all_side_effect_classes_accepted(side_effect):
    _validate_input(_valid_request(side_effect=side_effect))
