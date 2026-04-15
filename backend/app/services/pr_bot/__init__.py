"""GARL PR Bot — GitHub App that posts a sticky 'AI-authored %' comment on
every pull request plus a 'Verify all' link back to the canonical registry.

This package is the *logic* layer (attribution, HMAC validation, rate
limiting). The GitHub App manifest, Marketplace listing, and install URL
live under `integrations/pr-bot/`. The webhook HTTP endpoint lives in
`backend/app/api/routes.py` (added in a follow-up commit) and delegates
to the functions exported here.

Layered to keep one source of truth per concern — the Sentinel brief
flags that duplicating HMAC validators or trace signers between the
monorepo and a separate App repo would break the GARL trust chain.
"""
from app.services.pr_bot.commit_attribution import (
    AttributionResult,
    detect_ai_commits,
)
from app.services.pr_bot.hmac_verify import verify_github_signature
from app.services.pr_bot.rate_limiter import PerRepoRateLimiter

__all__ = [
    "AttributionResult",
    "detect_ai_commits",
    "verify_github_signature",
    "PerRepoRateLimiter",
]
