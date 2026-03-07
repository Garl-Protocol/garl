-- GARL Protocol v1.0 Migration — Sovereign Trust Layer
-- Identity, Security Dimension, Certification, GDPR, Routing

-- 1. Agent Identity and Security Fields
ALTER TABLE agents ADD COLUMN IF NOT EXISTS sovereign_id TEXT UNIQUE;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS score_security NUMERIC(6,2) DEFAULT 50.00;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS ema_security NUMERIC(8,4) DEFAULT 50.0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS certification_tier VARCHAR(20) DEFAULT 'bronze';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS permissions_declared JSONB DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS security_events JSONB DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT false;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- 2. Assign DID to existing agents (did:garl:<uuid>)
UPDATE agents SET sovereign_id = 'did:garl:' || id::text WHERE sovereign_id IS NULL;
ALTER TABLE agents ALTER COLUMN sovereign_id SET NOT NULL;

-- 3. Add security dimension to reputation_history
ALTER TABLE reputation_history ADD COLUMN IF NOT EXISTS score_security NUMERIC(6,2);

-- 4. Certification tier indexes
CREATE INDEX IF NOT EXISTS idx_agents_sovereign_id ON agents(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_agents_certification_tier ON agents(certification_tier);
CREATE INDEX IF NOT EXISTS idx_agents_is_deleted ON agents(is_deleted);
CREATE INDEX IF NOT EXISTS idx_agents_score_security ON agents(score_security DESC);

-- 5. Composite index for routing (category + tier + score)
CREATE INDEX IF NOT EXISTS idx_agents_route ON agents(category, certification_tier, trust_score DESC)
    WHERE is_deleted = false;

-- 6. Add tier info to endorsements table
ALTER TABLE endorsements ADD COLUMN IF NOT EXISTS endorser_tier VARCHAR(20) DEFAULT 'bronze';
ALTER TABLE endorsements ADD COLUMN IF NOT EXISTS tier_multiplier NUMERIC(6,2) DEFAULT 1.0;

-- 7. RLS update: filter deleted agents
DROP POLICY IF EXISTS "Agents are publicly readable" ON agents;
CREATE POLICY "Agents are publicly readable"
    ON agents FOR SELECT
    USING (is_deleted = false);

-- Service role must access all agents (including deleted)
DROP POLICY IF EXISTS "Service role full access on agents" ON agents;
CREATE POLICY "Service role full access on agents"
    ON agents FOR ALL
    USING (true)
    WITH CHECK (true);
