-- GARL Protocol v0.2 Major Update
-- Multi-dimensional trust, webhooks, anomaly detection, API key hashing

-- Multi-dimensional trust scores on agents
ALTER TABLE agents ADD COLUMN IF NOT EXISTS score_reliability NUMERIC(6,2) DEFAULT 50.00;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS score_speed NUMERIC(6,2) DEFAULT 50.00;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS score_cost_efficiency NUMERIC(6,2) DEFAULT 50.00;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS score_consistency NUMERIC(6,2) DEFAULT 50.00;

-- Anomaly detection fields
ALTER TABLE agents ADD COLUMN IF NOT EXISTS anomaly_flags JSONB DEFAULT '[]';
ALTER TABLE agents ADD COLUMN IF NOT EXISTS last_trace_at TIMESTAMPTZ;

-- API key hash (will migrate from plaintext)
ALTER TABLE agents ADD COLUMN IF NOT EXISTS api_key_hash VARCHAR(255) DEFAULT '';

-- Webhook subscriptions
CREATE TABLE IF NOT EXISTS webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    secret VARCHAR(100) NOT NULL,
    events TEXT[] DEFAULT ARRAY['score_change', 'milestone', 'anomaly'],
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_triggered_at TIMESTAMPTZ
);

-- Store multi-dim scores in reputation history
ALTER TABLE reputation_history ADD COLUMN IF NOT EXISTS score_reliability NUMERIC(6,2);
ALTER TABLE reputation_history ADD COLUMN IF NOT EXISTS score_speed NUMERIC(6,2);
ALTER TABLE reputation_history ADD COLUMN IF NOT EXISTS score_cost_efficiency NUMERIC(6,2);
ALTER TABLE reputation_history ADD COLUMN IF NOT EXISTS score_consistency NUMERIC(6,2);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_webhooks_agent ON webhooks(agent_id);
CREATE INDEX IF NOT EXISTS idx_agents_last_trace ON agents(last_trace_at DESC NULLS LAST);

-- RLS for webhooks
ALTER TABLE webhooks ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Webhooks service role access"
    ON webhooks FOR ALL
    USING (true)
    WITH CHECK (true);
