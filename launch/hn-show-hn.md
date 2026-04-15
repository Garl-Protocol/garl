# Show HN — draft

**Title (80 char max):**

```
Show HN: GARL for Code – Signed receipts for AI-generated commits (open source)
```

**URL field:**

```
https://garl.ai/for-code
```

**Text field:**

```
Nearly half of all new code on GitHub is AI-touched (Octoverse 2025),
but git history only records the human author — not the model, not the
prompt, not the verifier. We built a GitHub Action (and a companion
GitHub App) that signs every AI-authored commit with ECDSA-secp256k1
and posts a verifiable receipt on the PR.

Detects Claude Code, Cursor, GitHub Copilot, Aider, and Codex via
co-author trailers + model-name heuristics. Each qualifying commit gets
a signed trace on the GARL ledger and a short shareable URL
(garl.ai/r/{short}) with a cryptographic proof card and an Open Graph
preview for Slack / X / PR comments. An informational (neutral, never
blocking) GitHub check summarizes "N of M commits signed" per PR.

Five lines of YAML to install. Two repo secrets. No diffs or source
are uploaded — only commit SHA, subject, file-count, detected tool,
and confidence. Apache 2.0, full monorepo on GitHub.

Why now: California SB 942 (AI Transparency Act) is in force since
Jan 1, 2026. The EU AI Act Code of Practice on AI-generated content
(final June 2026, applicable alongside Article 50 in August 2026)
wants machine-readable disclosure. ISO/IEC 42001 Annex B is already
audited against. Enterprises need AI-code provenance today, and there
wasn't an open-source primitive for it — SLSA/Sigstore target build
artifacts, C2PA targets media. GARL emits an in-toto predicate
(`garl/ai-authorship/v1`) so existing supply-chain tooling can consume
the same receipt via `cosign verify-blob` or any Rekor-aware verifier.

Stack:
- FastAPI + Supabase/Postgres (backend)
- Next.js 14 (frontend, SSR receipts + @vercel/og)
- Composite GitHub Action (bash + Python stdlib, zero build step)
- ECDSA-secp256k1 signatures (same curve as Ethereum, natively
  verifiable by ERC-8004 consumers)
- Python + JS SDKs, MCP server (12 named tools + batch variants) for
  Claude Desktop / Cursor, plus `garl-verify` CLI for offline receipt
  verification (`pip install garl-protocol`)

Live receipt (real data from a monitoring agent running 20 traces/day):
https://garl.ai/r/6ff83db8

GitHub (protocol): https://github.com/Garl-Protocol/garl
GitHub (action): https://github.com/Garl-Protocol/garl-receipt-action
Landing: https://garl.ai/for-code

Feedback welcome — especially from anyone wiring AI provenance into
regulated pipelines.
```

## Notes for Arda

- Post under `ardakutsal` (or whichever HN account has karma > 50).
- Tuesday–Thursday 08:00–10:00 ET is the well-established sweet spot.
  Avoid Mondays (overload) and Fridays (drop-off).
- Reply to the first 2–3 comments within 30 minutes — HN ranking
  rewards author engagement.
- Pre-warm by posting the Dev.to article 24–48h earlier so there's a
  secondary search hit when people look "GARL for Code".
- Do NOT self-upvote from alt accounts — HN shadowbans.
