# Twitter / X launch thread — draft

**Handle:** @GARLProtocol (or personal if larger reach)

**Schedule:** weekday 09:00 or 15:00 ET

---

## Tweet 1 (lead, attaches OG preview)

```
Nearly half of all new code on GitHub is AI-touched (Octoverse 2025).

Git says who typed `git commit`.
It doesn't say which model wrote it.

We fixed that.

GARL for Code — cryptographic receipts for every AI-authored commit.
Open source. 5-line GitHub Action or one-click GitHub App.

Live demo → garl.ai/r/6ff83db8
```

## Tweet 2 (how it works)

```
The action walks your PR's commits, detects AI co-author trailers
(Claude, Cursor, Copilot, Aider, Codex), and signs each qualifying
commit with ECDSA-secp256k1.

PR gets a sticky comment + neutral check.
Each commit gets a shareable receipt URL:

🔐 GARL Verified AI Code
├── Model: claude-opus-4-6
├── Files touched: 12
├── Signed: ECDSA-secp256k1 (RFC 6979) ✓
└── Receipt: garl.ai/r/a8f3c2d1
```

## Tweet 3 (why it matters)

```
CA SB 942 live since Jan 2026.
EU AI Act Code of Practice applicable Aug 2026.
ISO 42001 Annex B already audited against.

SLSA / Sigstore sign build artifacts.
C2PA signs media.
Nobody signed AI-authored source commits.

Until now.

Apache 2.0. No SaaS lock-in. No black-box scoring. Full monorepo
on GitHub.
```

## Tweet 4 (install)

```
5 lines of YAML, 2 secrets, 1 minute:

📂 .github/workflows/garl-receipt.yml

- uses: Garl-Protocol/garl-receipt-action@v1.0.0
  with:
    garl-api-key: ${{ secrets.GARL_API_KEY }}
    garl-agent-id: ${{ secrets.GARL_AGENT_ID }}

Full setup: garl.ai/for-code
```

## Tweet 5 (call to action)

```
Building this because AI code provenance is going to be a procurement
requirement faster than most teams think.

If you ship AI-assisted code in a regulated context — finance, health,
gov — try it today. Feedback very welcome.

🌐 garl.ai/for-code
🐙 github.com/Garl-Protocol/garl
```

## Notes

- Keep Tweet 1 under 260 chars so there's room for the OG preview card
  that Twitter generates when it fetches garl.ai/r/6ff83db8.
- Quote-tweet some well-known AI-infrastructure voices (Simon Willison,
  Swyx, Addy Osmani) with the live receipt demo if they engage.
- Reply to every comment in the first 2 hours — Twitter's algo
  rewards author engagement heavily.
