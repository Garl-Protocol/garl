# GARL Receipt — GitHub Action

Sign every AI-authored commit in your pull requests with a cryptographically
verifiable **GARL Receipt**. When Claude Code, Cursor, GitHub Copilot, or
another coding agent writes code in your repo, this action detects it, posts
a signed receipt URL on the PR, and updates a single sticky comment with a
rolling summary.

> **Why?** Reviewers, auditors, and your future self should be able to see
> exactly which commits were AI-authored and verify the claim with a
> tamper-evident ECDSA-secp256k1 signature. EU AI Act Article 50 compliance
> starts with provenance.

## What it looks like on a PR

```
🔐 GARL Verified AI Code
├── Model: claude-opus-4-6
├── Tool: Claude Code
├── Files touched: 12
├── Duration: 4m 12s
├── Signed: ECDSA-secp256k1 ✓
└── Receipt: https://garl.ai/r/a8f3c2d1
```

Plus a rolling PR comment like:

> **3 of 5 commits** signed as AI-authored.  
> Breakdown: 2 Claude Code, 1 GitHub Copilot

And an informational (neutral) check named `GARL Receipt` on the PR.

## Setup (5 lines of YAML)

1. Register a GARL agent for this repo — either via the
   [MCP tool](https://garl.ai/docs#mcp-server) `garl_register_agent` or via
   `curl`:
   ```bash
   curl -sX POST https://api.garl.ai/api/v1/agents/auto-register \
     -H "Content-Type: application/json" \
     -d '{"name":"gh-<owner>-<repo>","framework":"github-action"}'
   ```
   Save `agent_id` and `api_key` from the response.

2. Add two repository secrets:
   - `GARL_AGENT_ID` — the agent UUID
   - `GARL_API_KEY` — the returned key

3. Add the workflow (`.github/workflows/garl-receipt.yml`):
   ```yaml
   name: GARL Receipt
   on:
     pull_request:
       types: [opened, synchronize, reopened]
   jobs:
     sign:
       runs-on: ubuntu-latest
       permissions:
         contents: read
         pull-requests: write
         checks: write
       steps:
         - uses: actions/checkout@v4
           with:
             fetch-depth: 0  # needed so git log can walk base..head
         - uses: Garl-Protocol/garl/integrations/github-action-receipt@main
           with:
             garl-api-key: ${{ secrets.GARL_API_KEY }}
             garl-agent-id: ${{ secrets.GARL_AGENT_ID }}
   ```

Open a PR that includes an AI co-author trailer — the action signs it.

## Inputs

| Name | Required | Default | Purpose |
|---|---|---|---|
| `garl-api-key` | ✅ | — | Repo agent API key (secret) |
| `garl-agent-id` | ✅ | — | Repo agent UUID (secret) |
| `min-confidence` | | `0.5` | Lowest AI-authorship confidence (0.0–1.0) that still produces a receipt. Below this, the commit is summarized but not signed. |
| `comment` | | `true` | Post/update a sticky PR comment with the receipt summary. |
| `check` | | `true` | Post an informational (neutral) GitHub check run on the PR. |
| `api-url` | | `https://api.garl.ai/api/v1` | GARL API base URL (override for self-hosted). |
| `site-url` | | `https://garl.ai` | Frontend base URL used in receipt links. |

## Outputs

| Name | Description |
|---|---|
| `receipts-json` | JSON array of `{commit, tool, confidence, model, receipt_url}` for each signed commit. |
| `ai-commit-count` | Integer count of commits signed in this run. |

## Detection rules

The action reads each commit's subject + body and scores AI authorship:

| Signal | Confidence |
|---|---|
| `Co-Authored-By: ...Claude` / `...Cursor` / `...GitHub Copilot` / `...aider` / `...codex` | **1.0** |
| `Generated with [Claude Code]` | 0.9 |
| Explicit model name (`claude-opus-4-6`, `gpt-4.1-mini`, etc.) | 0.6–0.7 |
| `🤖 Generated with ...` (emoji marker) | 0.6 |
| `cursor` heuristic | 0.4 |

Commits below `min-confidence` are listed as *no AI marker* but never
fail the workflow. The check run is always `neutral` — informational,
non-blocking.

## Privacy & data

Only metadata is sent to GARL:

- commit SHA, subject, files-changed count
- detected AI tool + confidence + model name (if any)
- commit duration (git committer date − author date)

Source code, diffs, and file contents are **never uploaded**.

## See also

- [GARL Trust Gate action](../github-action) — pre-deployment trust-score check
- [MCP server](../mcp-server) — 20 trust tools for Claude Desktop / Cursor
- [garl.ai/docs](https://garl.ai/docs) — full protocol reference

Apache 2.0 · Part of [GARL Protocol](https://garl.ai).
