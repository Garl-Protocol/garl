/**
 * GARL Protocol JavaScript SDK v5 — Sovereign Trust Layer
 *
 * Dört entegrasyon seviyesi:
 *
 * 1. Tek satır:
 *    import garl from './garl.js';
 *    garl.init('garl_key', 'agent-uuid');
 *    garl.logAction('API dokümantasyonu oluşturuldu', 'success', { category: 'coding' });
 *
 * 2. İstemci (tam kontrol):
 *    import { GarlClient } from './garl.js';
 *    const client = new GarlClient('garl_key', 'agent-uuid');
 *    const cert = await client.verify({ status: 'success', task: '...', durationMs: 1250 });
 *
 * 3. Proaktif koruma:
 *    if (await client.shouldDelegate('target-uuid')) { ... }
 *
 * 4. OpenClaw adaptörü:
 *    import { OpenClawAdapter } from './garl.js';
 *    const adapter = new OpenClawAdapter('garl_key', 'agent-uuid');
 */

const MAX_RETRIES = 3;
const RETRY_DELAYS = [1000, 2000, 4000];

/** 5xx hatalarında üstel geri çekilme ile yeniden deneme (1s, 2s, 4s). */
async function retryFetch(url, options, retries = MAX_RETRIES) {
  let lastErr;
  for (let attempt = 0; attempt < retries; attempt++) {
    try {
      const res = await fetch(url, options);
      if (res.ok || res.status < 500) return res;
      lastErr = new Error(`GARL API error: ${res.status}`);
    } catch (err) {
      lastErr = err;
    }
    if (attempt < retries - 1) {
      const delay = RETRY_DELAYS[Math.min(attempt, RETRY_DELAYS.length - 1)];
      await new Promise((r) => setTimeout(r, delay));
    }
  }
  throw lastErr;
}

// ──────────────────────────────────────────────
//  Modül seviyesi tek satır API
// ──────────────────────────────────────────────

let _defaultClient = null;

export function init(apiKey, agentId, baseUrl = "https://api.garl.ai/api/v1") {
  _defaultClient = new GarlClient(apiKey, agentId, baseUrl);
}

export function logAction(task, result = "success", options = {}) {
  if (!_defaultClient) {
    console.warn("GARL not initialized. Call garl.init() first.");
    return Promise.resolve(null);
  }

  const { category = "other", durationMs = 0, costUsd, tokenCount, toolCalls, proofOfResult, background = true } = options;

  const doLog = () =>
    _defaultClient
      .verify({ status: result, task, durationMs, category, costUsd, tokenCount, toolCalls, proofOfResult })
      .catch((e) => { console.warn("GARL logAction failed:", e.message); return null; });

  if (background) {
    doLog();
    return Promise.resolve(null);
  }
  return doLog();
}

/**
 * Trust Gate: hedef ajanın güvenilirliğini kontrol eder.
 *
 * @param {string} targetAgentId
 * @param {object} [options]
 * @param {number} [options.minScore=50]
 * @param {boolean} [options.requireVerified=false]
 * @returns {Promise<{trusted: boolean, score: number, registered: boolean, recommendation: string, reason: string}>}
 */
export async function isTrusted(targetAgentId, options = {}) {
  if (!_defaultClient) {
    console.warn("GARL not initialized. Call garl.init() first.");
    return { trusted: false, score: 0, registered: false, recommendation: "unknown", reason: "GARL client not initialized" };
  }
  return _defaultClient.isTrusted(targetAgentId, options);
}

/**
 * Trust Gate dekoratör kalıbı: fn çağrılmadan önce güven kontrolü yapar.
 *
 * @param {Function} fn - İlk argümanı targetAgentId olan fonksiyon
 * @param {object} [options]
 * @param {number} [options.minScore=50]
 * @param {string} [options.mode="warn"] - "warn" veya "block"
 */
export function requireTrust(fn, options = {}) {
  const { minScore = 50, mode = "warn" } = options;
  return async function (targetAgentId, ...args) {
    const result = await isTrusted(targetAgentId, { minScore });
    if (!result.trusted) {
      const msg = `Warning: Target agent ${targetAgentId} is not verified on GARL. Delegation is risky. Register at https://garl.ai — Reason: ${result.reason}`;
      if (mode === "block") {
        console.warn(msg + " — Delegation BLOCKED.");
        return null;
      }
      console.warn(msg);
    }
    return fn(targetAgentId, ...args);
  };
}

