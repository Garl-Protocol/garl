-- GARL Protocol v0.2 Migration
-- Adds: MCP trace fields, cost tracking, total_cost on agents

-- MCP-compliant optional fields on traces
ALTER TABLE traces ADD COLUMN IF NOT EXISTS runtime_env VARCHAR(100) DEFAULT '';
ALTER TABLE traces ADD COLUMN IF NOT EXISTS tool_calls JSONB DEFAULT '[]';
ALTER TABLE traces ADD COLUMN IF NOT EXISTS cost_usd NUMERIC(10,6) DEFAULT 0;

-- Aggregate cost on agents
ALTER TABLE agents ADD COLUMN IF NOT EXISTS total_cost_usd NUMERIC(12,6) DEFAULT 0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS avg_duration_ms INTEGER DEFAULT 0;
