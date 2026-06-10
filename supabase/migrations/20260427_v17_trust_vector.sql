-- v17 — Trust Vector multi-dimensional reputation
-- Additive only: adds trust_vector JSONB + trust_vector_computed_at TIMESTAMPTZ.
-- Existing rows get default '{}'::jsonb. No data is destroyed; legacy 5D
-- scoring stays authoritative for the legacy /api/v1/trust/* endpoints.
--
-- Backfilled into version control on 2026-06-10 from the live migration history
-- (supabase_migrations.schema_migrations); it was originally applied via the
-- Supabase MCP, not committed.

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS trust_vector JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS trust_vector_computed_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_agents_trust_vector_recompute
  ON agents (trust_vector_computed_at NULLS FIRST)
  WHERE is_deleted = false;

COMMENT ON COLUMN agents.trust_vector IS 'Multi-dimensional reputation. JSON shape per protocol/spec/trust-vector-v0.1.md. Computed from traces + endorsements; cached, invalidated on receipt write.';
COMMENT ON COLUMN agents.trust_vector_computed_at IS 'Last successful trust_vector recompute timestamp. NULL = never computed; recompute scheduler picks NULLs first.';
