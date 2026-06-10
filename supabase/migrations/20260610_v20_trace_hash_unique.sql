-- v20: make trace deduplication authoritative at the DB layer.
--
-- The app dedups on trace_hash via a check-then-insert (SELECT ... then INSERT),
-- which is a TOCTOU race: a concurrent double-submit can slip both inserts past
-- the check and create two rows with the same trace_hash. That then breaks
-- prefix verification (/api/v1/verify/{prefix} returns 409 on >1 match) and
-- undercuts the "unique, immutable receipt" guarantee. A UNIQUE constraint
-- makes the dedup authoritative; the service layer translates the resulting
-- 23505 into the same clean "duplicate" response.
--
-- Safe to apply: verified 0 existing duplicate trace_hash values and 0 NULLs
-- on 2026-06-10 before adding the constraint.
ALTER TABLE public.traces
  ADD CONSTRAINT traces_trace_hash_unique UNIQUE (trace_hash);

-- The plain btree index is now redundant: the UNIQUE constraint creates its
-- own backing index that serves the same equality/prefix lookups.
DROP INDEX IF EXISTS public.idx_traces_trace_hash;
