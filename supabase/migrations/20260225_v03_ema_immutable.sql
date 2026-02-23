-- GARL Protocol v0.3 Migration
-- Adds: trace_hash, token_count, proof_of_result, EMA support, immutable trace constraints

-- 1. New columns on traces
ALTER TABLE traces ADD COLUMN IF NOT EXISTS trace_hash VARCHAR(64);
ALTER TABLE traces ADD COLUMN IF NOT EXISTS token_count INTEGER DEFAULT 0;
ALTER TABLE traces ADD COLUMN IF NOT EXISTS proof_of_result JSONB DEFAULT NULL;

-- 2. New columns on agents for EMA tracking
ALTER TABLE agents ADD COLUMN IF NOT EXISTS ema_reliability NUMERIC(8,4) DEFAULT 50.0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS ema_speed NUMERIC(8,4) DEFAULT 50.0;
ALTER TABLE agents ADD COLUMN IF NOT EXISTS ema_cost_efficiency NUMERIC(8,4) DEFAULT 50.0;

-- 3. Index on trace_hash for quick integrity lookups
CREATE INDEX IF NOT EXISTS idx_traces_trace_hash ON traces(trace_hash);

-- 4. Immutable trace constraints
-- Prevent UPDATE on traces (execution records are permanent)
CREATE OR REPLACE FUNCTION prevent_trace_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Execution traces are immutable and cannot be modified. trace_id=%', OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS traces_immutable_update ON traces;
CREATE TRIGGER traces_immutable_update
    BEFORE UPDATE ON traces
    FOR EACH ROW
    EXECUTE FUNCTION prevent_trace_update();

-- Prevent DELETE on traces (execution records are permanent)
CREATE OR REPLACE FUNCTION prevent_trace_delete()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Execution traces are immutable and cannot be deleted. trace_id=%', OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS traces_immutable_delete ON traces;
CREATE TRIGGER traces_immutable_delete
    BEFORE DELETE ON traces
    FOR EACH ROW
    EXECUTE FUNCTION prevent_trace_delete();

-- 5. Immutable reputation_history (same protection)
CREATE OR REPLACE FUNCTION prevent_history_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Reputation history is immutable and cannot be modified. id=%', OLD.id;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS history_immutable_update ON reputation_history;
CREATE TRIGGER history_immutable_update
    BEFORE UPDATE ON reputation_history
    FOR EACH ROW
    EXECUTE FUNCTION prevent_history_update();

DROP TRIGGER IF EXISTS history_immutable_delete ON reputation_history;
CREATE TRIGGER history_immutable_delete
    BEFORE DELETE ON reputation_history
    FOR EACH ROW
    EXECUTE FUNCTION prevent_trace_delete();

-- 6. Add token_count to cost metrics index
CREATE INDEX IF NOT EXISTS idx_traces_cost_token ON traces(cost_usd, token_count);
