-- v19 — Supabase advisor remediation
--
-- Two security warnings (function_search_path_mutable) and two
-- performance INFOs (unindexed_foreign_keys) flagged after v18 landed.
-- This migration:
--   1. Pins the search_path on prevent_receipt_update / prevent_receipt_delete
--      to "" (empty) — the recommended remediation per Supabase docs:
--      https://supabase.com/docs/guides/database/database-linter?lint=0011
--      Functions with mutable search_path can be hijacked by an attacker
--      who creates a same-named function in a search-path-earlier schema.
--   2. Adds covering indexes for the two foreign keys flagged:
--      compensations(agent_id), receipts(merkle_batch_id).
--
-- The triggers themselves still reference unqualified plpgsql functions,
-- which is fine when search_path is "" because RAISE EXCEPTION is a
-- built-in (no search-path lookup).

CREATE OR REPLACE FUNCTION prevent_receipt_update() RETURNS TRIGGER AS $$
BEGIN
  IF NEW.id IS DISTINCT FROM OLD.id
     OR NEW.receipt_id IS DISTINCT FROM OLD.receipt_id
     OR NEW.agent_id IS DISTINCT FROM OLD.agent_id
     OR NEW.signature IS DISTINCT FROM OLD.signature
     OR NEW.input_hash IS DISTINCT FROM OLD.input_hash
     OR NEW.output_hash IS DISTINCT FROM OLD.output_hash
     OR NEW.side_effect IS DISTINCT FROM OLD.side_effect
     OR NEW.envelope_json::text IS DISTINCT FROM OLD.envelope_json::text THEN
    RAISE EXCEPTION 'Receipts are immutable; cannot modify identity/signature/envelope fields.';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SET search_path = '';

CREATE OR REPLACE FUNCTION prevent_receipt_delete() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Receipts cannot be deleted. Use redaction_policy to mask fields instead.';
END;
$$ LANGUAGE plpgsql SET search_path = '';

-- Covering indexes for the two unindexed FKs flagged.
CREATE INDEX IF NOT EXISTS idx_compensations_agent_id
  ON compensations(agent_id);

CREATE INDEX IF NOT EXISTS idx_receipts_merkle_batch_id
  ON receipts(merkle_batch_id) WHERE merkle_batch_id IS NOT NULL;
