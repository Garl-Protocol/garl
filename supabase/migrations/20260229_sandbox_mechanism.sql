-- GARL Protocol v1.0.1 — Sandbox Mechanism
-- Adds is_sandbox column for test/development agents

ALTER TABLE agents ADD COLUMN IF NOT EXISTS is_sandbox BOOLEAN NOT NULL DEFAULT false;

CREATE INDEX IF NOT EXISTS idx_agents_is_sandbox ON agents(is_sandbox) WHERE is_sandbox = true;
