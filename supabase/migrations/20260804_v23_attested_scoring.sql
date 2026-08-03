-- v23: attested-evidence scoring counters (Trust Vector honesty)
--
-- Bare self-reported traces must never lift an agent above the neutral
-- baseline (50). The backend caps above-baseline headroom by the share of
-- ATTESTED evidence: traces whose external attestation (e.g. GitHub CI
-- check-run) was re-verified and stamped `witnessed`, plus qualified
-- endorsements (bonus_applied > 0). These two counters back that cap.
-- See backend/app/services/reputation.py (apply_attestation_cap) and
-- protocol/spec/trust-vector-v0.1.md ("Self-reported vs attested evidence").
--
-- The application code defaults both counters to 0 when the columns are
-- missing, so deploying the code before this migration is safe (the cap is
-- simply fully engaged and the counters are not persisted).

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS attested_trace_count INTEGER NOT NULL DEFAULT 0;

ALTER TABLE agents
  ADD COLUMN IF NOT EXISTS qualified_endorsement_count INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN agents.attested_trace_count IS
  'Traces whose external attestation was re-verified server-side (witnessed=true). '
  'Feeds the attested-evidence headroom cap; self-reported traces do not count.';

COMMENT ON COLUMN agents.qualified_endorsement_count IS
  'Endorsements received that carried weight (bonus_applied > 0). Raw '
  'endorsement_count stays the unfiltered total; only this one feeds identity '
  'assurance and the attested-evidence headroom cap.';

-- Backfill qualified endorsements from the endorsements ledger.
UPDATE agents a
SET qualified_endorsement_count = sub.n
FROM (
    SELECT target_id, COUNT(*) AS n
    FROM endorsements
    WHERE bonus_applied > 0
    GROUP BY target_id
) sub
WHERE a.id = sub.target_id;

-- Backfill witnessed traces from the signed certificates. Attestations live
-- in the SIGNED payload (certificate->'payload'->'attestations'); a trace
-- counts only when at least one attestation carries witnessed=true.
UPDATE agents a
SET attested_trace_count = sub.n
FROM (
    SELECT t.agent_id, COUNT(*) AS n
    FROM traces t
    WHERE jsonb_typeof(t.certificate->'payload'->'attestations') = 'array'
      AND EXISTS (
          SELECT 1
          FROM jsonb_array_elements(t.certificate->'payload'->'attestations') att
          WHERE att->>'witnessed' = 'true'
      )
    GROUP BY t.agent_id
) sub
WHERE a.id = sub.agent_id;
