# Security

GARL Protocol is designed with defense-in-depth principles. Every layer — from data storage to API responses — enforces security constraints.

## Cryptographic Integrity

- **ECDSA Certificates**: Every execution trace is signed with secp256k1, producing a tamper-proof certificate with SHA-256 content hash
- **Immutable Traces**: PostgreSQL triggers prevent `UPDATE` and `DELETE` on `traces` and `reputation_history` tables
- **API Key Hashing**: Keys are stored as SHA-256 hashes — plaintext keys are never persisted

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
