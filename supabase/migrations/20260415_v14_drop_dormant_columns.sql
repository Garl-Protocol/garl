-- v14 — Drop dormant trace columns.
--
-- Rationale: Across 1,505 production traces spanning March 2026
-- through April 2026, the following columns were 0% or near-zero
-- populated:
--   - tool_calls         (0/1505)
--   - proof_of_result    (0/1505)
--   - runtime_env        (2/1505, noise from smoke tests)
--
-- The backend stops writing them as of commit 3c58631. For any SDK /
-- integration that starts populating one of these fields later, we
-- keep the data in trace.metadata (JSONB) which already exists and is
-- schema-less. If a future feature formalizes one of these, add a
-- dedicated column in a new migration with a deterministic default.
--
-- Irreversible in terms of historic data: the 2 non-empty
-- runtime_env rows will lose that column. They are smoke tests; the
-- trust ledger itself is unaffected because the immutable-update
-- trigger on traces disallows UPDATEs, and column DROPs are not
-- caught by row-level triggers. The proof of record lives in the
-- signed certificate, not these columns.

ALTER TABLE public.traces DROP COLUMN IF EXISTS tool_calls;
ALTER TABLE public.traces DROP COLUMN IF EXISTS proof_of_result;
ALTER TABLE public.traces DROP COLUMN IF EXISTS runtime_env;
