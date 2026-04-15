# Dev.to long-form — draft

**Title:**

```
GARL for Code: cryptographic receipts for every AI-generated commit
```

**Tags:** `ai`, `github`, `devops`, `opensource`

**Cover image:** export of the receipt page (`https://garl.ai/r/6ff83db8`) or the PR mockup from `/for-code`.

---

## Body

In 2026, nearly half of all new code on GitHub is AI-touched (per the
Octoverse 2025 report; 80% of new devs pick up Copilot in their first
week). Claude Code, Cursor, GitHub Copilot, Aider, Codex — every
modern IDE invites an agent into the commit. But `git log` only
remembers who typed `git commit`. It doesn't remember which model
wrote the lines, which prompt produced them, or whether a human
reviewer ever saw the diff before it merged.

That gap is about to become expensive. Three instruments are
converging:

- **California SB 942 (AI Transparency Act)** — in force since
  **Jan 1, 2026**. Requires machine-detectable provenance for AI
  content served to California users.
- **EU AI Act Code of Practice on AI-generated content** — final
  guidance expected **June 2026**, applicable alongside Article 50
  in August 2026. Article 50 itself targets deepfakes + public-interest
  text, but the Code of Practice is where code-specific transparency
  obligations are most likely to land. Signed machine-readable
  disclosures are the preferred shape.
- **ISO/IEC 42001:2023 Annex B** — AI management system audit
  evidence. Already live; Microsoft 365 Copilot is certified; enterprise
  procurement gates reference it.

Procurement questionnaires are already starting to ask "can you prove
this output came from a specific model?" Most teams can't.

So we built **GARL for Code** — an open-source GitHub Action that
signs every AI-authored commit with ECDSA-secp256k1 and posts a
verifiable receipt URL on the PR.

### What you see on a PR

When you open a PR that includes an AI co-author trailer (e.g.
`Co-Authored-By: Claude <noreply@anthropic.com>`), the action walks
the commit range, scores each commit for AI authorship, and posts a
sticky comment + an informational GitHub check:

```
🔐 GARL Verified AI Code
├── Model: claude-opus-4-6
├── Tool: Claude Code
├── Files touched: 12
├── Duration: 4m 12s
├── Signed: ECDSA-secp256k1 (RFC 6979 deterministic) ✓
└── Receipt: https://garl.ai/r/a8f3c2d1
```

The receipt URL is a public proof card — agent identity, tier, task
description, duration, SHA-256 hash, ECDSA signature — rendering an
Open Graph image so the link previews richly in Slack, Twitter, and
GitHub itself.

### Install

Five lines of YAML, two repo secrets, one workflow file:

```yaml
# .github/workflows/garl-receipt.yml
name: GARL Receipt
on:
  pull_request:
    types: [opened, synchronize, reopened]
jobs:
  sign:
    runs-on: ubuntu-latest
    permissions: { contents: read, pull-requests: write, checks: write }
    steps:
      - uses: actions/checkout@v4
        with: { fetch-depth: 0 }
      - uses: Garl-Protocol/garl-receipt-action@v1.0.0
        with:
          garl-api-key: ${{ secrets.GARL_API_KEY }}
          garl-agent-id: ${{ secrets.GARL_AGENT_ID }}
```

One-time: register a repo agent via the public `/agents/auto-register`
endpoint and save the returned `agent_id` / `api_key` as secrets. The
action refuses to submit anything if either secret is missing.

### How it detects AI authorship

The detection layer is deliberately conservative:

| Signal | Confidence |
|---|---|
| `Co-Authored-By: ... Claude / Cursor / Copilot / Aider / Codex` | 0.95 |
| `Generated with [Claude Code]` body marker | 0.85 |
| Explicit model name (`claude-opus-4-6`, `gpt-4.1-mini`, …) | 0.55 |
| Bare `cursor` heuristic | 0.4 |

Commits below `min-confidence` (default 0.5) are listed in the summary
but never fail the workflow. The check run is always **neutral** —
informational, non-blocking. The action is a provenance tool, not a
gate.

### What actually gets uploaded

Only metadata:

- Commit SHA + subject
- Files-changed count (not the diff, not the contents)
- Detected AI tool + confidence + model name (if visible in the
  message)
- Commit duration (committer_date − author_date)

No source code, no diffs, no file contents. Receipts only surface
task description, status, duration, category, and hashes — never
`input_summary` / `output_summary`.

### Why now

Three forces are colliding:

1. **Scale:** Octoverse 2025 — 80% of new devs pick up Copilot in the
   first week, sub-44% of AI-generated code is accepted unchanged. The
   provenance gap grows every week.
2. **Regulation:** CA SB 942 is already active. The EU AI Act Code of
   Practice lands in June 2026. ISO/IEC 42001 Annex B is already
   audited against today. The "who wrote it?" question stopped being
   optional in January.
3. **Tooling vacuum:** SLSA / Sigstore sign *build artifacts*. C2PA
   signs *media*. GitHub Artifact Attestations sign *artifacts*. Nobody
   was signing AI-authored *source commits* as its own event. GARL
   ships the in-toto predicate `garl/ai-authorship/v1` so the existing
   supply-chain toolchain can consume the same receipt.

GARL for Code is the open-source primitive for that gap.

### What you also get (the rest of the surface)

The Action is the front door; GARL ships the rest of the stack too:

- **`garl-verify` CLI.** `pip install garl-protocol` gives you a binary
  that verifies any receipt offline against the canonical key registry
  — "don't trust, verify". Refuses self-vouched keys.
- **Compliance export.** `GET /api/v1/agents/{id}/audit?format=...` in
  `csv`, `jsonld`, `in-toto` (DSSE), `slsa-v1.1`, `ca-sb942`,
  `iso42001-annexb`, or `c2pa` (Content Credentials adjacent).
- **Policy gate.** `POST /api/v1/policy/check` lets a CI job score a
  set of receipts against a declarative policy (min score, min tier,
  required/forbidden models, signing-epoch requirement) without
  re-implementing rule logic.
- **Sigstore Rekor anchor.** Opt-in env flag
  `ENABLE_REKOR_ANCHOR=true` double-anchors every signature in the
  Sigstore transparency log. Your verifier can `cosign verify-blob`
  against it.
- **PR Bot (GitHub App).** If you don't want to touch YAML, install the
  App at `github.com/apps/garl-pr-bot` — fork-PR safe, HMAC-gated,
  same sticky comment.

Agent-reputation endpoints (`/trust/*`, `/a2a/*`, `/erc8004/*`) are
still supported but carry explicit `Deprecation:` + `Sunset:
2027-04-15` headers — the pivot is to code.

All part of the same Apache-2.0 monorepo.

### Links

- **Landing page:** https://garl.ai/for-code
- **Live receipt example:** https://garl.ai/r/6ff83db8
- **GitHub Action:** https://github.com/Garl-Protocol/garl-receipt-action
- **GitHub Marketplace listing:** https://github.com/marketplace/actions/garl-receipt
- **PR Bot (GitHub App):** https://github.com/apps/garl-pr-bot
- **Public key registry (JWKS-style):** https://api.garl.ai/.well-known/garl-keys.json
- **`garl-verify` CLI on PyPI:** https://pypi.org/project/garl-protocol/
- **Full protocol repo:** https://github.com/Garl-Protocol/garl

Feedback very welcome — especially from teams wiring AI provenance
into regulated pipelines.
