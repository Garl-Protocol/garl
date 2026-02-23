-- GARL Protocol v0.4.0 Migration — Trust Platform Upgrade
-- Adds: endorsements table, endorsement columns on agents, webhook CRUD support,
-- API key hardening (drop plaintext api_key column)

-- 1. Endorsements table (Sybil-resistant reputation transfer)
CREATE TABLE IF NOT EXISTS endorsements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endorser_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    target_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    endorser_score NUMERIC(6,2) NOT NULL DEFAULT 50.00,
    endorser_traces INTEGER NOT NULL DEFAULT 0,
    bonus_applied NUMERIC(8,4) NOT NULL DEFAULT 0,
    context VARCHAR(500) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_endorsement UNIQUE (endorser_id, target_id),
    CONSTRAINT no_self_endorsement CHECK (endorser_id != target_id)
);

CREATE INDEX IF NOT EXISTS idx_endorsements_target ON endorsements(target_id);
CREATE INDEX IF NOT EXISTS idx_endorsements_endorser ON endorsements(endorser_id);
CREATE INDEX IF NOT EXISTS idx_endorsements_created ON endorsements(created_at DESC);

-- Endorsements are immutable (once given, cannot be modified)
CREATE OR REPLACE FUNCTION prevent_endorsement_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Endorsements are immutable. id=%', OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS endorsements_immutable_update ON endorsements;
CREATE TRIGGER endorsements_immutable_update
    BEFORE UPDATE ON endorsements
    FOR EACH ROW
    EXECUTE FUNCTION prevent_endorsement_update();

-- 2. New columns on agents for endorsement tracking
ALTER TABLE agents ADD COLUMN IF NOT EXISTS endorsement_score NUMERIC(8,4) DEFAULT 0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS endorsement_count INTEGER DEFAULT 0;

-- 3. Webhook management columns
ALTER TABLE webhooks ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ;

-- 4. API Key Hardening — drop plaintext api_key column
-- The api_key_hash column already exists from a previous migration.
-- Only the hash is needed for verification; plaintext should never be stored.
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'agents' AND column_name = 'api_key'
    ) THEN
        -- Remove the unique constraint on api_key first (if it exists)
        ALTER TABLE agents DROP CONSTRAINT IF EXISTS agents_api_key_key;
        -- Drop the plaintext column
        ALTER TABLE agents DROP COLUMN api_key;
        RAISE NOTICE 'Dropped plaintext api_key column from agents table';
    END IF;
END $$;

-- 5. Row Level Security for endorsements
ALTER TABLE endorsements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Endorsements are publicly readable"
    ON endorsements FOR SELECT
    USING (true);

CREATE POLICY "Service role full access on endorsements"
    ON endorsements FOR ALL
    USING (true)
    WITH CHECK (true);

-- 6. Index for leaderboard batch decay optimization
CREATE INDEX IF NOT EXISTS idx_agents_last_trace_at ON agents(last_trace_at);