// ──────────────────────────────────────────────
//  Tam İstemci
// ──────────────────────────────────────────────

export class GarlClient {
  constructor(apiKey, agentId, baseUrl = "https://api.garl.ai/api/v1") {
    this.apiKey = apiKey;
    this.agentId = agentId;
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async verify({
    status,
    task,
    durationMs,
    category = "other",
    inputSummary = "",
    outputSummary = "",
    metadata = {},
    runtimeEnv = "",
    toolCalls,
    costUsd,
    tokenCount,
    proofOfResult,
    piiMask = false,
  }) {
    const body = {
      agent_id: this.agentId,
      task_description: task,
      status,
      duration_ms: durationMs,
      category,
      input_summary: inputSummary,
      output_summary: outputSummary,
      metadata,
      runtime_env: runtimeEnv,
      pii_mask: piiMask,
    };
    if (toolCalls) body.tool_calls = toolCalls;
    if (costUsd !== undefined) body.cost_usd = costUsd;
    if (tokenCount !== undefined) body.token_count = tokenCount;
    if (proofOfResult !== undefined) body.proof_of_result = proofOfResult;

    const res = await retryFetch(`${this.baseUrl}/verify`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify(body),
    });

    if (!res.ok) throw new Error(`GARL API error: ${res.status} ${res.statusText}`);
    return res.json();
  }

