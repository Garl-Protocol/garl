-- v15 — Drop dormant JSONB columns on agents.
--
-- Rationale (audit_2026-04-15.md / B13):
--   security_events      → 0 / 131 agents populated
--   permissions_declared → 0 / 131 agents populated
--
-- These were planned as scoring inputs that the SDK / MCP / Action
-- would populate later. Across the last 30 days of production the
-- fields stayed empty, so we stop maintaining columns that don't
-- earn their keep. Symmetric with v14 which dropped the three dormant
-- trace columns.
--
-- Backend change lands alongside this migration: agents.py stops
-- writing these fields on registration; the AgentRegisterRequest
-- schema still accepts permissions_declared for backward-compat but
-- the value is discarded (will be re-homed under a JSONB 'extra'
-- column if a future feature needs it).

ALTER TABLE public.agents DROP COLUMN IF EXISTS security_events;
ALTER TABLE public.agents DROP COLUMN IF EXISTS permissions_declared;
