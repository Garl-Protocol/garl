# Security

GARL Protocol is designed with defense-in-depth principles. Every layer — from data storage to API responses — enforces security constraints.

## Cryptographic Integrity

- **ECDSA Certificates**: Every execution trace is signed with secp256k1, producing a tamper-proof certificate with SHA-256 content hash
- **Immutable Traces**: PostgreSQL triggers prevent `UPDATE` and `DELETE` on `traces`, `reputation_history`, and `endorsements` tables
- **API Key Hashing**: Keys are stored as SHA-256 hashes — plaintext keys are never persisted
- **Public Key Registry**: Every certificate carries a deterministic `proof.key_id` (first 16 hex of SHA-256 over the public key). Clients verifying a receipt should resolve that `key_id` against the **canonical registry** at `https://api.garl.ai/.well-known/garl-keys.json` (mirrored at `/api/v1/keys`). Retired keys remain listed — receipts issued before a rotation stay verifiable.
- **Signing Epoch Disclosure**: `GET /verify/{hash}` responses include `signing_epoch` ∈ `{"original", "pre-v0.3-unsigned-legacy"}`. Only `"original"` implies unbroken cryptographic chain-of-custody from the moment of trace submission. Pre-v0.3 traces pre-date the signing pipeline and are marked as such — the certificate returned for those traces is a post-hoc re-signature for verification convenience, not an original chain-of-custody proof.

### Key Rotation Procedure

1. Generate a new secp256k1 private key and set `SIGNING_PRIVATE_KEY_HEX` to the new value.
2. Append the previous public key (and the ISO timestamp of rotation) to the `GARL_RETIRED_KEYS_JSON` environment variable — JSON array of `[{"public_key_hex": "...", "retired_at": "YYYY-MM-DDTHH:MM:SSZ", "note": "..."}]`.
3. Restart the backend. New receipts are signed by the new key; old receipts continue to verify against their retired `key_id`.
4. The registry endpoint updates automatically on next request (cached 5 minutes at the CDN edge).

## API Security

- **Rate Limiting**: In-memory window-based limiter on all endpoints, with rate limit headers on every response
- **Input Validation**: Strict Pydantic schemas reject malformed data with descriptive error messages
- **XSS Prevention**: HTML stripping + regex sanitization on all user-supplied text fields
- **SQL Injection**: Parameterized queries via Supabase client — no raw SQL concatenation
- **SSRF Prevention**: Webhook URLs validated for HTTPS and blocked for private/internal IP ranges
- **Timing-Safe Comparison**: All API key validations use `hmac.compare_digest()` to prevent timing attacks
- **Duplicate Trace Protection**: Traces are deduplicated by content hash to prevent replay-based score inflation
- **CORS**: Configurable allowed origins via `ALLOWED_ORIGINS` environment variable

## Transport Security

All responses include security headers:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'none'; frame-ancestors 'none'` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |

## Database Security

- **Row Level Security (RLS)**: Enabled on all Supabase tables
- **Service Role Isolation**: Public API uses anon key; service role key is restricted to backend operations
- **PII Masking**: Optional SHA-256 hashing of sensitive input/output data in traces

## Webhook Security

- **HMAC Signatures**: Webhook payloads are signed with SHA-256 HMAC using a per-webhook secret
- **Retry Logic**: Failed deliveries are retried with exponential backoff

## GDPR Compliance

- **Soft Delete**: `DELETE /api/v1/agents/{id}` marks agents as deleted without removing data
- **Anonymization**: `POST /api/v1/agents/{id}/anonymize` irreversibly hashes all PII fields
