#!/usr/bin/env node

/**
 * GARL Protocol v1.0.1 "Sovereign Trust Layer" MCP Server v3.0.0
 *
 * Anthropic MCP standardına %100 uyumlu güven araçları sunucusu.
 * Cursor, Windsurf, Claude Desktop, OpenClaw ve tüm MCP istemcileriyle çalışır.
 */

import { Server } from "@modelcontextprotocol/sdk/server/index.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from "@modelcontextprotocol/sdk/types.js";

const API_URL = (process.env.GARL_API_URL || "https://api.garl.ai/api/v1").replace(/\/$/, "");
const API_KEY = process.env.GARL_API_KEY || "";
const AGENT_ID = process.env.GARL_AGENT_ID || "";

// GARL API'ye istek gönderir
async function garlFetch(path, options = {}) {
  const url = `${API_URL}${path}`;
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (API_KEY) headers["x-api-key"] = API_KEY;

  const res = await fetch(url, { ...options, headers });
  const text = await res.text();
  if (!res.ok) throw new Error(`GARL API ${res.status}: ${text}`);
  return text ? JSON.parse(text) : {};
}

// Kademe sıralaması
const TIER_ORDER = { bronze: 1, silver: 2, gold: 3, enterprise: 4 };

const TOOLS = [
  {
    name: "garl_verify",
    description:
      "Send an execution trace to GARL and receive a cryptographic certificate. " +
      "Call this after completing a meaningful task to build your trust reputation.",
    inputSchema: {
      type: "object",
      properties: {
        task_description: { type: "string", description: "Short one-line summary of the completed task" },
        status: { type: "string", enum: ["success", "failure", "partial"], description: "Task result" },
        duration_ms: { type: "number", description: "Task duration in milliseconds" },
        category: { type: "string", enum: ["coding", "research", "sales", "data", "automation", "other"], description: "Task category", default: "other" },
        tool_calls: { type: "array", items: { type: "object", properties: { name: { type: "string" }, duration_ms: { type: "number" } }, required: ["name"] }, description: "List of tools used during the task" },
        cost_usd: { type: "number", description: "Token/API cost in USD (if known)" },
        input_summary: { type: "string", description: "Input/prompt summary" },
        output_summary: { type: "string", description: "Output/result summary" },
        permissions_used: { type: "array", items: { type: "string" }, description: "List of permissions used (e.g., file_read, network)" },
        security_context: { type: "object", description: "Security context (e.g., sandbox, production)", properties: { environment: { type: "string" }, isolation_level: { type: "string" } } },
      },
      required: ["task_description", "status", "duration_ms"],
    },
  },
  {
    name: "garl_verify_batch",
    description: "Send up to 50 execution traces in a single request for high-volume agents.",
    inputSchema: {
      type: "object",
      properties: {
        traces: { type: "array", items: { type: "object", properties: { task_description: { type: "string" }, status: { type: "string", enum: ["success", "failure", "partial"] }, duration_ms: { type: "number" }, category: { type: "string" } }, required: ["task_description", "status", "duration_ms"] }, description: "Trace array (max 50)", maxItems: 50 },
      },
      required: ["traces"],
    },
  },
  {
    name: "garl_check_trust",
    description:
      "Check another agent's trust score and get a delegation recommendation. " +
      "Use this to verify the target agent's reliability before delegating work.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to check" } },
      required: ["agent_id"],
    },
  },
  {
    name: "garl_should_delegate",
    description:
      "Proactive trust guard — check if it's safe to delegate work to another agent. " +
      "Returns clear yes/no with reasoning. Automatically blocks low-trust, unverified, or anomalous agents.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "UUID of the target agent to evaluate" },
        min_score: { type: "number", description: "Required minimum trust score (default: 60)", default: 60 },
        min_tier: { type: "string", enum: ["bronze", "silver", "gold", "enterprise"], description: "Required minimum certification level (default: silver)", default: "silver" },
        require_verified: { type: "boolean", description: "Require >= 10 traces (default: true)", default: true },
        block_anomalies: { type: "boolean", description: "Block agents with active anomaly flags (default: true)", default: true },
      },
      required: ["agent_id"],
    },
  },
  {
    name: "garl_get_score",
    description: "Get your current GARL trust score, multi-dimensional breakdown, and profile.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "Agent UUID (default: your own agent)" } },
    },
  },
  {
    name: "garl_trust_history",
    description: "Get an agent's trust score history over time for charting and auditing.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "Agent UUID (default: your own agent)" },
        limit: { type: "number", description: "Number of history records (default: 50)", default: 50 },
      },
    },
  },
  {
    name: "garl_leaderboard",
    description: "List the highest-scored agents in the GARL Protocol with optional category filter.",
    inputSchema: {
      type: "object",
      properties: {
        category: { type: "string", enum: ["coding", "research", "sales", "data", "automation", "other", "all"], description: "Filter by category (default: all)" },
        limit: { type: "number", description: "Number of results (default: 10, max: 100)", default: 10 },
      },
    },
  },
  {
    name: "garl_compare",
    description: "Compare multiple agents side-by-side across all trust dimensions.",
    inputSchema: {
      type: "object",
      properties: { agent_ids: { type: "array", items: { type: "string" }, description: "List of agent UUIDs to compare (2-10)", minItems: 2, maxItems: 10 } },
      required: ["agent_ids"],
    },
  },
  {
    name: "garl_agent_card",
    description: "Get an Agent Card with trust data for an agent. Includes trust score, dimensions, and capabilities.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "Agent UUID (default: your own agent)" } },
    },
  },
  {
    name: "garl_endorse",
    description:
      "Endorse another agent (A2A reputation transfer). Your trust score and trace count " +
      "determine the bonus magnitude. Sybil-resistant: low-trust agents produce zero bonus.",
    inputSchema: {
      type: "object",
      properties: {
        target_agent_id: { type: "string", description: "UUID of the agent to endorse" },
        context: { type: "string", description: "Why you are endorsing this agent" },
      },
      required: ["target_agent_id"],
    },
  },
  {
    name: "garl_register_webhook",
    description: "Register a webhook to receive notifications about trust score changes, milestones, and anomalies.",
    inputSchema: {
      type: "object",
      properties: {
        url: { type: "string", description: "Webhook endpoint URL" },
        events: { type: "array", items: { type: "string", enum: ["trace_recorded", "milestone", "anomaly", "score_change", "tier_change"] }, description: "Event types to subscribe to" },
      },
      required: ["url"],
    },
  },
  {
    name: "garl_search",
    description: "Search agents by name, description, or category. Trusted agent discovery for delegation.",
    inputSchema: {
      type: "object",
      properties: {
        query: { type: "string", description: "Search query (name or description)" },
        category: { type: "string", enum: ["coding", "research", "sales", "data", "automation", "other", "all"], description: "Filter by category" },
        limit: { type: "number", description: "Max results (default: 10)", default: 10 },
      },
    },
  },
  {
    name: "garl_route",
    description: "Smart routing: category + min_tier → best agents. Lists agents in a specific category at or above a minimum certification level.",
    inputSchema: {
      type: "object",
      properties: {
        category: { type: "string", description: "Category filter (e.g., coding, research)" },
        min_tier: { type: "string", enum: ["bronze", "silver", "gold", "enterprise"], description: "Minimum certification level" },
        limit: { type: "number", description: "Number of agents to return (default: 10)", default: 10 },
      },
    },
  },
  {
    name: "garl_compliance",
    description: "CISO compliance report. Summarizes the agent's security and compliance status.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to get the report for" } },
      required: ["agent_id"],
    },
  },
  {
    name: "garl_soft_delete",
    description: "GDPR soft delete. Deactivates agent data (recoverable). x-api-key required.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to delete" } },
      required: ["agent_id"],
    },
  },
  {
    name: "garl_anonymize",
    description: "GDPR anonymization. Irreversibly anonymizes agent data. x-api-key required.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to anonymize" } },
      required: ["agent_id"],
    },
  },
];

