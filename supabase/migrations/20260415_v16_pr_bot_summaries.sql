-- v16 — pr_bot_summaries table for the GARL PR Bot (F2).
--
-- Stores the last computed AI-authorship summary for each (owner, repo,
-- pr_number). The GARL PR Bot webhook handler upserts a row on every
-- relevant pull_request event; the public GET /api/v1/pr-bot/summary
-- endpoint reads from here so the /pr landing page and the sticky
-- comment's "Verify all" link don't round-trip back to GitHub.
--
-- No immutability trigger — pr_bot_summaries is cache-like, expected to
-- be re-computed on synchronize events, and not part of the
-- cryptographic ledger.

CREATE TABLE IF NOT EXISTS public.pr_bot_summaries (
    owner            text        NOT NULL,
    repo             text        NOT NULL,
    pr_number        integer     NOT NULL,
    ai_percentage    numeric     NOT NULL DEFAULT 0,
    ai_commits       integer     NOT NULL DEFAULT 0,
    total_commits    integer     NOT NULL DEFAULT 0,
    model_counts     jsonb       NOT NULL DEFAULT '{}'::jsonb,
    updated_at       timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (owner, repo, pr_number)
);

ALTER TABLE public.pr_bot_summaries ENABLE ROW LEVEL SECURITY;

-- Public read: anyone can look up a PR summary by its canonical path.
CREATE POLICY pr_bot_summaries_public_read
    ON public.pr_bot_summaries
    FOR SELECT
    USING (true);

-- Writes only via service_role (backend handler). No end-user writes.
CREATE POLICY pr_bot_summaries_service_write
    ON public.pr_bot_summaries
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE INDEX IF NOT EXISTS idx_pr_bot_summaries_updated_at
    ON public.pr_bot_summaries (updated_at DESC);
