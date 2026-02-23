-- GARL Protocol Database Schema
-- Run this in Supabase SQL Editor

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
    homepage_url TEXT,
    api_key VARCHAR(100) NOT NULL UNIQUE,
    developer_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Execution traces
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
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Reputation history for trend charts
CREATE TABLE IF NOT EXISTS reputation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_id UUID NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
    trust_score NUMERIC(6,2) NOT NULL,
    event_type VARCHAR(20) NOT NULL,
    trust_delta NUMERIC(8,4) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API keys table for developer access
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    developer_id UUID,
    key_hash VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(100) DEFAULT 'Default',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_traces_agent_id ON traces(agent_id);
CREATE INDEX IF NOT EXISTS idx_traces_created_at ON traces(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_traces_status ON traces(status);
CREATE INDEX IF NOT EXISTS idx_agents_trust_score ON agents(trust_score DESC);
CREATE INDEX IF NOT EXISTS idx_agents_category ON agents(category);
CREATE INDEX IF NOT EXISTS idx_reputation_history_agent ON reputation_history(agent_id, created_at DESC);

-- Row Level Security
ALTER TABLE agents ENABLE ROW LEVEL SECURITY;
ALTER TABLE traces ENABLE ROW LEVEL SECURITY;
ALTER TABLE reputation_history ENABLE ROW LEVEL SECURITY;

-- Public read policies (anyone can view agent scores and traces)
CREATE POLICY "Agents are publicly readable"
    ON agents FOR SELECT
    USING (true);

CREATE POLICY "Traces are publicly readable"
    ON traces FOR SELECT
    USING (true);

CREATE POLICY "Reputation history is publicly readable"
    ON reputation_history FOR SELECT
    USING (true);

-- Service role can do everything (backend uses service role key)
CREATE POLICY "Service role full access on agents"
    ON agents FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access on traces"
    ON traces FOR ALL
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role full access on reputation_history"
    ON reputation_history FOR ALL
    USING (true)
    WITH CHECK (true);
