-- v22: per-agent HMAC hash keys (EDPB Guidelines 02/2025 ¶52/¶54 alignment)
--
-- Unsalted hashes of personal data are personal data (¶52). GARL's keyed-hash
-- mode HMACs personal-data payloads under a per-agent key held ONLY here,
-- off-chain. Destroying the key (secret_hex -> NULL, destroyed_at stamped) is
-- the sanctioned erasure mechanism: ledger hashes become unlinkable
-- commitments. See backend/app/core/keyed_hash.py and docs/compliance/edpb.md.

CREATE TABLE IF NOT EXISTS agent_hash_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    key_id VARCHAR(16) NOT NULL UNIQUE,
    secret_hex CHAR(64),                 -- NULL once destroyed (erasure)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    rotated_at TIMESTAMPTZ,              -- set when superseded by a newer key
    destroyed_at TIMESTAMPTZ             -- set on GDPR erasure; irreversible
);

COMMENT ON TABLE agent_hash_keys IS
  'Per-agent HMAC-SHA-256 keys for keyed content hashing (EDPB 02/2025 ¶52). '
  'secret_hex is nulled on destruction — that IS the erasure mechanism.';

CREATE INDEX IF NOT EXISTS idx_agent_hash_keys_agent
  ON agent_hash_keys (agent_id) WHERE destroyed_at IS NULL;

-- Key secrets are the unlinkability guarantee: service-role only, no public
-- read policy at all.
ALTER TABLE agent_hash_keys ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS agent_hash_keys_service_role_all ON agent_hash_keys;
CREATE POLICY agent_hash_keys_service_role_all ON agent_hash_keys
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- A destroyed key must never come back: block resurrection of secret_hex.
CREATE OR REPLACE FUNCTION prevent_hash_key_resurrection()
RETURNS TRIGGER AS $$
BEGIN
    IF OLD.destroyed_at IS NOT NULL THEN
        RAISE EXCEPTION 'agent_hash_keys row is destroyed and immutable';
    END IF;
    IF NEW.destroyed_at IS NOT NULL AND NEW.secret_hex IS NOT NULL THEN
        RAISE EXCEPTION 'destroyed hash key cannot retain a secret';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS agent_hash_keys_no_resurrection ON agent_hash_keys;
CREATE TRIGGER agent_hash_keys_no_resurrection
    BEFORE UPDATE ON agent_hash_keys
    FOR EACH ROW EXECUTE FUNCTION prevent_hash_key_resurrection();
