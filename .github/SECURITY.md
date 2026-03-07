# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 1.0.x   | Yes       |
| < 1.0   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in GARL Protocol, please report it responsibly.

**Email:** [security@garl.ai](mailto:security@garl.ai)

Please include:

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Response Timeline

- **Acknowledgment:** Within 48 hours
- **Initial assessment:** Within 5 business days
- **Fix timeline:** Depends on severity — critical issues are patched within 72 hours

## Scope

The following are in scope:

- `api.garl.ai` (REST API, A2A, MCP endpoints)
- `garl.ai` (frontend application)
- `@garl-protocol/mcp-server` (npm package)
- `garl` Python and JavaScript SDKs

The following are **out of scope:**

- Third-party services (Supabase, Railway, Cloudflare)
- Social engineering attacks
- Denial of service attacks

## Disclosure Policy

We follow coordinated disclosure. Please allow us reasonable time to address the issue before any public disclosure. We will credit reporters in our changelog unless anonymity is requested.
