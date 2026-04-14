-- v13 — drop the orphaned `api_keys` table.
--
-- The table was created in v0.1 init alongside the agents schema as a
-- placeholder for future "rotate / list / scope" features but never got
-- written to: agents.api_key_hash has been the single source of truth
-- since v0.4. Dropping reclaims the schema slot and removes a dead
-- surface from public docs / OpenAPI tooling.
--
-- If key rotation lands later, it should live alongside agents
-- (per-agent rotation history) rather than as a separate global table.

BEGIN;

DROP TABLE IF EXISTS public.api_keys;

COMMIT;
