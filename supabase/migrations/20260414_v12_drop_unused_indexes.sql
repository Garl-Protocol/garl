-- v12 — drop indexes flagged "never used" by the Supabase performance
-- advisor (lint 0005_unused_index). Keeps idx_agents_sovereign_id even
-- though currently unused: DID lookup is core to GARL's identity story
-- and a `GET /agents/by-sovereign/{did}` resolver is on the roadmap.
--
-- Each DROP is IF EXISTS so re-running the migration in isolation
-- after a manual revert is safe.

BEGIN;

DROP INDEX IF EXISTS public.idx_traces_cost_token;
DROP INDEX IF EXISTS public.idx_agents_last_trace;
DROP INDEX IF EXISTS public.idx_agents_is_sandbox;
DROP INDEX IF EXISTS public.idx_agents_certification_tier;
DROP INDEX IF EXISTS public.idx_agents_score_security;

-- Intentionally retained:
--   public.idx_agents_sovereign_id  -- DID resolver primitive (planned)
--   public.idx_agents_route        -- composite, hot path for /trust/route
--   public.idx_traces_agent_id     -- FK lookup, hot path

COMMIT;
