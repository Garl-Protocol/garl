-- v19 — Supabase advisor fixes: pin search_path on the receipt immutability
-- trigger functions (prevents search_path-injection / function-hijack), and add
-- two missing indexes. Backfilled into version control on 2026-06-10 from the
-- live migration history; originally applied via the Supabase MCP.

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

CREATE INDEX IF NOT EXISTS idx_compensations_agent_id ON compensations(agent_id);
CREATE INDEX IF NOT EXISTS idx_receipts_merkle_batch_id ON receipts(merkle_batch_id) WHERE merkle_batch_id IS NOT NULL;
