# Launch credentials & publishing inventory

_2026-04-15, post-PR#3 merge. Snapshot of what an agent can publish on
its own versus what still requires a human-held credential. Not for
use this launch — reference for the next one._

## Publishing channels

| Channel | Where | Agent can publish solo? | What blocks full automation |
|---|---|---|---|
| **PyPI** (`garl-protocol`) | pypi.org | ✅ Yes | Token now stored in macOS keyring (`https://upload.pypi.org/legacy/`, `__token__`, 213 chars). `twine upload` reads silently. |
| **npm** (`@garl-protocol/mcp-server`, `@garl-protocol/sdk`) | registry.npmjs.org | ✅ Yes | Shell session has `npm whoami=garlai`. No MFA prompt observed in prior publishes. |
| **GitHub Releases** (monorepo) | github.com/Garl-Protocol/garl/releases | ✅ Yes | `gh auth status = ardakutsal`. `gh release create …` scripted. |
| **GitHub Releases** (Action repo) | github.com/Garl-Protocol/garl-receipt-action/releases | ✅ Yes | Same `gh` auth. |
| **GitHub Marketplace listing (Action)** | github.com/marketplace/actions/garl-receipt | ❌ **UI-only** | GitHub requires a browser click on the release-edit page: "Publish this Action to the GitHub Marketplace". No REST/GraphQL mutation. Same for category selection. |
| **GitHub App publishing (PR Bot)** | github.com/apps/garl-pr-bot | ❌ **UI-only** (register) + ✅ (update later) | Initial App registration must happen via https://github.com/settings/apps/new?manifest=... — a single human click. After that, App settings can be patched via `gh api /apps/...`. |
| **dev.to** | dev.to/ardakutsal | ❌ UI-only | dev.to has an API but the free tier requires Premium to publish posts programmatically. Human publishes the pre-written draft. |
| **Hacker News Show HN** | news.ycombinator.com | ❌ UI-only | No publish API. Human submits. Karma ≥50 required on the posting account. |
| **X / Twitter thread** | x.com/@\<handle\> | 🟡 Possible with paid API | X API v2 POST tweets is gated behind Basic tier ($100/mo) and above. Human posts this launch; automation viable if the budget is approved. |
| **LinkedIn** | linkedin.com/in/\<handle\> or company page | 🟡 UI-only for personal, API for company | Personal post is UI-only. Company page needs an LinkedIn Marketing Developer Platform app (multi-day review). Human posts. |
| **Reddit** (r/MachineLearning, r/programming, r/compliance, etc.) | reddit.com | 🟡 PRAW + account age | `praw` + account with ≥30 days + karma threshold. We don't have the account wired today. Human posts per subreddit. |
| **Product Hunt** | producthunt.com | 🟡 UI-only (maker hand-off) | Launch needs a "maker" account with standing; no scripted publish. |
| **Slack — relevant communities (MCP, AI agents, Sigstore)** | various workspaces | ❌ UI-only | Each workspace needs a user token; we don't hold them. Human posts. |

## Automation-ready (green) — 4 channels

- PyPI
- npm
- GitHub Releases (monorepo + Action repo)

Everything else needs a one-off human click. The Marketplace and App
registration clicks are **install-time, not per-release** — they happen
once.

## What we fixed this launch

- ✅ PyPI token now in macOS keyring so next release is one command
- ✅ Main branch protection (Backend Tests + Frontend Build required)
- ✅ v16 pr_bot_summaries migration applied
- ✅ Launch drafts use accurate Octoverse-anchored stats + triple
  compliance pitch + accurate "12 named MCP tools + batch variants"

## What the NEXT launch should bake in

1. **Twitter Basic tier** if viral velocity matters — $100/mo.
2. **Reddit publishing account** (PRAW + seasoned account) — 30-day
   lead time on account age.
3. **LinkedIn company page + Marketing Dev Platform app** if enterprise
   reach matters — multi-week lead time.
4. **Scripted dev.to cover-image generation** — dev.to API *reads* drafts
   via v1, publishes via v1 (paid tier). Evaluate if > 1 launch per
   quarter.
5. **GitHub App webhook secret rotation cadence** — add to ops
   calendar once we're live.

_File is informational; does not affect any automated path._