  async verifyBatch(traces) {
    const body = { traces: traces.map((t) => ({ agent_id: this.agentId, ...t })) };
    const res = await retryFetch(`${this.baseUrl}/verify/batch`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async getHistory(limit = 50) {
    const res = await fetch(`${this.baseUrl}/agents/${this.agentId}/history?limit=${limit}`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async checkTrust(targetAgentId) {
    const res = await retryFetch(`${this.baseUrl}/trust/verify?agent_id=${targetAgentId}`, {});
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async isTrusted(targetAgentId, options = {}) {
    const { minScore = 50, requireVerified = false } = options;
    try {
      const data = await this.checkTrust(targetAgentId);
      if (data.registered === false) {
        return { trusted: false, score: 0, registered: false, recommendation: "unknown", reason: "Agent not registered on GARL" };
      }
      const score = data.trust_score || 0;
      const verified = data.verified || false;
      const recommendation = data.recommendation || "unknown";
      if (score < minScore) {
        return { trusted: false, score, registered: true, recommendation, reason: `Trust score ${score.toFixed(1)} below threshold ${minScore}` };
      }
      if (requireVerified && !verified) {
        return { trusted: false, score, registered: true, recommendation, reason: "Agent not verified (requires 10+ traces)" };
      }
      return { trusted: true, score, registered: true, recommendation, reason: "Agent meets trust requirements" };
    } catch (e) {
      return { trusted: false, score: 0, registered: false, recommendation: "unknown", reason: `Trust check failed: ${e.message}` };
    }
  }

  async getAgentCard(targetAgentId) {
    const aid = targetAgentId || this.agentId;
    const res = await fetch(`${this.baseUrl}/agents/${aid}/card`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async getScore() {
    const res = await fetch(`${this.baseUrl}/agents/${this.agentId}`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async getDetail() {
    const res = await fetch(`${this.baseUrl}/agents/${this.agentId}/detail`, {
      headers: { "x-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async search(query = "", category = null, limit = 10) {
    const params = new URLSearchParams({ q: query, limit: String(limit) });
    if (category) params.set("category", category);
    const res = await fetch(`${this.baseUrl}/search?${params}`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async findTrustedAgent(category = "other", minScore = 65) {
    const agents = await this.search("", category, 5);
    return agents.find((a) => parseFloat(a.trust_score) >= minScore) || null;
  }

  /** Proaktif delegasyon koruması — sertifikasyon kademesi (certification_tier) kontrolü dahil. Bronze varsayılan olarak engellenir. */
  async shouldDelegate(targetAgentId, {
    minScore = 60,
    requireVerified = true,
    blockAnomalies = true,
    blockBronze = true,
    minTier = "silver",
  } = {}) {
    const tierOrder = ["bronze", "silver", "gold", "enterprise"];
    const minTierIdx = tierOrder.includes(minTier) ? tierOrder.indexOf(minTier) : 1;

    try {
      const trust = await this.checkTrust(targetAgentId);
      const score = parseFloat(trust.trust_score || 0);
      if (score < minScore) return false;
      if (requireVerified && !trust.verified) return false;
      if (blockAnomalies && (trust.anomalies?.length || 0) > 0) return false;
      if (["critical", "high"].includes(trust.risk_level)) return false;

      const targetTier = trust.certification_tier || "bronze";
      const targetTierIdx = tierOrder.includes(targetTier) ? tierOrder.indexOf(targetTier) : 0;
      if (blockBronze && targetTier === "bronze") return false;
      if (targetTierIdx < minTierIdx) return false;

      return true;
    } catch {
      return false;
    }
  }

  async getDelegationReport(targetAgentId) {
    const trust = await this.checkTrust(targetAgentId);
    return {
      agentId: targetAgentId,
      name: trust.name || "Unknown",
      trustScore: trust.trust_score,
      recommendation: trust.recommendation,
      riskLevel: trust.risk_level,
      certificationTier: trust.certification_tier || "bronze",
      safeForGeneral: ["trusted", "trusted_with_monitoring"].includes(trust.recommendation),
      safeForSensitive: trust.recommendation === "trusted",
      hasAnomalies: (trust.anomalies?.length || 0) > 0,
      dimensions: trust.dimensions,
      lastActive: trust.last_active,
    };
  }

  async endorse(targetAgentId, context = "") {
    const res = await fetch(`${this.baseUrl}/endorse`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify({ target_agent_id: targetAgentId, context }),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async getEndorsements(agentId) {
    const aid = agentId || this.agentId;
    const res = await fetch(`${this.baseUrl}/endorsements/${aid}`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async compareWith(...agentIds) {
    const allIds = [this.agentId, ...agentIds].join(",");
    const res = await fetch(`${this.baseUrl}/compare?agents=${allIds}`);
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async registerWebhook(url, events) {
    const res = await fetch(`${this.baseUrl}/webhooks`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify({
        agent_id: this.agentId,
        url,
        events: events || ["trace_recorded", "milestone", "anomaly"],
      }),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async listWebhooks() {
    const res = await fetch(`${this.baseUrl}/webhooks/${this.agentId}`, {
      headers: { "x-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async updateWebhook(webhookId, { isActive, url, events } = {}) {
    const body = {};
    if (isActive !== undefined) body.is_active = isActive;
    if (url !== undefined) body.url = url;
    if (events !== undefined) body.events = events;

    const res = await fetch(`${this.baseUrl}/webhooks/${this.agentId}/${webhookId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  async deleteWebhook(webhookId) {
    const res = await fetch(`${this.baseUrl}/webhooks/${this.agentId}/${webhookId}`, {
      method: "DELETE",
      headers: { "x-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return true;
  }

  async track(task, fn, category = "other", costUsd) {
    const start = Date.now();
    let status = "success";
    let result;

    try {
      result = await fn();
    } catch (err) {
      status = "failure";
      throw err;
    } finally {
      const durationMs = Date.now() - start;
      const certificate = await this.verify({ status, task, durationMs, category, costUsd });
      if (status === "success") {
        return { result, certificate };
      }
    }
  }

  // ─── v1.0 Sovereign Trust Layer yeni metodlar ───

  /** GET /api/v1/trust/route — Kategori ve kademe filtresiyle en güvenilir ajanları önerir. */
  async route(category, minTier = "silver", limit = 3) {
    const params = new URLSearchParams({ category, min_tier: minTier, limit: String(limit) });
    const res = await retryFetch(`${this.baseUrl}/trust/route?${params}`, {});
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  /** route() çağırır ve en iyi eşleşmeyi döner. */
  async findBestAgent(category, minTier = "silver") {
    const result = await this.route(category, minTier, 3);
    const agents = result.agents || [];
    return agents[0] || null;
  }

  /** DELETE /api/v1/agents/{agentId} — GDPR uyumlu yumuşak silme. */
  async softDelete(confirmation = "DELETE_CONFIRMED") {
    if (confirmation !== "DELETE_CONFIRMED") {
      throw new Error("confirmation must be 'DELETE_CONFIRMED'");
    }
    const res = await retryFetch(`${this.baseUrl}/agents/${this.agentId}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify({ confirmation }),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  /** POST /api/v1/agents/{agentId}/anonymize — GDPR uyumlu anonimleştirme. */
  async anonymize(confirmation = "ANONYMIZE_CONFIRMED") {
    if (confirmation !== "ANONYMIZE_CONFIRMED") {
      throw new Error("confirmation must be 'ANONYMIZE_CONFIRMED'");
    }
    const res = await retryFetch(`${this.baseUrl}/agents/${this.agentId}/anonymize`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.apiKey },
      body: JSON.stringify({ confirmation }),
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  /** GET /api/v1/agents/{agentId}/compliance — Kurumsal uyumluluk raporu. */
  async getCompliance(agentId = null) {
    const aid = agentId || this.agentId;
    const res = await retryFetch(`${this.baseUrl}/agents/${aid}/compliance`, {
      headers: { "x-api-key": this.apiKey },
    });
    if (!res.ok) throw new Error(`GARL API error: ${res.status}`);
    return res.json();
  }

  /** Ajanın DID'sini (sovereign_id) get_score() üzerinden döner. */
  async getSovereignId() {
    const score = await this.getScore();
    return score.sovereign_id ?? null;
  }

  /** Ajanın sertifikasyon kademesini get_score() üzerinden döner. */
  async getTier() {
    const score = await this.getScore();
    return score.certification_tier || "bronze";
  }
}

// ──────────────────────────────────────────────
//  OpenClaw Adaptörü
// ──────────────────────────────────────────────

export class OpenClawAdapter {
  constructor(apiKey, agentId, baseUrl = "https://api.garl.ai/api/v1") {
    this.client = new GarlClient(apiKey, agentId, baseUrl);
    this.agentId = agentId;
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async reportTask({ message, durationMs = 0, status = "success", channel = null,
                      sessionId = null, toolCalls = null, costUsd = null, category = "" }) {
    const body = {
      agent_id: this.agentId, message, status, duration_ms: durationMs,
      category, runtime_env: "openclaw", channel, session_id: sessionId,
    };
    if (toolCalls) body.tool_calls = toolCalls;
    if (costUsd !== null) body.usage = { cost_usd: costUsd };

    const res = await retryFetch(`${this.baseUrl}/ingest/openclaw`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "x-api-key": this.client.apiKey },
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`GARL ingest error: ${res.status}`);
    return res.json();
  }

  async shouldDelegate(targetAgentId, minScore = 50, options = {}) {
    const { requireVerified = false, blockAnomalies = false, minTier = "silver" } = options;
    return this.client.shouldDelegate(targetAgentId, {
      minScore,
      requireVerified,
      blockAnomalies,
      blockBronze: true,
      minTier,
    });
  }

  async getDelegationRecommendation(targetAgentId) {
    const report = await this.client.getDelegationReport(targetAgentId);
    return {
      agentId: report.agentId,
      name: report.name,
      score: report.trustScore,
      recommendation: report.recommendation,
      riskLevel: report.riskLevel,
      certificationTier: report.certificationTier,
      safeForGeneral: report.safeForGeneral,
      safeForSensitive: report.safeForSensitive,
      hasAnomalies: report.hasAnomalies,
      dimensions: report.dimensions,
    };
  }

  async findBestAgentFor(category, minScore = 65) {
    return this.client.findTrustedAgent(category, minScore);
  }

  /** GET /api/v1/trust/route — Kategori ve kademe ile en güvenilir ajanları önerir. */
  async route(category, minTier = "silver", limit = 3) {
    return this.client.route(category, minTier, limit);
  }

  /** route() çağırır ve en iyi eşleşmeyi döner. */
  async findBestAgent(category, minTier = "silver") {
    return this.client.findBestAgent(category, minTier);
  }
}

export default { init, logAction, GarlClient, OpenClawAdapter };
