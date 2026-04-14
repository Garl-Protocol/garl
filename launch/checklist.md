# Launch checklist

## 48 hours before

- [ ] PyPI package `garl-protocol 1.1.0` uploaded (wheel is already built in
      `sdks/python/dist/`; run `twine upload dist/*` once token is in
      `~/.pypirc` or `TWINE_PASSWORD`).
- [ ] GitHub Marketplace: edit the v1.1.0 release, check
      "Publish this Action to the GitHub Marketplace", pick the category
      ("Continuous integration" + "Security" recommended), confirm icon.
- [ ] Dogfood PR #2 closed + self-test branch cleaned up.
- [ ] `.github/assets/` has a fresh `for-code-hero.png` (for README and
      Dev.to cover) + `for-code-receipt.png` (clean screenshot of
      garl.ai/r/6ff83db8).
- [ ] Double-check garl.ai/for-code renders end-to-end on mobile.
- [ ] Double-check first pass of HN / X / Dev.to copy.

## 24 hours before

- [ ] Publish Dev.to article (secondary search hit).
- [ ] Post quiet teaser from @GARLProtocol on X ("shipping something
      tomorrow for every team that merges AI code").
- [ ] Make sure api.garl.ai is healthy; scale Railway backend up to
      2 replicas if possible.
- [ ] Pre-warm Cloudflare cache for garl.ai, garl.ai/for-code,
      garl.ai/r/6ff83db8 (hit each URL a few times).

## Launch day (T-0)

- [ ] 08:00 ET — post Show HN with link to garl.ai/for-code.
- [ ] 08:05 ET — post X thread (see `x-thread.md`). Pin Tweet 1.
- [ ] 08:10 ET — post to r/programming ([Show & Tell] angle).
- [ ] 08:30 ET — post to r/devops + r/github (separate threads).
- [ ] 09:00 ET — post to Claude + Cursor Discords.
- [ ] 12:00 ET — post to r/opensource + Indie Hackers milestone.
- [ ] Throughout day: reply to every HN / Reddit / X comment within 30 min.

## 24–72 hours after

- [ ] Post retro / numbers update on X (e.g. "X stars, Y new receipt URLs
      generated in the first Z hours").
- [ ] If HN ranks top 10: pitch Changelog News and TLDR AI.
- [ ] If a specific team adopts: ask for a quote + testimonial.

## Kill switches

- If Railway backend starts throttling under HN traffic:
  1. Scale backend replicas immediately.
  2. Check Supabase connection pool usage — bump to 20 if needed.
  3. If still overwhelmed, put the homepage + /for-code behind Vercel
     Edge Cache (we're on Next 14, `next: { revalidate: 60 }` is
     already set on stats).
- If the GitHub Action starts failing for lots of users:
  1. Tail `api.garl.ai` logs for `/verify` error patterns.
  2. Check Cloudflare WAF for user-agent bans (we've already set a
     custom UA; add `dogfood` tests if a new ban appears).
  3. Post a pinned note on the release page.
