-- v21 — Session-level behavioral layer v0: signed session alerts.
--
-- Motivating case: Grok/Bankr, May 2026 — ~$150-175K lost through a chain of
-- individually-legitimate transactions (privilege escalation + encoded
-- instructions). Every per-action check passed; the tell was the SESSION-level
-- pattern (spend velocity, delegation depth, novel irreversible targets).
-- This table stores the signed alert envelopes produced by
-- backend/app/services/session_anomaly.py.
--
-- Scope-escalation attempts (a child capability token trying to WIDEN its
-- parent at issue time) are recorded here too, as rows with
-- rule = 'scope_escalation_attempt' — deliberately no separate table.
--
-- Alerts are evidence, so they follow the receipts immutability model:
-- public read, service-role write, no UPDATE, no DELETE.

CREATE TABLE IF NOT EXISTS session_alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  agent_id UUID NOT NULL REFERENCES agents(id),
  rule VARCHAR(40) NOT NULL,
  severity VARCHAR(10) NOT NULL CHECK (severity IN ('info','warning','critical')),
  summary TEXT NOT NULL,
  evidence JSONB NOT NULL,
  signature TEXT NOT NULL,
  verification_key_id VARCHAR(16) NOT NULL,
  envelope_json JSONB NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_alerts_agent_created ON session_alerts(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_alerts_rule ON session_alerts(rule);

-- Immutability: alerts are append-only evidence, like receipts.
-- search_path pinned per the v19 advisor fix (prevents function hijack).
CREATE OR REPLACE FUNCTION prevent_session_alert_update() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Session alerts are immutable; updates are not allowed.';
END;
$$ LANGUAGE plpgsql SET search_path = '';

DROP TRIGGER IF EXISTS session_alerts_immutable_update ON session_alerts;
CREATE TRIGGER session_alerts_immutable_update BEFORE UPDATE ON session_alerts FOR EACH ROW EXECUTE FUNCTION prevent_session_alert_update();

CREATE OR REPLACE FUNCTION prevent_session_alert_delete() RETURNS TRIGGER AS $$
BEGIN
  RAISE EXCEPTION 'Session alerts cannot be deleted.';
END;
$$ LANGUAGE plpgsql SET search_path = '';

DROP TRIGGER IF EXISTS session_alerts_immutable_delete ON session_alerts;
CREATE TRIGGER session_alerts_immutable_delete BEFORE DELETE ON session_alerts FOR EACH ROW EXECUTE FUNCTION prevent_session_alert_delete();

ALTER TABLE session_alerts ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS session_alerts_public_read ON session_alerts;
CREATE POLICY session_alerts_public_read ON session_alerts FOR SELECT TO public USING (true);

DROP POLICY IF EXISTS session_alerts_service_role_all ON session_alerts;
CREATE POLICY session_alerts_service_role_all ON session_alerts FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMENT ON TABLE session_alerts IS 'Signed session-level behavioral alerts (garl/session-alert/v0.1). Append-only. Producer: backend/app/services/session_anomaly.py; docs/session-alerts.md.';
COMMENT ON COLUMN session_alerts.envelope_json IS 'Canonical signed alert envelope. signature = ECDSA-secp256k1 over the envelope without signature/verification_key_id (same pipeline as receipts).';
