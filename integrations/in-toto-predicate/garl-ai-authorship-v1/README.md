# in-toto predicate: `garl/ai-authorship-v1`

Predicate type identifier: **`https://garl.ai/ai-authorship/v1`**

## What it claims

A single GARL receipt attests that an identified agent (by UUID) executed a task and produced an output whose content hash is the subject `sha256` digest. The agent's identity, the task metadata, the execution outcome (success/failure/partial), the cost/latency, and a link back to the GARL signing-key registry are carried in the predicate body.

GARL's own ECDSA-secp256k1 signer produces the signature that appears in the DSSE envelope when the receipt is exported as `?format=in-toto`. Verifiers who want a second-anchor can re-wrap the statement and sign it with Sigstore Cosign or a private signer.

## Schema

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "garl-trace:<trace-uuid>",
      "digest": { "sha256": "<64-hex trace_hash>" }
    }
  ],
  "predicateType": "https://garl.ai/ai-authorship/v1",
  "predicate": {
    "agent_id": "<agent-uuid>",
    "agent_name": "<string>",
    "task_description": "<string>",
    "status": "success" | "failure" | "partial",
    "category": "<string>",
    "duration_ms": 0,
    "cost_usd": 0,
    "token_count": 0,
    "signed_at_unix": 1776269706,
    "signing_epoch": "original" | "pre-v0.3-unsigned-legacy",
    "canonical_registry": "https://api.garl.ai"
  }
}
```

## DSSE envelope (what `?format=in-toto` actually returns per-trace)

```json
{
  "payloadType": "application/vnd.in-toto+json",
  "payload": "<base64 of the Statement JSON above>",
  "signatures": [
    {
      "keyid": "<16-hex key_id from /.well-known/garl-keys.json>",
      "sig": "<base64 of the ECDSA-secp256k1 signature bytes>"
    }
  ]
}
```

## Verifying a predicate

1. Base64-decode `payload` — you now have the in-toto Statement JSON.
2. Base64-decode `signatures[].sig` — you now have raw ECDSA signature bytes.
3. Look up `signatures[].keyid` in `https://api.garl.ai/.well-known/garl-keys.json`. Use the matching `public_key_hex` as the verifying key.
4. Recompute the canonical JSON of the Statement (sorted keys, no whitespace) and verify the signature against SHA-256 of that canonical bytes.

The canonical registry's JSON is produced with `json.dumps(..., sort_keys=True, separators=(",", ":"))`; verifiers must match that encoding exactly.

## Why this predicate exists

GARL is deliberately positioned inside the supply-chain attestation ecosystem rather than alongside it. Emitting a first-class in-toto predicate means:

- **OpenSSF Scorecard** can add a check for `uses-ai-authorship-attestation`.
- **GitHub Artifact Attestations** consumers can wrap GARL statements with Cosign or Rekor as a second anchor.
- **SLSA-aware build systems** can treat GARL receipts as an input to their own provenance predicates.

## Related

- SLSA v1.1 provenance format: available via `?format=slsa-v1.1` on the same `/agents/{id}/audit` endpoint.
- Key registry: [`/.well-known/garl-keys.json`](https://api.garl.ai/.well-known/garl-keys.json).
- Ecosystem positioning: [`docs/ecosystem.md`](../../../docs/ecosystem.md).
