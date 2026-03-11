-- GARL Protocol v1.1 Migration — Security Hardening
-- Fixes all Supabase security linter warnings:
--   1. Enable RLS on api_keys table (ERROR)
--   2. Set search_path on immutability trigger functions (WARN x4)
--   3. Restrict "full access" RLS policies to service_role only (WARN x5)

-- ============================================================
-- 1. api_keys: Enable RLS + restrictive policies
-- ============================================================

ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on api_keys"
    ON api_keys FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================================
-- 2. Fix mutable search_path on immutability trigger functions
-- ============================================================

CREATE OR REPLACE FUNCTION prevent_trace_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Execution traces are immutable and cannot be modified. trace_id=%', OLD.id;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION prevent_trace_delete()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Execution traces are immutable and cannot be deleted. trace_id=%', OLD.id;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION prevent_history_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Reputation history is immutable and cannot be modified. id=%', OLD.id;
    RETURN NULL;
END;
$$;

CREATE OR REPLACE FUNCTION prevent_endorsement_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'GARL Protocol: Endorsements are immutable. id=%', OLD.id;
    RETURN NULL;
END;
$$;

-- ============================================================
-- 3. Restrict "full access" policies to service_role only
--    Drop the old permissive policies and recreate with TO service_role
-- ============================================================

-- agents
DROP POLICY IF EXISTS "Service role full access on agents" ON agents;
CREATE POLICY "Service role full access on agents"
    ON agents FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- traces
DROP POLICY IF EXISTS "Service role full access on traces" ON traces;
CREATE POLICY "Service role full access on traces"
    ON traces FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- reputation_history
DROP POLICY IF EXISTS "Service role full access on reputation_history" ON reputation_history;
CREATE POLICY "Service role full access on reputation_history"
    ON reputation_history FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- endorsements
DROP POLICY IF EXISTS "Service role full access on endorsements" ON endorsements;
CREATE POLICY "Service role full access on endorsements"
    ON endorsements FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- webhooks
DROP POLICY IF EXISTS "Webhooks service role access" ON webhooks;
CREATE POLICY "Webhooks service role access"
    ON webhooks FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);