// Araç çağrılarını işler
async function handleToolCall(name, args) {
  switch (name) {
    case "garl_verify": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured. Set it as an environment variable.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured. Set it as an environment variable.");
      if (!args.task_description) throw new Error("task_description is required.");
      if (!args.status) throw new Error("status is required.");
      if (args.duration_ms === undefined || args.duration_ms === null) throw new Error("duration_ms is required.");
      const body = { agent_id: AGENT_ID, task_description: args.task_description, status: args.status, duration_ms: args.duration_ms, category: args.category || "other", runtime_env: "openclaw-mcp", input_summary: args.input_summary || "", output_summary: args.output_summary || "" };
      if (args.tool_calls) body.tool_calls = args.tool_calls;
      if (args.cost_usd !== undefined) body.cost_usd = args.cost_usd;
      if (args.permissions_used) body.permissions_used = args.permissions_used;
      if (args.security_context) body.security_context = args.security_context;
      const result = await garlFetch("/verify", { method: "POST", body: JSON.stringify(body) });
      return { content: [{ type: "text", text: [`Trace successfully recorded.`, `Trust delta: ${result.trust_delta > 0 ? "+" : ""}${result.trust_delta.toFixed(2)}`, `Certificate ID: ${result.id}`, `Status: ${result.status}`].join("\n") }] };
    }

    case "garl_verify_batch": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.traces || !args.traces.length) throw new Error("traces array is required.");
      const traces = args.traces.map(t => ({ agent_id: AGENT_ID, task_description: t.task_description, status: t.status, duration_ms: t.duration_ms, category: t.category || "other", runtime_env: "openclaw-mcp" }));
      const result = await garlFetch("/verify/batch", { method: "POST", body: JSON.stringify({ traces }) });
      return { content: [{ type: "text", text: `Batch submission: ${result.submitted} successful, ${result.failed} failed.` }] };
    }

    case "garl_check_trust": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      const result = await garlFetch(`/trust/verify?agent_id=${encodeURIComponent(args.agent_id)}`);
      const dims = result.dimensions;
      const anomalyText = result.anomalies?.length ? `\nAnomalies: ${result.anomalies.map(a => a.type || a).join(", ")}` : "";
      const certTier = result.certification_tier ? `\nCertification Tier: ${result.certification_tier}` : "";
      const sovereignId = result.sovereign_id ? `\nSovereign ID: ${result.sovereign_id}` : "";
      return { content: [{ type: "text", text: [`Agent: ${result.name}`, `Trust Score: ${result.trust_score.toFixed(1)}/100`, `Risk Level: ${result.risk_level.toUpperCase()}`, `Recommendation: ${result.recommendation}`, `Verified: ${result.verified ? "Yes" : "No"} (${result.total_traces} traces)`, certTier, sovereignId, ``, `Dimensions:`, `  Reliability:       ${(dims?.reliability ?? 0).toFixed(1)}`, `  Security:          ${(dims?.security ?? 0).toFixed(1)}`, `  Speed:             ${(dims?.speed ?? 0).toFixed(1)}`, `  Cost Efficiency:   ${(dims?.cost_efficiency ?? 0).toFixed(1)}`, `  Consistency:       ${(dims?.consistency ?? 0).toFixed(1)}`, anomalyText].filter(Boolean).join("\n") }] };
    }

    case "garl_should_delegate": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      const trust = await garlFetch(`/trust/verify?agent_id=${encodeURIComponent(args.agent_id)}`);
      const minScore = args.min_score ?? 60;
      const minTier = (args.min_tier || "silver").toLowerCase();
      const requireVerified = args.require_verified ?? true;
      const blockAnomalies = args.block_anomalies ?? true;
      const reasons = [];
      let safe = true;
      if (parseFloat(trust.trust_score) < minScore) { reasons.push(`Score ${trust.trust_score.toFixed(1)} below threshold ${minScore}`); safe = false; }
      const agentTier = (trust.certification_tier || "bronze").toLowerCase();
      if ((TIER_ORDER[agentTier] ?? 0) < (TIER_ORDER[minTier] ?? 1)) { reasons.push(`Tier ${agentTier} below required ${minTier}`); safe = false; }
      if (requireVerified && !trust.verified) { reasons.push(`Unverified (${trust.total_traces} traces, 10+ required)`); safe = false; }
      if (blockAnomalies && trust.anomalies?.length > 0) { reasons.push(`Active anomalies: ${trust.anomalies.map(a => a.type || a).join(", ")}`); safe = false; }
      if (["critical", "high"].includes(trust.risk_level)) { reasons.push(`Risk level: ${trust.risk_level.toUpperCase()}`); safe = false; }
      if (safe) reasons.push("All trust checks passed");
      return { content: [{ type: "text", text: [`Delegation for ${trust.name}: ${safe ? "SAFE" : "BLOCKED"}`, `Trust Score: ${trust.trust_score.toFixed(1)}/100`, `Risk Level: ${trust.risk_level.toUpperCase()}`, `Decision: ${trust.recommendation}`, `Reasons: ${reasons.join("; ")}`].join("\n") }] };
    }

    case "garl_get_score": {
      const aid = args.agent_id || AGENT_ID;
      const result = await garlFetch(`/agents/${aid}`);
      return { content: [{ type: "text", text: [`Agent: ${result.name}`, `Trust Score: ${result.trust_score.toFixed(1)}/100`, `Success Rate: ${result.success_rate.toFixed(1)}%`, `Total Traces: ${result.total_traces}`, `Category: ${result.category}`, `Framework: ${result.framework}`].join("\n") }] };
    }

    case "garl_trust_history": {
      const aid = args.agent_id || AGENT_ID;
      const limit = Math.min(args.limit || 50, 200);
      const result = await garlFetch(`/agents/${aid}/history?limit=${limit}`);
      const summary = result.slice(0, 10).map(h => `${h.created_at?.slice(0, 16)} — Score: ${parseFloat(h.trust_score).toFixed(1)} (${h.event_type}, delta: ${parseFloat(h.trust_delta).toFixed(2)})`).join("\n");
      return { content: [{ type: "text", text: `Trust History (last ${result.length} records):\n\n${summary}${result.length > 10 ? `\n... and ${result.length - 10} more` : ""}` }] };
    }

    case "garl_leaderboard": {
      const cat = args.category && args.category !== "all" ? `&category=${encodeURIComponent(args.category)}` : "";
      const limit = Math.min(Math.max(args.limit || 10, 1), 100);
      const result = await garlFetch(`/leaderboard?limit=${limit}${cat}`);
      const rows = result.map(a => `#${a.rank} ${a.name} — ${a.trust_score.toFixed(1)} (${a.framework}, ${a.total_traces} traces)`).join("\n");
      return { content: [{ type: "text", text: `GARL Leaderboard:\n\n${rows}` }] };
    }

    case "garl_compare": {
      if (!args.agent_ids || args.agent_ids.length < 2) throw new Error("At least 2 agent_ids required.");
      if (args.agent_ids.length > 10) throw new Error("Maximum 10 agent_ids allowed.");
      const result = await garlFetch(`/compare?agents=${args.agent_ids.join(",")}`);
      const rows = result.map(a => `${a.name}: Score=${a.trust_score.toFixed(1)} Rel=${(a.score_reliability || 50).toFixed(1)} Sec=${(a.score_security || 50).toFixed(1)} Spd=${(a.score_speed || 50).toFixed(1)} Cost=${(a.score_cost_efficiency || 50).toFixed(1)} Con=${(a.score_consistency || 50).toFixed(1)}`).join("\n");
      return { content: [{ type: "text", text: `Agent Comparison:\n\n${rows}` }] };
    }

    case "garl_agent_card": {
      const aid = args.agent_id || AGENT_ID;
      const result = await garlFetch(`/agents/${aid}/card`);
      return { content: [{ type: "text", text: JSON.stringify(result, null, 2) }] };
    }

    case "garl_endorse": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.target_agent_id) throw new Error("target_agent_id is required.");
      const result = await garlFetch("/endorse", { method: "POST", body: JSON.stringify({ target_agent_id: args.target_agent_id, context: args.context || "" }) });
      return { content: [{ type: "text", text: [`Endorsement sent.`, `Target: ${args.target_agent_id}`, `Applied bonus: +${result.bonus_applied.toFixed(4)}`, `Target new trust score: ${result.target_new_trust_score.toFixed(2)}`].join("\n") }] };
    }

    case "garl_register_webhook": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.url) throw new Error("Webhook URL is required.");
      const result = await garlFetch("/webhooks", { method: "POST", body: JSON.stringify({ agent_id: AGENT_ID, url: args.url, events: args.events || ["trace_recorded", "milestone", "anomaly"] }) });
      return { content: [{ type: "text", text: `Webhook registered.\nID: ${result.id}\nSecret: ${result.secret}\nEvents: ${result.events.join(", ")}` }] };
    }

    case "garl_search": {
      const params = new URLSearchParams();
      if (args.query) params.set("q", args.query);
      if (args.category && args.category !== "all") params.set("category", args.category);
      params.set("limit", String(Math.min(args.limit || 10, 50)));
      const result = await garlFetch(`/search?${params}`);
      const rows = result.map(a => `${a.name} — Score: ${parseFloat(a.trust_score).toFixed(1)} (${a.category}, ${a.total_traces} traces)${a.verified ? " ✓" : ""}`).join("\n");
      return { content: [{ type: "text", text: `Search Results:\n\n${rows || "No agents found."}` }] };
    }

    case "garl_route": {
      const params = new URLSearchParams();
      if (args.category) params.set("category", args.category);
      if (args.min_tier) params.set("min_tier", args.min_tier);
      params.set("limit", String(args.limit || 10));
      const result = await garlFetch(`/trust/route?${params}`);
      const recs = result.recommendations || result;
      const rows = Array.isArray(recs) ? recs.map((a, i) => `${i + 1}. ${a.name || a.agent_id} — Score: ${(a.trust_score ?? 0).toFixed(1)} [${a.certification_tier || "N/A"}]`).join("\n") : JSON.stringify(result, null, 2);
      return { content: [{ type: "text", text: `Routing Results:\n\n${rows}` }] };
    }

    case "garl_compliance": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured. Required for CISO report.");
      const result = await garlFetch(`/agents/${encodeURIComponent(args.agent_id)}/compliance`);
      return { content: [{ type: "text", text: typeof result === "object" ? JSON.stringify(result, null, 2) : String(result) }] };
    }

    case "garl_soft_delete": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured. Required for GDPR deletion.");
      await garlFetch(`/agents/${encodeURIComponent(args.agent_id)}`, { method: "DELETE", body: JSON.stringify({ confirmation: "DELETE_CONFIRMED" }) });
      return { content: [{ type: "text", text: `Agent ${args.agent_id} soft-deleted (GDPR).` }] };
    }

    case "garl_anonymize": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured. Required for GDPR anonymization.");
      await garlFetch(`/agents/${encodeURIComponent(args.agent_id)}/anonymize`, { method: "POST", body: JSON.stringify({ confirmation: "ANONYMIZE_CONFIRMED" }) });
      return { content: [{ type: "text", text: `Agent ${args.agent_id} anonymized (GDPR).` }] };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

const server = new Server(
  { name: "garl-trust", version: "3.0.0" },
  { capabilities: { tools: {} } }
);

server.setRequestHandler(ListToolsRequestSchema, async () => ({ tools: TOOLS }));

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;
  try {
    return await handleToolCall(name, args || {});
  } catch (error) {
    return { content: [{ type: "text", text: `Error: ${error.message}` }], isError: true };
  }
});

async function main() {
  if (!API_KEY) {
    console.error("Warning: GARL_API_KEY not set. Write operations will fail. Register at https://garl.dev or run the setup script.");
  }
  if (!AGENT_ID) {
    console.error("Warning: GARL_AGENT_ID not set. Trace submissions will fail.");
  }
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => { console.error("Fatal error:", err); process.exit(1); });
