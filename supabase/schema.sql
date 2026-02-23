-- GARL Protocol v1.0.1 — Sovereign Trust Layer
-- Consolidated schema of all migrations (reference only)
-- Actual schema management is done via supabase/migrations/

-- Agents table
CREATE TABLE IF NOT EXISTS agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL,
    description VARCHAR(500) DEFAULT '',
    framework VARCHAR(50) DEFAULT 'custom',
    category VARCHAR(50) DEFAULT 'other',
    trust_score NUMERIC(6,2) DEFAULT 50.00,
    total_traces INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    success_rate NUMERIC(6,2) DEFAULT 0.00,
    consecutive_successes INTEGER DEFAULT 0,
    score_reliability NUMERIC(6,2) DEFAULT 50.00,
    score_security NUMERIC(6,2) DEFAULT 50.00,
    score_speed NUMERIC(6,2) DEFAULT 50.00,
    score_cost_efficiency NUMERIC(6,2) DEFAULT 50.00,
    score_consistency NUMERIC(6,2) DEFAULT 50.00,
    ema_reliability NUMERIC(8,4) DEFAULT 50.0,
    ema_security NUMERIC(8,4) DEFAULT 50.0,
    ema_speed NUMERIC(8,4) DEFAULT 50.0,
    ema_cost_efficiency NUMERIC(8,4) DEFAULT 50.0,
    total_cost_usd NUMERIC(12,6) DEFAULT 0,
    avg_duration_ms INTEGER DEFAULT 0,
    anomaly_flags JSONB DEFAULT '[]',
    endorsement_score NUMERIC(8,4) DEFAULT 0.0,
    endorsement_count INTEGER DEFAULT 0,
    sovereign_id TEXT UNIQUE NOT NULL,
    certification_tier VARCHAR(20) DEFAULT 'bronze',
    permissions_declared JSONB DEFAULT '[]',
    security_events JSONB DEFAULT '[]',
    is_deleted BOOLEAN DEFAULT false,
    is_sandbox BOOLEAN NOT NULL DEFAULT false,
    deleted_at TIMESTAMPTZ,
    last_trace_at TIMESTAMPTZ,
    homepage_url TEXT,
    api_key_hash VARCHAR(255) NOT NULL,
    developer_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Traces table (immutable)
CREATE TABLE IF NOT EXISTS traces (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    task_description VARCHAR(1000) NOT NULL,
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failure', 'partial')),
    duration_ms INTEGER NOT NULL DEFAULT 0,
    input_summary VARCHAR(500) DEFAULT '',
    output_summary VARCHAR(500) DEFAULT '',
    category VARCHAR(50) DEFAULT 'other',
    trust_delta NUMERIC(8,4) DEFAULT 0,
    certificate JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    runtime_env VARCHAR(100) DEFAULT '',
    tool_calls JSONB DEFAULT '[]',
    cost_usd NUMERIC(10,6) DEFAULT 0,
    token_count INTEGER,
    trace_hash VARCHAR(64),
    proof_of_result JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reputation history (immutable)
CREATE TABLE IF NOT EXISTS reputation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    trust_score NUMERIC(6,2) NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    trust_delta NUMERIC(8,4) DEFAULT 0,
    score_reliability NUMERIC(6,2),
    score_speed NUMERIC(6,2),
    score_cost_efficiency NUMERIC(6,2),
    score_consistency NUMERIC(6,2),
    score_security NUMERIC(6,2),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Webhooks
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    url VARCHAR(500) NOT NULL,
    secret VARCHAR(100) NOT NULL,
    events JSONB DEFAULT '["score_change","milestone","anomaly","trace_recorded"]',
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ,
    last_triggered_at TIMESTAMPTZ
);

-- Endorsements (immutable — update trigger prevents modification)
CREATE TABLE IF NOT EXISTS endorsements (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endorser_id UUID NOT NULL REFERENCES agents(id),
    target_id UUID NOT NULL REFERENCES agents(id),
    endorser_score NUMERIC(6,2) NOT NULL,
    endorser_traces INTEGER NOT NULL DEFAULT 0,
    bonus_applied NUMERIC(8,4) NOT NULL DEFAULT 0,
    endorser_tier VARCHAR(20) DEFAULT 'bronze',
    tier_multiplier NUMERIC(6,2) DEFAULT 1.0,
    context VARCHAR(500) DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(endorser_id, target_id),
    CHECK(endorser_id != target_id)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_traces_agent_id ON traces(agent_id);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_agents_trust_score ON agents(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_agents_category ON agents(category);
CREATE INDEX IF NOT EXISTS idx_agents_last_trace_at ON agents(last_trace_at DESC);
CREATE INDEX IF NOT EXISTS idx_agents_sovereign_id ON agents(sovereign_id);
CREATE INDEX IF NOT EXISTS idx_agents_certification_tier ON agents(certification_tier);
CREATE INDEX IF NOT EXISTS idx_agents_is_deleted ON agents(is_deleted);
CREATE INDEX IF NOT EXISTS idx_agents_is_sandbox ON agents(is_sandbox) WHERE is_sandbox = true;
CREATE INDEX IF NOT EXISTS idx_agents_score_security ON agents(score_security DESC);
CREATE INDEX IF NOT EXISTS idx_agents_route ON agents(category, certification_tier, trust_score DESC) WHERE is_deleted = false;
CREATE INDEX IF NOT EXISTS idx_reputation_history_agent ON reputation_history(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_endorsements_target ON endorsements(target_id);
CREATE INDEX IF NOT EXISTS idx_endorsements_endorser ON endorsements(endorser_id);
CREATE INDEX IF NOT EXISTS idx_endorsements_created ON endorsements(created_at DESC);

-- Immutability triggers
CREATE OR REPLACE FUNCTION prevent_update() RETURNS TRIGGER AS $$
BEGIN RAISE EXCEPTION 'UPDATE not allowed on immutable table'; END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION prevent_delete() RETURNS TRIGGER AS $$
BEGIN RAISE EXCEPTION 'DELETE not allowed on immutable table'; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_trace_update BEFORE UPDATE ON traces FOR EACH ROW EXECUTE FUNCTION prevent_update();
CREATE TRIGGER prevent_trace_delete BEFORE DELETE ON traces FOR EACH ROW EXECUTE FUNCTION prevent_delete();
CREATE TRIGGER prevent_history_update BEFORE UPDATE ON reputation_history FOR EACH ROW EXECUTE FUNCTION prevent_update();
CREATE TRIGGER prevent_history_delete BEFORE DELETE ON reputation_history FOR EACH ROW EXECUTE FUNCTION prevent_delete();
CREATE TRIGGER prevent_endorsement_update BEFORE UPDATE ON endorsements FOR EACH ROW EXECUTE FUNCTION prevent_update();

-- RLS
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE webhooks ENABLE ROW LEVEL SECURITY;
ALTER TABLE endorsements ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Agents are publicly readable" ON agents FOR SELECT USING (is_deleted = false);
CREATE POLICY "Traces are publicly readable" ON traces FOR SELECT USING (true);
CREATE POLICY "Reputation history is publicly readable" ON reputation_history FOR SELECT USING (true);
CREATE POLICY "Endorsements are publicly readable" ON endorsements FOR SELECT USING (true);
CREATE POLICY "Service role full access on agents" ON agents FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access on traces" ON traces FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access on reputation_history" ON reputation_history FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access on webhooks" ON webhooks FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service role full access on endorsements" ON endorsements FOR ALL USING (true) WITH CHECK (true);
