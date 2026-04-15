# Self-hosting GARL Protocol

The code in this repository is Apache 2.0 — you can run your own GARL deployment for internal audit trails, regulated-industry isolation, or research. This document covers the practical setup and the one thing that is explicitly **not** transferable: the phrase "GARL Verified".

## Why self-host

- **Regulatory isolation.** You need your ledger inside a specific jurisdiction or VPC.
- **Internal-only receipts.** AI-commit provenance for proprietary repos where a public URL is a non-starter.
- **Research.** Experimenting with alternate scoring formulas, new certificate shapes, or integration prototypes before proposing them upstream.

If your need is "get a receipt URL I can share publicly", you can use the canonical registry at `https://api.garl.ai` directly — no self-hosting required, free.

## Architecture

A self-hosted deployment needs three things:

1. **Backend** (`backend/`) — FastAPI + Python 3.10+. Deploys to Railway, Fly.io, Render, any container runtime. Env vars: `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SIGNING_PRIVATE_KEY_HEX`, `ALLOWED_ORIGINS`.
2. **Database** (`supabase/migrations/`) — PostgreSQL 14+. Supabase is easiest because the immutable-ledger triggers in v03 and the RLS policies are already migration-scripted. Self-hosted Postgres works too — apply migrations with `psql`.
3. **Frontend** (`frontend/`, optional) — Next.js 14. Only needed if you want the receipt cards and dashboard UI.

See `docker-compose.yml` at the repo root for a single-command local dev setup.

## Generating a signing key

```
python3 -c "from ecdsa import SigningKey, SECP256k1; print(SigningKey.generate(SECP256k1).to_string().hex())"
```

Set the output as `SIGNING_PRIVATE_KEY_HEX`. Receipts issued by your deployment are signed with this key; their `proof.key_id` (first 16 hex of SHA-256 over the public key) uniquely identifies your deployment.

## Publishing your public key

When a third party wants to verify a receipt your deployment issued, they need your public key. Two conventions:

1. **JWKS-style registry** at `<your-host>/.well-known/garl-keys.json` — the default route in `app/main.py` serves this automatically, matching the canonical registry's format.
2. **Out-of-band** — publish the hex public key in your README or internal docs and have verifiers hard-code it.

Supporting key rotation: set the `GARL_RETIRED_KEYS_JSON` environment variable to a JSON array of previous keys when you rotate. See `docs/security.md` for the full procedure.

## What you **cannot** call your deployment

The trademark policy ([TRADEMARK.md](../TRADEMARK.md)) asks that self-hosted deployments do not describe themselves as:

- "the GARL Registry"
- "GARL Verified" (this is a property of the canonical registry at `api.garl.ai`)
- "Official GARL"

Good phrasing: "internal GARL-format receipts", "self-hosted GARL deployment", "GARL-compatible".

## Federation, bridging, and the canonical registry

A self-hosted deployment can **bridge** to the canonical registry if both sides want that:

- Your deployment's trust receipts remain local.
- Optionally, a subset can be re-anchored to the canonical registry via the public `POST /api/v1/verify` endpoint with an API key of your canonical-registry agent.

Federation across multiple self-hosted deployments is out of scope today. If you need it, open an issue — we want to understand the use case before designing the primitive.

## Updating to new versions

Self-hosted deployments should follow the canonical registry's release cadence (see `CHANGELOG.md` or GitHub Releases). Database migrations are cumulative and idempotent within a major version line. Breaking changes are announced on the canonical registry with a minimum 14-day notice period (see [GOVERNANCE.md](../GOVERNANCE.md)).
