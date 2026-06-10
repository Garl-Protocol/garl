-- v18 — Wave 2 foundation: Action Receipts, Capability Tokens, Compensations,
-- Merkle batches. Backfilled into version control on 2026-06-10 from the live
-- migration history; it was originally applied via the Supabase MCP.
--
-- The immutability triggers below are security-critical (they enforce the
-- "immutable ledger" claim) and were previously only in the live DB. v19
-- pins their search_path; this file is the original v18 form.

CREATE TABLE IF NOT EXISTS receipts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID UNIQUE NOT NULL,
  agent_id UUID NOT NULL REFERENCES agents(id),
  human_delegate TEXT,
  runtime VARCHAR(40) NOT NULL,
  protocol VARCHAR(20) NOT NULL,
  action_type VARCHAR(40) NOT NULL,
  tool_server TEXT,
  capability_token_hash CHAR(64),
  policy_decision VARCHAR(20),
  input_hash CHAR(64) NOT NULL,
  output_hash CHAR(64) NOT NULL,
  side_effect VARCHAR(20) NOT NULL CHECK (side_effect IN ('none','reversible','irreversible')),
  cost JSONB,
  attestations TEXT[],
  redaction_policy JSONB,
  previous_receipt_hash CHAR(64),
  signature TEXT NOT NULL,
  verification_key_id VARCHAR(16) NOT NULL,
  envelope_json JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  anchored_at TIMESTAMPTZ,
  merkle_batch_id INTEGER
);

CREATE INDEX IF NOT EXISTS idx_receipts_agent_id ON receipts(agent_id);
CREATE INDEX IF NOT EXISTS idx_receipts_action_type ON receipts(action_type);
CREATE INDEX IF NOT EXISTS idx_receipts_side_effect ON receipts(side_effect);
CREATE INDEX IF NOT EXISTS idx_receipts_pending_anchor ON receipts(created_at) WHERE anchored_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_receipts_output_hash ON receipts(output_hash);

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
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS receipts_immutable_update ON receipts;
CREATE TRIGGER receipts_immutable_update BEFORE UPDATE ON receipts FOR EACH ROW EXECUTE FUNCTION prevent_receipt_update();

CREATE OR REPLACE FUNCTION prevent_receipt_delete() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Receipts cannot be deleted. Use redaction_policy to mask fields instead.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS receipts_immutable_delete ON receipts;
CREATE TRIGGER receipts_immutable_delete BEFORE DELETE ON receipts FOR EACH ROW EXECUTE FUNCTION prevent_receipt_delete();

ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS receipts_public_read ON receipts;
CREATE POLICY receipts_public_read ON receipts FOR SELECT TO public USING (redaction_policy IS NULL OR (redaction_policy->>'mode' IS DISTINCT FROM 'private'));

DROP POLICY IF EXISTS receipts_service_role_all ON receipts;
CREATE POLICY receipts_service_role_all ON receipts FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMENT ON TABLE receipts IS 'Action Receipt v0.1 envelope storage. Immutable. Spec: protocol/spec/action-receipt-v0.1.md.';
COMMENT ON COLUMN receipts.envelope_json IS 'Canonical receipt JSON for verifiers. Identical to the body of the public receipt URL.';

CREATE TABLE IF NOT EXISTS capability_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  token_hash CHAR(64) UNIQUE NOT NULL,
  agent_id UUID NOT NULL REFERENCES agents(id),
  human_delegate TEXT,
  jwt_form TEXT NOT NULL,
  caveats JSONB NOT NULL DEFAULT '[]'::jsonb,
  scope TEXT NOT NULL,
  spend_limit_usd NUMERIC(12,6),
  side_effect_class VARCHAR(20) NOT NULL CHECK (side_effect_class IN ('none','reversible','irreversible')),
  merchant_allowlist TEXT[],
  parent_token_hash CHAR(64),
  issued_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ NOT NULL,
  revoked_at TIMESTAMPTZ,
  revocation_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_capability_tokens_agent_id ON capability_tokens(agent_id);
CREATE INDEX IF NOT EXISTS idx_capability_tokens_active ON capability_tokens(agent_id, expires_at) WHERE revoked_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_capability_tokens_parent ON capability_tokens(parent_token_hash) WHERE parent_token_hash IS NOT NULL;

ALTER TABLE capability_tokens ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS capability_tokens_service_role_all ON capability_tokens;
CREATE POLICY capability_tokens_service_role_all ON capability_tokens FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMENT ON TABLE capability_tokens IS 'Issued capability tokens. JWT-shaped envelope signed with ECDSA-secp256k1 RFC 6979 deterministic. Attenuation: parent_token_hash chains.';

CREATE TABLE IF NOT EXISTS compensations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  receipt_id UUID NOT NULL,
  agent_id UUID NOT NULL REFERENCES agents(id),
  undo_payload JSONB NOT NULL,
  reason TEXT NOT NULL,
  triggered_at TIMESTAMPTZ DEFAULT NOW(),
  status VARCHAR(20) DEFAULT 'pending' CHECK (status IN ('recorded','pending','succeeded','failed')),
  result_receipt_id UUID,
  CONSTRAINT compensations_receipt_fk FOREIGN KEY (receipt_id) REFERENCES receipts(receipt_id)
);

CREATE INDEX IF NOT EXISTS idx_compensations_receipt_id ON compensations(receipt_id);
CREATE INDEX IF NOT EXISTS idx_compensations_status ON compensations(status, triggered_at);

ALTER TABLE compensations ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS compensations_service_role_all ON compensations;
CREATE POLICY compensations_service_role_all ON compensations FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMENT ON TABLE compensations IS 'Reversibility primitives. status flow: recorded -> pending -> succeeded|failed.';

CREATE TABLE IF NOT EXISTS merkle_batches (
  batch_id SERIAL PRIMARY KEY,
  root CHAR(64) NOT NULL,
  receipt_count INTEGER NOT NULL CHECK (receipt_count > 0),
  built_at TIMESTAMPTZ DEFAULT NOW(),
  anchored_at TIMESTAMPTZ,
  chain_id INTEGER,
  tx_hash VARCHAR(66),
  contract_address VARCHAR(42)
);

CREATE INDEX IF NOT EXISTS idx_merkle_batches_pending ON merkle_batches(built_at) WHERE anchored_at IS NULL;

ALTER TABLE merkle_batches ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS merkle_batches_public_read ON merkle_batches;
CREATE POLICY merkle_batches_public_read ON merkle_batches FOR SELECT TO public USING (true);

DROP POLICY IF EXISTS merkle_batches_service_role_all ON merkle_batches;
CREATE POLICY merkle_batches_service_role_all ON merkle_batches FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMENT ON TABLE merkle_batches IS 'Periodic Merkle root commitments. anchored_at NULL = built but not yet on-chain.';

ALTER TABLE receipts DROP CONSTRAINT IF EXISTS receipts_merkle_batch_fk;
ALTER TABLE receipts ADD CONSTRAINT receipts_merkle_batch_fk FOREIGN KEY (merkle_batch_id) REFERENCES merkle_batches(batch_id);
