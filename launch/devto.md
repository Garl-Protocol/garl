# Dev.to long-form — draft

**Title:**

```
GARL for Code: cryptographic receipts for every AI-generated commit
```

**Tags:** `ai`, `github`, `devops`, `opensource`

**Cover image:** export of the receipt page (`https://garl.ai/r/6ff83db8`) or the PR mockup from `/for-code`.

---

## Body

In 2026, 46% of new code is AI-generated. Claude Code, Cursor, GitHub
Copilot, Aider, Codex — every modern IDE invites an agent into the
commit. But `git log` only remembers who typed `git commit`. It
doesn't remember which model wrote the lines, which prompt produced
them, or whether a human reviewer ever saw the diff before it merged.

That gap is about to become expensive. The EU AI Act's Article 50
provenance obligations land **August 2, 2026**, with fines up to
€35M / 7% of global turnover for non-compliance. Procurement
questionnaires are already starting to ask "can you prove this output
came from a specific model?" Most teams can't.

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
├── Signed: ECDSA-secp256k1 ✓
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
      - uses: Garl-Protocol/garl/integrations/github-action-receipt@v1.1.0
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
| `Co-Authored-By: ... Claude / Cursor / Copilot / Aider / Codex` | 1.0 |
| `Generated with [Claude Code]` | 0.9 |
| Explicit model name (`claude-opus-4-6`, `gpt-4.1-mini`, …) | 0.6–0.7 |
| `🤖 Generated with ...` emoji marker | 0.6 |
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

1. **Scale:** 92% of US developers use AI tools daily. Half of all
   new code is AI-generated. The provenance gap grows every week.
2. **Regulation:** EU AI Act Article 50. NIST AI Agent Standards work.
   Procurement questionnaires. The "who wrote it?" question is
   stopping being optional.
3. **Tooling vacuum:** SLSA / Sigstore sign *build artifacts*. C2PA
   signs *media*. The existing "AI Provenance Protocol" is a spec,
   not a product. Nobody was signing AI-authored source commits.

GARL for Code is the open-source primitive for that gap.

### Related — for agent developers

GARL for Code is the first "vertical" of the broader GARL Protocol:
an open trust layer for AI agents. If you're building agents instead
of shipping code, there's also:

- A Python SDK (`garl-protocol`) and a JavaScript SDK (`@garl-protocol/sdk`)
  for submitting traces and querying trust scores
- An MCP server (`@garl-protocol/mcp-server`) with 20 tools for Claude
  Desktop / Cursor
- A public REST API with rate-limited reads, ECDSA-signed traces, and
  an immutable Postgres ledger

All part of the same Apache-2.0 monorepo.

### Links

- **Landing page:** https://garl.ai/for-code
- **Live receipt example:** https://garl.ai/r/6ff83db8
- **GitHub Action:** https://github.com/Garl-Protocol/garl/tree/main/integrations/github-action-receipt
- **Full repo:** https://github.com/Garl-Protocol/garl

Feedback very welcome — especially from teams wiring AI provenance
into regulated pipelines.
