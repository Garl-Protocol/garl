# GARL PR Bot

A GitHub App that posts a sticky **"🔐 GARL Verified AI Code"** comment on every pull request, with the AI-authorship percentage and a verifiable receipt URL. Fork-PR safe because it runs inside a registered App (not an Action), so fork authors never see any secret.

**Day-1 comment format (v1, minimal):**

```
🔐 GARL Verified AI Code

73% AI-authored (8 of 11 commits)
Models: claude-code×6, cursor×2

[Verify all →](https://garl.ai/pr/acme/widgets/42)
```

Plus a neutral GitHub Check Run with the same summary. Never blocks a PR — this is provenance telemetry, not a gate. Policy gating is opt-in via `POST /api/v1/policy/check`.

## Install

1. Visit the public install URL for the canonical App:

    `https://github.com/apps/garl-pr-bot/installations/new`

2. Pick the repositories (or the whole org) you want the App to watch.
3. Done. The first PR opened / synchronised after install gets a sticky comment within ~5 seconds.

Fork-authored PRs also work — the App's webhook is authenticated via HMAC, and the commit list comes back through the installation token that the victim repo already granted to the App. No per-fork secret is ever required.

## Self-host

The App logic ships in the main GARL backend — nothing else to run. To point a fresh GitHub App at your deployment:

1. Create the App from the manifest in [`app-manifest.json`](./app-manifest.json):
   `https://github.com/settings/apps/new?state=garl-prbot&manifest=...`
2. Record these four values from the App settings page:
   - `App ID`
   - `Private key` (download `.pem`, treat as secret)
   - `Webhook secret` (generate a random string, paste into App settings + your backend secret store)
   - `Client ID` (optional, only needed if you want user-OAuth in v2)
3. Set these Railway env vars on the backend service:
   - `GITHUB_APP_ID`
   - `GITHUB_APP_PRIVATE_KEY` (paste the PEM; `\n` literals are auto-normalised)
   - `GITHUB_APP_WEBHOOK_SECRET`
4. Webhook URL (configure on the App): `https://<your-backend>/api/v1/pr-bot/webhook`
5. Webhook events to subscribe: only **Pull request**. HMAC secret = same `GITHUB_APP_WEBHOOK_SECRET`.

## Security posture

- **HMAC gate first.** Every webhook request must present a valid `X-Hub-Signature-256` before any other code runs. No secret → endpoint 503s.
- **Per-repo rate limit.** Fork-author synchronize spam is capped at 30 events / 60 seconds per `(owner, repo)`. Excess events are dropped silently and counted for observability.
- **Metadata-only.** The App reads commit SHA + message + files-changed count via the GitHub API. It never fetches the diff. Commits are attributed based on co-author trailers and commit-message signals — source is never uploaded.
- **Background ACK.** The webhook ACKs within milliseconds; commit fetch + comment upsert runs in a daemon thread. GitHub's 10-second retry SLA is never blown.
- **Sticky via hidden marker.** Re-opens and synchronize events PATCH the existing bot comment rather than post duplicates. Handled by [`STICKY_MARKER`](../../backend/app/services/pr_bot/renderer.py).

## What the bot does *not* do (v1)

- No per-commit breakdown in the comment (v2 roadmap).
- No VS Code hover integration (F3 in the audit roadmap).
- No model-version-diff analytics (F4 in the audit roadmap).
- No policy enforcement — `/api/v1/policy/check` is a separate opt-in endpoint CIs can call directly.

## Related

- App architecture: `backend/app/services/pr_bot/` in the main repo.
- Webhook endpoint: [`backend/app/api/pr_bot_routes.py`](../../backend/app/api/pr_bot_routes.py).
- Summary schema: [`supabase/migrations/20260415_v16_pr_bot_summaries.sql`](../../supabase/migrations/20260415_v16_pr_bot_summaries.sql).
- Canonical receipt-signing Action (separate repo): `Garl-Protocol/garl-receipt-action`.
