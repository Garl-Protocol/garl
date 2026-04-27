-- v17 — Trust Vector multi-dimensional reputation
--
-- Adds JSONB `trust_vector` column to agents. Multi-dimensional replacement
-- for the single composite trust_score. Score-by-domain instead of one
-- global number — agents who are great at code may be untested at payments;
-- one number conflates those signals.
--
-- Vector schema (initial set; additive over time):
--   agent_identity_assurance    — DID stability + endorsement count + age weighting
--   code_task_reliability       — reliability EMA filtered to category=coding traces
--   security_review_pass_rate   — security dim EMA (existing scoring carries forward)
--   reversible_action_success   — success rate on side_effect=reversible receipts
--   payment_dispute_rate        — placeholder, populated as payment receipts land
--   human_override_rate         — % of receipts that triggered policy=requires_human
--   recency_weighted_consistency — variance with recency decay
--   verified_receipt_count      — total signed receipts (authoritative count)
--   third_party_attestation_count — endorsements + external attestations
--
-- Backward compatibility: existing trust_score / score_* columns stay; vector
-- is computed on read or via background recompute. Both surfaces remain valid
-- until v25+ when the legacy scalars become a view.

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS trust_vector JSONB NOT NULL DEFAULT '{}'::jsonb,
  ADD COLUMN IF NOT EXISTS trust_vector_computed_at TIMESTAMPTZ;

-- Partial index for the recompute scheduler: only non-deleted agents.
CREATE INDEX IF NOT EXISTS idx_agents_trust_vector_recompute
  ON agents (trust_vector_computed_at NULLS FIRST)
  WHERE is_deleted = false;

COMMENT ON COLUMN agents.trust_vector IS 'Multi-dimensional reputation. JSON shape per protocol/spec/trust-vector-v0.1.md. Computed from traces + endorsements; cached, invalidated on receipt write.';
COMMENT ON COLUMN agents.trust_vector_computed_at IS 'Last successful trust_vector recompute timestamp. NULL = never computed; recompute scheduler picks NULLs first.';
