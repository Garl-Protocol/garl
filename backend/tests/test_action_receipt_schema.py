"""Validate the Action Receipt v0.1 JSON Schema is itself well-formed and
that the example in the spec passes the schema."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
SCHEMA_PATH = REPO_ROOT / "protocol" / "schema" / "action-receipt-v0.1.json"
SPEC_PATH = REPO_ROOT / "protocol" / "spec" / "action-receipt-v0.1.md"


def _load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_file_exists():
    assert SCHEMA_PATH.exists(), f"Schema missing: {SCHEMA_PATH}"


def test_schema_parses_as_json():
    schema = _load_schema()
    assert isinstance(schema, dict)
    assert schema["$schema"].startswith("https://json-schema.org/")
    assert schema["$id"].endswith("/action-receipt-v0.1.json")


def test_schema_locks_version_const():
    schema = _load_schema()
    assert schema["properties"]["version"]["const"] == "garl/action-receipt/v0.1"


def test_required_envelope_present():
    schema = _load_schema()
    required = set(schema["required"])
    expected = {
        "receipt_id", "version", "issuer", "agent_identity",
        "human_delegate", "runtime", "protocol", "action_type",
        "input_hash", "output_hash", "side_effect", "timestamp",
        "signature", "verification_key_id",
    }
    assert required == expected


def test_side_effect_classes_match_spec():
    schema = _load_schema()
    side_effect_values = set(schema["properties"]["side_effect"]["enum"])
    assert side_effect_values == {"none", "reversible", "irreversible"}


def test_runtime_enum_includes_all_known_runtimes():
    schema = _load_schema()
    runtimes = set(schema["properties"]["runtime"]["enum"])
    must_have = {"claude-code", "cursor", "copilot", "aider", "codex", "mcp-client", "custom"}
    assert must_have.issubset(runtimes)


def test_protocol_enum_includes_payment_rails():
    """Action receipts that ride payment rails must declare which one. Both
    Stripe ACP, Google AP2, and Coinbase x402 must be addressable."""
    schema = _load_schema()
    protocols = set(schema["properties"]["protocol"]["enum"])
    assert {"acp", "ap2", "x402"}.issubset(protocols)


def test_capability_request_subschema_exists():
    schema = _load_schema()
    cap = schema["$defs"]["capability_request"]
    assert "token_hash" in cap["required"]
    assert "side_effect_class" in cap["required"]
    assert set(cap["properties"]["side_effect_class"]["enum"]) == {"none", "reversible", "irreversible"}


def test_input_and_output_hashes_are_sha256_hex():
    schema = _load_schema()
    pat_in = schema["properties"]["input_hash"]["pattern"]
    pat_out = schema["properties"]["output_hash"]["pattern"]
    assert pat_in == "^[a-f0-9]{64}$"
    assert pat_out == "^[a-f0-9]{64}$"


def test_verification_key_id_is_16_hex():
    """Matches first-16-of-sha256 of public key — used as a stable lookup
    handle into /.well-known/garl-keys.json."""
    schema = _load_schema()
    pat = schema["properties"]["verification_key_id"]["pattern"]
    assert pat == "^[a-f0-9]{16}$"


def test_no_additional_properties_at_top_level():
    """Strict envelope to prevent silent drift between issuers and
    verifiers. Optional fields are explicitly listed in properties."""
    schema = _load_schema()
    assert schema["additionalProperties"] is False


def test_spec_file_exists():
    assert SPEC_PATH.exists(), f"Spec missing: {SPEC_PATH}"


def test_spec_locks_same_version_as_schema():
    """Spec and schema must agree on the version constant. If they drift
    consumers can't tell which to trust."""
    schema = _load_schema()
    spec = SPEC_PATH.read_text(encoding="utf-8")
    schema_version = schema["properties"]["version"]["const"]
    assert schema_version in spec, (
        f"Schema version {schema_version!r} not mentioned in spec; "
        "spec and schema have drifted."
    )


def _example_from_spec() -> dict:
    """Pull the JSON example block out of the spec markdown and parse it."""
    text = SPEC_PATH.read_text(encoding="utf-8")
    in_json = False
    lines = []
    for raw in text.splitlines():
        if raw.strip() == "```json" and not in_json:
            in_json = True
            lines = []
            continue
        if raw.strip() == "```" and in_json:
            candidate = "\n".join(lines)
            if '"receipt_id"' in candidate and '"version": "garl/action-receipt/v0.1"' in candidate:
                # Spec contains illustrative placeholders (e.g. "<hex ...>") — accept
                # invalid signature for the example test, since the schema doesn't
                # require runtime hex match for the signature placeholder.
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError:
                    pass
            in_json = False
        elif in_json:
            lines.append(raw)
    raise AssertionError("Could not find a JSON example block in the spec")


def test_spec_example_parses():
    """The illustrative example in the spec must at least be syntactically
    valid JSON. Schema conformance is checked when jsonschema is available."""
    example = _example_from_spec()
    assert example["version"] == "garl/action-receipt/v0.1"
    assert example["side_effect"] in {"none", "reversible", "irreversible"}


def test_spec_example_validates_against_schema_if_jsonschema_available():
    try:
        from jsonschema import Draft202012Validator  # type: ignore
    except ImportError:
        pytest.skip("jsonschema not installed; install to run schema conformance test")
    schema = _load_schema()
    example = _example_from_spec()
    # The example uses placeholder text for `signature`; replace with a
    # valid hex run so the pattern-only validator is happy. We're testing
    # the schema, not the cryptography here.
    if not all(c in "0123456789abcdef" for c in example["signature"].lower()):
        example["signature"] = "ab" * 32
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(example), key=lambda e: e.path)
    assert not errors, f"Example fails schema: {[e.message for e in errors]}"
