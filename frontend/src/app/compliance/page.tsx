"use client";

import { useState, useEffect, useCallback, Suspense } from "react";
import { useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import {
  Shield,
  Check,
  X,
  AlertTriangle,
  FileCheck,
  Award,
  AlertCircle,
  Info,
  Lock,
  Download,
} from "lucide-react";
import { fetchCompliance, type ComplianceReport } from "@/lib/api";

const TIER_COLORS: Record<string, string> = {
  bronze: "#92400e",
  silver: "#94a3b8",
  gold: "#f59e0b",
  enterprise: "#a855f7",
};

function truncateLabel(label: string, maxLen = 16): string {
  if (label.length <= maxLen) return label;
  return label.slice(0, maxLen - 3) + "...";
}

function getBarColor(score: number): string {
  if (score >= 70) return "bg-garl-accent";
  if (score >= 40) return "bg-garl-warning";
  return "bg-garl-danger";
}

interface LeaderboardAgent {
  id: string;
  name: string;
  trust_score: number;
  certification_tier: string;
  framework: string;
}

function ComplianceContent() {
  const searchParams = useSearchParams();
  const agentId = searchParams.get("agent_id") || "";
  const [data, setData] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [authRequired, setAuthRequired] = useState(false);
  const [apiKey, setApiKey] = useState("");
  const [authError, setAuthError] = useState("");
  const [agents, setAgents] = useState<LeaderboardAgent[]>([]);
  const [agentSearch, setAgentSearch] = useState("");

  const apiBase =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

  useEffect(() => {
    if (!agentId) {
      fetch(`${apiBase}/search?limit=50`)
        .then((r) => r.json())
        .then((raw) => setAgents(Array.isArray(raw) ? raw : raw.data || []))
        .catch(() => {});
    }
  }, [agentId, apiBase]);

  const loadData = useCallback(async (key?: string) => {
    if (!agentId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const storedKey = key || (typeof window !== "undefined" ? localStorage.getItem("garl_api_key") || "" : "");
      const report = await fetchCompliance(agentId, storedKey || undefined);
      setData(report);
      setAuthRequired(false);
      if (storedKey && typeof window !== "undefined") localStorage.setItem("garl_api_key", storedKey);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to load data";
      if (msg.includes("401")) {
        setAuthRequired(true);
      } else {
        setError(msg);
      }
    } finally {
      setLoading(false);
    }
  }, [agentId]);

  const handleApiKeySubmit = () => {
    if (!apiKey.trim()) { setAuthError("API key is required"); return; }
    setAuthError("");
    loadData(apiKey.trim());
  };

  useEffect(() => {
    loadData();
  }, [loadData]);

  if (loading) {
    return (
      <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4">
        <div className="h-10 w-10 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
        <span className="font-mono text-sm text-garl-muted">Loading...</span>
      </div>
    );
  }

  if (authRequired) {
    return (
      <div className="mx-auto max-w-md px-4 py-20">
        <motion.div
          initial={false}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-garl-blue/30 bg-garl-surface p-8 text-center"
        >
          <Lock className="mx-auto mb-4 h-10 w-10 text-garl-blue" />
          <h2 className="mb-2 font-mono text-lg font-semibold text-garl-text">
            Protected Compliance Data
          </h2>
          <p className="mb-6 font-mono text-xs text-garl-muted">
            Compliance reports require authentication. Enter the API key you received when registering your agent.
          </p>
          <div className="space-y-3">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleApiKeySubmit()}
              placeholder="Enter your API key"
              className="w-full rounded-lg border border-garl-border bg-garl-bg px-4 py-2.5 font-mono text-sm text-garl-text placeholder-garl-muted focus:border-garl-blue/50 focus:outline-none"
            />
            {authError && (
              <p className="font-mono text-xs text-garl-danger">{authError}</p>
            )}
            <button
              onClick={handleApiKeySubmit}
              className="w-full rounded-lg bg-garl-blue/20 px-4 py-2.5 font-mono text-sm font-semibold text-garl-blue transition-all hover:bg-garl-blue/30"
            >
              Unlock Compliance Report
            </button>
          </div>
          <a
            href="/leaderboard"
            className="mt-4 inline-block font-mono text-xs text-garl-muted hover:text-garl-accent"
          >
            ← Back to Leaderboard
          </a>
        </motion.div>
      </div>
    );
  }

  if (!agentId) {
    const filtered = agents.filter(
      (a) =>
        a.name.toLowerCase().includes(agentSearch.toLowerCase()) ||
        a.framework.toLowerCase().includes(agentSearch.toLowerCase())
    );
    return (
      <div className="mx-auto max-w-3xl px-4 py-12">
        <motion.div initial={false} animate={{ opacity: 1, y: 0 }}>
          <div className="mb-8 text-center">
            <Shield className="mx-auto mb-4 h-10 w-10 text-garl-accent" />
            <h1 className="mb-2 font-mono text-2xl font-bold text-garl-text">
              Compliance Evidence Export
            </h1>
            <p className="font-mono text-sm text-garl-muted">
              Export audit-ready evidence of an agent&apos;s AI-authored work —
              signed, tamper-evident receipts mapped to CA SB 942, the EU AI Act
              Code of Practice, and ISO 42001. Formats: CSV, JSON-LD, in-toto,
              SLSA, C2PA.
            </p>
          </div>
          <input
            type="text"
            value={agentSearch}
            onChange={(e) => setAgentSearch(e.target.value)}
            placeholder="Search agents..."
            className="mb-4 w-full rounded-lg border border-garl-border bg-garl-surface px-4 py-2.5 font-mono text-sm text-garl-text placeholder-garl-muted focus:border-garl-accent/50 focus:outline-none"
          />
          <div className="space-y-2">
            {filtered.length === 0 && (
              <p className="py-8 text-center font-mono text-xs text-garl-muted">
                {agents.length === 0 ? "Loading agents..." : "No agents found"}
              </p>
            )}
            {filtered.map((a) => (
              <a
                key={a.id}
                href={`/compliance?agent_id=${a.id}`}
                className="flex items-center justify-between rounded-lg border border-garl-border bg-garl-surface p-4 transition-all hover:border-garl-accent/30"
              >
                <div className="flex items-center gap-3">
                  <FileCheck className="h-4 w-4 text-garl-accent" />
                  <div>
                    <span className="font-mono text-sm font-semibold text-garl-text">
                      {a.name}
                    </span>
                    <span className="ml-2 font-mono text-xs text-garl-muted">
                      {a.framework}
                    </span>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <span
                    className="rounded px-2 py-0.5 font-mono text-[10px] font-semibold uppercase"
                    style={{
                      backgroundColor: `${TIER_COLORS[a.certification_tier] || TIER_COLORS.bronze}20`,
                      color: TIER_COLORS[a.certification_tier] || TIER_COLORS.bronze,
                    }}
                  >
                    {a.certification_tier}
                  </span>
                  <span
                    className={`font-mono text-sm font-bold ${
                      a.trust_score >= 70 ? "text-garl-accent" : a.trust_score >= 40 ? "text-garl-warning" : "text-garl-danger"
                    }`}
                  >
                    {a.trust_score.toFixed(1)}
                  </span>
                </div>
              </a>
            ))}
          </div>
        </motion.div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="mx-auto max-w-7xl px-4 py-20">
        <motion.div
          initial={false}
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl border border-garl-danger/40 bg-garl-danger/5 p-6 text-center"
        >
          <AlertCircle className="mx-auto mb-3 h-12 w-12 text-garl-danger" />
          <h2 className="mb-2 font-mono text-lg font-semibold text-garl-text">
            Compliance Report Unavailable
          </h2>
          <p className="mb-4 font-mono text-sm text-garl-muted">
            {error || "Agent not found or data could not be retrieved."}
          </p>
          <a
            href="/leaderboard"
            className="inline-flex items-center gap-2 rounded-lg border border-garl-border px-4 py-2 font-mono text-xs transition-colors hover:border-garl-accent/40"
          >
            Back to Leaderboard
          </a>
        </motion.div>
      </div>
    );
  }

  const tier = data.certification_tier || "bronze";
  const tierColor = TIER_COLORS[tier] || TIER_COLORS.bronze;
  const sla = data.sla_compliance;
  const dims = data.dimensions;
  const anomalyHistory = data.anomaly_history || { active: [], archived: [], total_flags: 0 };
  const endorsement = data.endorsement_summary || {
    received: [],
    given: [],
    total_endorsement_bonus: 0,
  };
  const recentEndorsements = (endorsement.received || []).slice(0, 5);

  const dimLabels: Record<string, string> = {
    reliability: "Reliability",
    security: "Security",
    speed: "Speed",
    cost_efficiency: "Cost Efficiency",
    consistency: "Consistency",
  };

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      {/* Header */}
      <motion.div
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        className="mb-8 rounded-xl border border-garl-border bg-garl-surface p-6"
      >
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex flex-wrap items-center gap-3">
              <Shield className="h-6 w-6 text-garl-accent" />
              <h1 className="font-mono text-2xl font-bold text-garl-text">
                {truncateLabel(data.name, 32)}
              </h1>
              <span
                className="rounded px-2 py-0.5 font-mono text-xs font-semibold uppercase"
                style={{
                  backgroundColor: `${tierColor}20`,
                  color: tierColor,
                  borderColor: tierColor,
                  borderWidth: 1,
                }}
              >
                {tier}
              </span>
            </div>
            {data.sovereign_id && (
              <p className="mb-2 font-mono text-xs text-garl-muted">
                DID: {truncateLabel(data.sovereign_id, 48)}
              </p>
            )}
          </div>
          <div className="flex items-center gap-6">
            <div className="text-center">
              <div
                className={`font-mono text-4xl font-bold ${
                  data.trust_score >= 70
                    ? "text-garl-accent"
                    : data.trust_score >= 40
                    ? "text-garl-warning"
                    : "text-garl-danger"
                }`}
              >
                {data.trust_score.toFixed(1)}
              </div>
              <div className="mt-1 font-mono text-xs text-garl-muted">
                Trust Score
              </div>
            </div>
            <div className="h-12 w-px bg-garl-border" />
            <div className="text-center">
              <div
                className="font-mono text-2xl font-bold uppercase"
                style={{ color: tierColor }}
              >
                {tier}
              </div>
              <div className="mt-1 font-mono text-xs text-garl-muted">
                Tier
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* Section 1: SLA Compliance Status */}
      <motion.section
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.05 }}
        className="mb-8"
      >
        <h2 className="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-garl-accent">
          SLA Compliance Status
        </h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
          <div className="rounded-lg border border-garl-border bg-garl-surface p-4">
            <div className="mb-1 font-mono text-xs text-garl-muted">
              Uptime Rate
            </div>
            <div className="font-mono text-xl font-bold text-garl-text">
              {(sla.uptime_rate ?? 0).toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg border border-garl-border bg-garl-surface p-4">
            <div className="mb-1 font-mono text-xs text-garl-muted">
              Avg. Response (ms)
            </div>
            <div className="font-mono text-xl font-bold text-garl-text">
              {sla.avg_response_ms ?? 0}
            </div>
          </div>
          <div className="rounded-lg border border-garl-border bg-garl-surface p-4">
            <div className="mb-1 font-mono text-xs text-garl-muted">
              Total Executions
            </div>
            <div className="font-mono text-xl font-bold text-garl-text">
              {sla.total_executions ?? 0}
            </div>
          </div>
          <div className="rounded-lg border border-garl-border bg-garl-surface p-4">
            <div className="mb-1 font-mono text-xs text-garl-muted">
              SLA Met
            </div>
            <div className="flex items-center gap-2">
              {sla.sla_met ? (
                <>
                  <Check className="h-5 w-5 text-garl-accent" />
                  <span className="font-mono text-sm text-garl-accent">Yes</span>
                </>
              ) : (
                <>
                  <X className="h-5 w-5 text-garl-danger" />
                  <span className="font-mono text-sm text-garl-danger">No</span>
                </>
              )}
            </div>
          </div>
          <div className="rounded-lg border border-garl-border bg-garl-surface p-4">
            <div className="mb-1 font-mono text-xs text-garl-muted">
              Tier Qualification
            </div>
            <span
              className="inline-block rounded px-2 py-0.5 font-mono text-xs font-semibold uppercase"
              style={{
                backgroundColor: `${TIER_COLORS[sla.tier_qualification || "bronze"]}20`,
                color: TIER_COLORS[sla.tier_qualification || "bronze"],
              }}
            >
              {sla.tier_qualification || "bronze"}
            </span>
          </div>
        </div>
      </motion.section>

      {/* Section 2: Security Risk Analysis */}
      <motion.section
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.1 }}
        className="mb-8"
      >
        <h2 className="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-garl-accent">
          Security Risk Analysis
        </h2>
        <div className="rounded-xl border border-garl-border bg-garl-surface p-6">
          <div className="mb-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="font-mono text-xs text-garl-muted">
                Security Score
              </span>
              <span className="font-mono text-sm font-bold text-garl-text">
                {(data.security_score ?? 0).toFixed(0)}/100
              </span>
            </div>
            <div className="h-3 w-full overflow-hidden rounded-full bg-garl-border">
              <motion.div
                initial={{ width: 0 }}
                animate={{
                  width: `${Math.min(data.security_score ?? 0, 100)}%`,
                }}
                transition={{ duration: 0.6, ease: "easeOut" }}
                className="h-full rounded-full"
                style={{
                  background:
                    (data.security_score ?? 0) >= 70
                      ? "linear-gradient(90deg, #00ff88, #00f3ff)"
                      : (data.security_score ?? 0) >= 40
                      ? "linear-gradient(90deg, #ffaa00, #ff8800)"
                      : "linear-gradient(90deg, #ff4444, #ff6666)",
                }}
              />
            </div>
          </div>
          <div className="mb-4">
            <div className="mb-2 font-mono text-xs text-garl-muted">
              Security Risks
            </div>
            <ul className="space-y-2">
              {(data.security_risks || []).length === 0 ? (
                <li className="font-mono text-xs text-garl-muted">
                  No risks detected
                </li>
              ) : (
                (data.security_risks || []).map((r, i) => (
                  <li
                    key={i}
                    className={`flex items-center gap-2 rounded px-3 py-2 font-mono text-xs ${
                      r.level === "critical"
                        ? "bg-garl-danger/10 text-garl-danger"
                        : r.level === "warning"
                        ? "bg-garl-warning/10 text-garl-warning"
                        : "bg-garl-blue/10 text-garl-blue"
                    }`}
                  >
                    {r.level === "critical" ? (
                      <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                    ) : r.level === "warning" ? (
                      <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                    ) : (
                      <Info className="h-3.5 w-3.5 shrink-0" />
                    )}
                    <span>{r.message}</span>
                  </li>
                ))
              )}
            </ul>
          </div>
          {(data.permissions_declared || []).length > 0 && (
            <div>
              <div className="mb-2 font-mono text-xs text-garl-muted">
                Declared Permissions
              </div>
              <div className="flex flex-wrap gap-2">
                {(data.permissions_declared || []).map((p, i) => (
                  <span
                    key={i}
                    className="rounded border border-garl-border px-2 py-1 font-mono text-[10px] text-garl-muted"
                  >
                    {truncateLabel(String(p), 20)}
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      </motion.section>

      {/* Section 3: 5-Dimensional Trust Analysis */}
      <motion.section
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.15 }}
        className="mb-8"
      >
        <h2 className="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-garl-accent">
          5-Dimensional Trust Analysis
        </h2>
        <div className="rounded-xl border border-garl-border bg-garl-surface p-6">
          <div className="space-y-4">
            {(
              [
                "reliability",
                "security",
                "speed",
                "cost_efficiency",
                "consistency",
              ] as const
            ).map((key) => {
              const score = dims[key] ?? 0;
              const label = dimLabels[key] || key;
              return (
                <div key={key}>
                  <div className="mb-1 flex items-center justify-between">
                    <span
                      className="font-mono text-xs text-garl-muted"
                      title={label}
                    >
                      {truncateLabel(label)}
                    </span>
                    <span
                      className={`font-mono text-xs font-bold ${
                        score >= 70
                          ? "text-garl-accent"
                          : score >= 40
                          ? "text-garl-warning"
                          : "text-garl-danger"
                      }`}
                    >
                      {score.toFixed(1)}
                    </span>
                  </div>
                  <div className="h-2 w-full overflow-hidden rounded-full bg-garl-border">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${Math.min(score, 100)}%` }}
                      transition={{ duration: 0.5, delay: 0.1 * ["reliability", "security", "speed", "cost_efficiency", "consistency"].indexOf(key) }}
                      className={`h-full rounded-full ${getBarColor(score)}`}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </motion.section>

      {/* Section 4: Anomaly History */}
      <motion.section
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.2 }}
        className="mb-8"
      >
        <h2 className="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-garl-accent">
          Anomaly History
        </h2>
        <div className="rounded-xl border border-garl-border bg-garl-surface p-6">
          <div className="mb-4 flex items-center justify-between">
            <span className="font-mono text-xs text-garl-muted">
              Total Flags
            </span>
            <span className="font-mono text-sm font-bold text-garl-text">
              {anomalyHistory.total_flags ?? 0}
            </span>
          </div>
          <div className="space-y-2">
            {(anomalyHistory.active || []).map((a: { type?: string; severity?: string; message?: string }, i: number) => (
              <div
                key={`active-${i}`}
                className="flex items-center gap-2 rounded border border-garl-danger/30 bg-garl-danger/10 px-3 py-2"
              >
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-garl-danger" />
                <span className="font-mono text-xs text-garl-danger">
                  [{a.severity || "warning"}]
                </span>
                <span className="font-mono text-xs text-garl-text">
                  {truncateLabel(a.message || "", 60)}
                </span>
              </div>
            ))}
            {(anomalyHistory.archived || []).map((a: { type?: string; severity?: string; message?: string }, i: number) => (
              <div
                key={`archived-${i}`}
                className="flex items-center gap-2 rounded border border-garl-border/50 bg-garl-bg/50 px-3 py-2 opacity-60"
              >
                <FileCheck className="h-3.5 w-3.5 shrink-0 text-garl-muted" />
                <span className="font-mono text-xs text-garl-muted">
                  [{a.severity || "archived"}]
                </span>
                <span className="font-mono text-xs text-garl-muted">
                  {truncateLabel(a.message || "", 60)}
                </span>
              </div>
            ))}
            {((anomalyHistory.active || []).length === 0 &&
              (anomalyHistory.archived || []).length === 0) && (
              <div className="py-4 text-center font-mono text-xs text-garl-muted">
                No anomaly records
              </div>
            )}
          </div>
        </div>
      </motion.section>

      {/* Section 5: Endorsement Summary */}
      <motion.section
        initial={false}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay: 0.25 }}
      >
        <h2 className="mb-4 font-mono text-sm font-semibold uppercase tracking-wider text-garl-accent">
          Endorsement Summary
        </h2>
        <div className="rounded-xl border border-garl-border bg-garl-surface p-6">
          <div className="mb-6 grid gap-4 sm:grid-cols-3">
            <div className="rounded-lg border border-garl-border bg-garl-bg/50 p-4">
              <div className="mb-1 font-mono text-xs text-garl-muted">
                Total Bonus
              </div>
              <div className="font-mono text-2xl font-bold text-garl-accent">
                +{(endorsement.total_endorsement_bonus ?? 0).toFixed(2)}
              </div>
            </div>
            <div className="rounded-lg border border-garl-border bg-garl-bg/50 p-4">
              <div className="mb-1 font-mono text-xs text-garl-muted">
                Received
              </div>
              <div className="font-mono text-2xl font-bold text-garl-text">
                {(endorsement.received || []).length}
              </div>
            </div>
            <div className="rounded-lg border border-garl-border bg-garl-bg/50 p-4">
              <div className="mb-1 font-mono text-xs text-garl-muted">
                Given
              </div>
              <div className="font-mono text-2xl font-bold text-garl-text">
                {(endorsement.given || []).length}
              </div>
            </div>
          </div>
          <div>
            <div className="mb-2 font-mono text-xs text-garl-muted">
              Recent Endorsements
            </div>
            <ul className="space-y-2">
              {recentEndorsements.length === 0 ? (
                <li className="py-4 text-center font-mono text-xs text-garl-muted">
                  No endorsements yet
                </li>
              ) : (
                recentEndorsements.map((e: { endorser_tier?: string; bonus_applied?: number; context?: string; created_at?: string; id?: string }, i: number) => (
                  <li
                    key={e.id || `endorsement-${i}`}
                    className="flex items-center justify-between rounded border border-garl-border/50 px-3 py-2"
                  >
                    <div className="flex items-center gap-2">
                      <Award className="h-3.5 w-3.5 text-garl-accent" />
                      <span
                        className="rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase"
                        style={{
                          backgroundColor: `${TIER_COLORS[e.endorser_tier || "bronze"]}20`,
                          color: TIER_COLORS[e.endorser_tier || "bronze"],
                        }}
                      >
                        {e.endorser_tier || "bronze"}
                      </span>
                      <span className="font-mono text-xs text-garl-muted">
                        {truncateLabel(e.context || "-", 30)}
                      </span>
                    </div>
                    <span className="font-mono text-xs font-bold text-garl-accent">
                      +{(e.bonus_applied ?? 0).toFixed(2)}
                    </span>
                  </li>
                ))
              )}
            </ul>
          </div>
        </div>
      </motion.section>

      {/* Export Actions */}
      <div className="mt-8 flex flex-wrap gap-3">
        <button
          onClick={() => {
            const json = JSON.stringify(data, null, 2);
            const blob = new Blob([json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `garl-compliance-${data.agent_id.slice(0, 8)}.json`;
            a.click();
            URL.revokeObjectURL(url);
          }}
          className="flex items-center gap-2 rounded-lg border border-garl-border bg-garl-surface px-4 py-2.5 font-mono text-xs text-garl-muted transition-colors hover:border-garl-accent/30 hover:text-garl-accent"
        >
          <Download className="h-3.5 w-3.5" />
          Export JSON
        </button>
        <button
          onClick={() => {
            const buildHtml = () => {
              const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
              const risks = data.security_risks ?? [];
              const riskRows = risks.length === 0
                ? '<div class="row accent">No security risks detected.</div>'
                : risks.map((r: { level: string; message: string }) =>
                    `<div class="row"><span class="label">[${esc(r.level.toUpperCase())}]</span><span class="value">${esc(r.message)}</span></div>`
                  ).join("");
              return [
                "<html><head><title>GARL Compliance Report</title>",
                "<style>",
                "body{font-family:monospace;background:#fff;color:#111;padding:40px;max-width:800px;margin:0 auto}",
                "h1{font-size:18px;border-bottom:2px solid #00AA55;padding-bottom:8px}",
                "h2{font-size:14px;margin-top:24px;color:#333}",
                ".meta{color:#666;font-size:11px}",
                ".section{margin:16px 0;padding:12px;border:1px solid #ddd;border-radius:8px}",
                ".row{display:flex;justify-content:space-between;padding:4px 0;font-size:12px}",
                ".label{color:#666}.value{font-weight:bold}",
                ".accent{color:#00AA55}.danger{color:#cc3333}",
                "@media print{body{padding:20px}}",
                "</style></head><body>",
                "<h1>GARL Protocol — Compliance Report</h1>",
                `<div class="meta">Agent: ${esc(data.name)} (${esc(data.agent_id)})<br/>`,
                `Tier: ${esc(data.certification_tier ?? "bronze")} | Trust Score: ${data.trust_score.toFixed(1)}<br/>`,
                `Generated: ${new Date().toISOString()}</div>`,
                '<div class="section"><h2>SLA Compliance</h2>',
                `<div class="row"><span class="label">Uptime Rate</span><span class="value">${(data.sla_compliance?.uptime_rate ?? 0).toFixed(1)}%</span></div>`,
                `<div class="row"><span class="label">Avg Response</span><span class="value">${data.sla_compliance?.avg_response_ms ?? 0}ms</span></div>`,
                `<div class="row"><span class="label">Total Executions</span><span class="value">${data.sla_compliance?.total_executions ?? 0}</span></div>`,
                `<div class="row"><span class="label">SLA Met</span><span class="value ${data.sla_compliance?.sla_met ? "accent" : "danger"}">${data.sla_compliance?.sla_met ? "YES" : "NO"}</span></div>`,
                "</div>",
                '<div class="section"><h2>Trust Dimensions</h2>',
                `<div class="row"><span class="label">Reliability</span><span class="value">${data.dimensions.reliability.toFixed(1)}</span></div>`,
                `<div class="row"><span class="label">Security</span><span class="value">${data.dimensions.security.toFixed(1)}</span></div>`,
                `<div class="row"><span class="label">Speed</span><span class="value">${data.dimensions.speed.toFixed(1)}</span></div>`,
                `<div class="row"><span class="label">Cost Efficiency</span><span class="value">${data.dimensions.cost_efficiency.toFixed(1)}</span></div>`,
                `<div class="row"><span class="label">Consistency</span><span class="value">${data.dimensions.consistency.toFixed(1)}</span></div>`,
                "</div>",
                `<div class="section"><h2>Security Risks</h2>${riskRows}</div>`,
                '<div class="section"><h2>Anomaly History</h2>',
                `<div class="row"><span class="label">Active Flags</span><span class="value">${(data.anomaly_history?.active ?? []).length}</span></div>`,
                `<div class="row"><span class="label">Archived</span><span class="value">${(data.anomaly_history?.archived ?? []).length}</span></div>`,
                `<div class="row"><span class="label">Total</span><span class="value">${data.anomaly_history?.total_flags ?? 0}</span></div>`,
                "</div>",
                '<div style="margin-top:32px;font-size:10px;color:#999;border-top:1px solid #ddd;padding-top:8px">',
                "GARL Protocol — garl.ai — Cryptographic trust verification for AI agents</div>",
                "</body></html>",
              ].join("\n");
            };
            const blob = new Blob([buildHtml()], { type: "text/html" });
            const url = URL.createObjectURL(blob);
            const win = window.open(url, "_blank");
            if (win) {
              win.addEventListener("load", () => { win.print(); URL.revokeObjectURL(url); });
            }
          }}
          className="flex items-center gap-2 rounded-lg bg-garl-accent px-4 py-2.5 font-mono text-xs font-semibold text-garl-bg transition-opacity hover:opacity-90"
        >
          <Download className="h-3.5 w-3.5" />
          Print / Save PDF
        </button>
      </div>
    </div>
  );
}

export default function CompliancePage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-[60vh] items-center justify-center">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
        </div>
      }
    >
      <ComplianceContent />
    </Suspense>
  );
}
