#!/usr/bin/env node

/**
 * GARL Protocol MCP Server v1.4.0
 *
 * Cryptographic verification for AI agent actions: signed receipts,
 * Trust Vectors, capability tokens, capability gates, reversibility.
 *
 * Tools added in v1.3.0:
 *   - garl_get_trust_vector       (multi-dim reputation, replaces single score)
 *   - garl_record_action_receipt  (Action Receipt v0.1 — generic, beyond commits)
 *
 * Tools added in v1.4.0:
 *   - garl_issue_capability_token  (JWT-shaped + ECDSA-secp256k1 + RFC 6979)
 *   - garl_verify_capability_token (signature + exp + revocation)
 *   - garl_revoke_capability_token (cascades to attenuated descendants)
 *   - garl_evaluate_action         (Capability Gate pre-flight)
 *   - garl_undo_action             (UETA §10(b) consumer-undo)
 *
 * Works with Claude Desktop, Cursor, Windsurf, and all MCP-compatible clients.
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

// Sends requests to the GARL API
async function garlFetch(path, options = {}) {
  const url = `${API_URL}${path}`;
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (API_KEY) headers["x-api-key"] = API_KEY;

  const res = await fetch(url, { ...options, headers });
  const text = await res.text();
  if (!res.ok) throw new Error(`GARL API ${res.status}: ${text}`);
  return text ? JSON.parse(text) : {};
}

// Tier ordering for comparison
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
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
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
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_get_score",
    description: "Get your current GARL trust score, multi-dimensional breakdown, and profile.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "Agent UUID (default: your own agent)" } },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_compare",
    description: "Compare multiple agents side-by-side across all trust dimensions.",
    inputSchema: {
      type: "object",
      properties: { agent_ids: { type: "array", items: { type: "string" }, description: "List of agent UUIDs to compare (2-10)", minItems: 2, maxItems: 10 } },
      required: ["agent_ids"],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_agent_card",
    description: "Get an Agent Card with trust data for an agent. Includes trust score, dimensions, and capabilities.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "Agent UUID (default: your own agent)" } },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
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
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
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
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
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
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_compliance",
    description: "CISO compliance report. Summarizes the agent's security and compliance status.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to get the report for" } },
      required: ["agent_id"],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_register_agent",
    description:
      "Register a new AI agent on GARL Protocol. Returns a DID identity, API key, and initial trust score. " +
      "Use this when an agent wants to join the trust network.",
    inputSchema: {
      type: "object",
      properties: {
        name: { type: "string", description: "Agent name (unique)" },
        framework: { type: "string", description: "Framework the agent uses (e.g., langchain, crewai, autogpt, custom)" },
        description: { type: "string", description: "Short description of the agent's purpose" },
        category: { type: "string", enum: ["coding", "research", "sales", "data", "automation", "other"], description: "Primary task category", default: "other" },
      },
      required: ["name"],
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
  {
    name: "garl_get_feed",
    description: "Get the live trust feed — recent verification events across the GARL network.",
    inputSchema: {
      type: "object",
      properties: {
        limit: { type: "number", description: "Number of feed entries (default: 10, max: 50)", default: 10 },
      },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_soft_delete",
    description: "GDPR soft delete. Deactivates agent data (recoverable). x-api-key required.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to delete" } },
      required: ["agent_id"],
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "garl_anonymize",
    description: "GDPR anonymization. Irreversibly anonymizes agent data. x-api-key required.",
    inputSchema: {
      type: "object",
      properties: { agent_id: { type: "string", description: "UUID of the agent to anonymize" } },
      required: ["agent_id"],
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: false },
  },
  {
    name: "garl_trust_gate",
    description:
      "Mandatory pre-delegation trust gate. Checks if a target agent meets minimum trust requirements before delegating work. " +
      "Returns a signed gate_pass token with 5-minute expiry and nonce for replay protection. " +
      "Use this as a hard prerequisite before any delegation.",
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "UUID of the target agent to gate-check" },
        min_score: { type: "number", description: "Minimum trust score required (default: 60)", default: 60 },
        min_tier: { type: "string", enum: ["bronze", "silver", "gold", "enterprise"], description: "Minimum certification tier (default: silver)", default: "silver" },
      },
      required: ["agent_id"],
    },
  },
  {
    name: "garl_receipt",
    description:
      "Fetch a public, shareable GARL Receipt for any trace hash. Works without an API key. " +
      "Accepts either a full 64-char SHA-256 hash or a short 8-63 char prefix (as seen in garl.ai/r/{short} URLs). " +
      "Returns the shareable receipt URL plus agent name, tier, task description, duration, status and ECDSA signature. " +
      "Use this after garl_verify to grab a paste-ready proof link, or to inspect any public trace from a URL.",
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    inputSchema: {
      type: "object",
      properties: {
        trace_hash: {
          type: "string",
          description: "SHA-256 trace hash or 8+ char prefix",
          minLength: 8,
          maxLength: 64,
        },
      },
      required: ["trace_hash"],
    },
  },
  {
    name: "garl_simulate_score",
    description:
      "Simulate how submitting a trace would affect an agent's trust score WITHOUT writing to the database. " +
      "Returns projected new score, delta, and tier change. Use this for what-if analysis before submitting traces.",
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "UUID of the agent to simulate for" },
        status: { type: "string", enum: ["success", "failure", "partial"], description: "Simulated trace status" },
        duration_ms: { type: "number", description: "Simulated duration in milliseconds" },
        category: { type: "string", enum: ["coding", "research", "sales", "data", "automation", "other"], description: "Task category" },
      },
      required: ["agent_id", "status"],
    },
  },
  {
    name: "garl_get_trust_vector",
    description:
      "Get an agent's multi-dimensional Trust Vector (v0.1). Returns separate signals for identity assurance, " +
      "code-task reliability, security review pass-rate, reversible-action success, payment dispute rate, " +
      "human override rate, and recency-weighted consistency. Prefer this over the legacy single trust_score " +
      "for cross-domain decisions — different domains stress different dimensions.",
    inputSchema: {
      type: "object",
      properties: {
        agent_id: { type: "string", description: "Agent UUID (default: your own agent)" },
      },
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_record_action_receipt",
    description:
      "Submit a GARL Action Receipt v0.1 for any agent action — not just code commits. " +
      "Hits the dedicated /api/v1/receipts endpoint (the v0.1 envelope). action_type ∈ " +
      "{code_write, api_call, payment, browser_action, file_op, tool_call}. side_effect ∈ " +
      "{none, reversible, irreversible}. Caller MUST hash input + output bytes locally; " +
      "this tool only persists the envelope.",
    inputSchema: {
      type: "object",
      properties: {
        action_type: {
          type: "string",
          enum: ["code_write", "api_call", "payment", "browser_action", "file_op", "tool_call"],
        },
        side_effect: {
          type: "string",
          enum: ["none", "reversible", "irreversible"],
          description: "Reversibility class. Be conservative — when in doubt, irreversible",
        },
        runtime: {
          type: "string",
          enum: ["claude-code", "cursor", "copilot", "aider", "codex", "mcp-client", "langchain", "crewai", "llamaindex", "semantic-kernel", "custom"],
          default: "mcp-client",
        },
        protocol: {
          type: "string",
          enum: ["github", "mcp", "a2a", "acp", "ap2", "x402", "raw-http"],
          default: "mcp",
        },
        input_hash:  { type: "string", description: "SHA-256 hex (64 chars) of input canonical JSON" },
        output_hash: { type: "string", description: "SHA-256 hex (64 chars) of output canonical JSON" },
        tool_server: { type: "string" },
        capability_token_hash: { type: "string", description: "SHA-256 hex of the capability token under whose authority this action ran" },
        policy_decision: { type: "string", enum: ["allowed", "denied", "requires_human"] },
        cost: { type: "object", properties: { usd: {type:"number"}, tokens_in: {type:"integer"}, tokens_out: {type:"integer"}, duration_ms: {type:"integer"} } },
        previous_receipt_hash: { type: "string", description: "SHA-256 hex of the prior receipt's output_hash, if chaining" },
        attestations: { type: "array", items: { type: "string" } },
        human_delegate: { type: "string" },
      },
      required: ["action_type", "side_effect", "input_hash", "output_hash"],
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
  {
    name: "garl_issue_capability_token",
    description:
      "Issue a fresh GARL capability token (JWT-shaped + ECDSA-secp256k1 + RFC 6979). " +
      "Tokens are scoped + time-bound + side-effect-classed. The agent presents the resulting " +
      "JWT to a tool server; the tool server verifies offline against the GARL key registry.",
    inputSchema: {
      type: "object",
      properties: {
        scope: { type: "string", description: "What the token authorizes, e.g. 'github:issue:create'" },
        side_effect_class: { type: "string", enum: ["none", "reversible", "irreversible"] },
        expires_in_seconds: { type: "integer", default: 3600 },
        spend_limit_usd: { type: "number" },
        merchant_allowlist: { type: "array", items: { type: "string" } },
        caveats: { type: "array", items: { type: "object" } },
        parent_token_hash: { type: "string", description: "Attenuate from parent (SHA-256 hex of parent JWT)" },
        human_delegate: { type: "string" },
      },
      required: ["scope", "side_effect_class"],
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
  {
    name: "garl_verify_capability_token",
    description:
      "Verify a GARL capability token's signature, expiration, and revocation. Returns valid:true + claims, " +
      "or valid:false + reason.",
    inputSchema: {
      type: "object",
      properties: {
        token: { type: "string", description: "JWT-shaped capability token (header.payload.signature)" },
        check_revocation: { type: "boolean", default: true },
      },
      required: ["token"],
    },
    annotations: { readOnlyHint: true, destructiveHint: false, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_revoke_capability_token",
    description:
      "Revoke a capability token. By default cascades to all attenuated descendants — anyone " +
      "downstream of the revoked token is also marked revoked.",
    inputSchema: {
      type: "object",
      properties: {
        token_hash: { type: "string", description: "SHA-256 hex of the JWT to revoke" },
        reason: { type: "string", default: "manual-revoke" },
        cascade: { type: "boolean", default: true },
      },
      required: ["token_hash"],
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: true, openWorldHint: true },
  },
  {
    name: "garl_evaluate_action",
    description:
      "Capability Gate pre-flight. Given the agent's intended (action_type, side_effect_class), returns " +
      "{decision, reason, score, threshold, dimension, [token]}. If allowed, the response includes a " +
      "freshly-minted capability token already scoped to this action.",
    inputSchema: {
      type: "object",
      properties: {
        action_type: {
          type: "string",
          enum: ["code_write", "api_call", "payment", "browser_action", "file_op", "tool_call"],
        },
        side_effect_class: { type: "string", enum: ["none", "reversible", "irreversible"] },
        target: { type: "string", description: "What the action targets (URL, repo, etc.). Becomes part of token scope." },
        requested_scope: { type: "string", description: "Override the default scope string" },
        expires_in_seconds: { type: "integer", default: 3600 },
        spend_limit_usd: { type: "number" },
        merchant_allowlist: { type: "array", items: { type: "string" } },
        threshold_override: { type: "number", description: "Custom Trust Vector threshold (0..1) if the org has a stricter policy" },
      },
      required: ["action_type", "side_effect_class"],
    },
    annotations: { readOnlyHint: false, destructiveHint: false, idempotentHint: false, openWorldHint: true },
  },
  {
    name: "garl_undo_action",
    description:
      "Trigger UETA §10(b) consumer-undo for a reversible receipt. Returns the recorded undo_payload " +
      "for the caller to actually execute. Refuses if the receipt was classified irreversible.",
    inputSchema: {
      type: "object",
      properties: {
        receipt_id: { type: "string", description: "UUID of the original receipt" },
        reason: { type: "string", default: "consumer-initiated-undo" },
      },
      required: ["receipt_id"],
    },
    annotations: { readOnlyHint: false, destructiveHint: true, idempotentHint: false, openWorldHint: true },
  },
];

// Handles tool call dispatch
async function handleToolCall(name, args) {
  switch (name) {
    case "garl_verify": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured. Set it as an environment variable.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured. Set it as an environment variable.");
      if (!args.task_description) throw new Error("task_description is required.");
      if (!args.status) throw new Error("status is required.");
      if (args.duration_ms === undefined || args.duration_ms === null) throw new Error("duration_ms is required.");
      const body = { agent_id: AGENT_ID, task_description: args.task_description, status: args.status, duration_ms: args.duration_ms, category: args.category || "other", runtime_env: "mcp-client", input_summary: args.input_summary || "", output_summary: args.output_summary || "" };
      if (args.tool_calls) body.tool_calls = args.tool_calls;
      if (args.cost_usd !== undefined) body.cost_usd = args.cost_usd;
      if (args.permissions_used) body.permissions_used = args.permissions_used;
      if (args.security_context) body.security_context = args.security_context;
      const result = await garlFetch("/verify", { method: "POST", body: JSON.stringify(body) });
      const lines = [
        `Trace successfully recorded.`,
        `Trust delta: ${result.trust_delta > 0 ? "+" : ""}${result.trust_delta.toFixed(2)}`,
        `Certificate ID: ${result.id}`,
        `Status: ${result.status}`,
      ];
      if (result.receipt_url) lines.push(`Receipt: ${result.receipt_url}`);
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    case "garl_receipt": {
      if (!args.trace_hash) throw new Error("trace_hash is required.");
      const hash = String(args.trace_hash).trim();
      if (hash.length < 8 || hash.length > 64) {
        throw new Error("trace_hash must be 8-64 characters.");
      }
      const r = await garlFetch(`/verify/${encodeURIComponent(hash)}`, { method: "GET" });
      const parts = [
        `🔐 GARL Receipt ${r.verified ? "✓ verified" : "✗ UNVERIFIED"}`,
        `Agent: ${r.agent_name || "unknown"}${r.agent_tier ? ` (${r.agent_tier})` : ""}${r.agent_trust_score !== null && r.agent_trust_score !== undefined ? ` · trust ${Number(r.agent_trust_score).toFixed(1)}` : ""}`,
        r.task_description ? `Task: ${r.task_description}` : null,
        r.duration_ms ? `Duration: ${r.duration_ms}ms` : null,
        r.status ? `Status: ${r.status}` : null,
        r.receipt_url ? `Receipt: ${r.receipt_url}` : null,
        r.trace_hash ? `Hash: ${r.trace_hash}` : null,
      ].filter(Boolean);
      return { content: [{ type: "text", text: parts.join("\n") }] };
    }

    case "garl_verify_batch": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.traces || !args.traces.length) throw new Error("traces array is required.");
      const traces = args.traces.map(t => ({ agent_id: AGENT_ID, task_description: t.task_description, status: t.status, duration_ms: t.duration_ms, category: t.category || "other", runtime_env: "mcp-client" }));
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

    case "garl_register_agent": {
      if (!args.name) throw new Error("name is required.");
      const regBody = { name: args.name };
      if (args.framework) regBody.framework = args.framework;
      if (args.description) regBody.description = args.description;
      if (args.category) regBody.category = args.category;
      const regResult = await garlFetch("/agents/auto-register", { method: "POST", body: JSON.stringify(regBody) });
      return { content: [{ type: "text", text: [
        `Agent registered successfully!`,
        `Name: ${regResult.name}`,
        `Agent ID: ${regResult.id}`,
        `DID: ${regResult.sovereign_id}`,
        `API Key: ${regResult.api_key}`,
        `Trust Score: ${regResult.trust_score}`,
        ``,
        `Save the API Key — it is shown only once.`,
        `Set GARL_API_KEY="${regResult.api_key}" and GARL_AGENT_ID="${regResult.id}" to start submitting traces.`,
      ].join("\n") }] };
    }

    case "garl_get_feed": {
      const feedLimit = Math.min(Math.max(args.limit || 10, 1), 50);
      const feedResult = await garlFetch(`/feed?limit=${feedLimit}`);
      if (!Array.isArray(feedResult) || feedResult.length === 0) {
        return { content: [{ type: "text", text: "No recent feed entries." }] };
      }
      const feedRows = feedResult.map(e => {
        const delta = e.trust_delta > 0 ? `+${e.trust_delta.toFixed(2)}` : e.trust_delta.toFixed(2);
        return `${e.status === "success" ? "✓" : "✗"} ${e.agent_name || e.agent_id?.slice(0, 8)} — ${e.task_description?.slice(0, 60)} (${delta})`;
      }).join("\n");
      return { content: [{ type: "text", text: `Live Trust Feed:\n\n${feedRows}` }] };
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

    case "garl_trust_gate": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      const trust = await garlFetch(`/trust/verify?agent_id=${encodeURIComponent(args.agent_id)}`);
      const minScore = args.min_score ?? 60;
      const minTier = (args.min_tier || "silver").toLowerCase();
      const agentTier = (trust.certification_tier || "bronze").toLowerCase();
      const passed = parseFloat(trust.trust_score) >= minScore && (TIER_ORDER[agentTier] ?? 0) >= (TIER_ORDER[minTier] ?? 1);
      const nonce = Math.random().toString(36).substring(2, 15) + Date.now().toString(36);
      const expiresAt = new Date(Date.now() + 5 * 60 * 1000).toISOString();
      if (passed) {
        return { content: [{ type: "text", text: [
          `GATE: PASSED`,
          `Agent: ${trust.name}`,
          `Score: ${trust.trust_score.toFixed(1)} (required: ${minScore})`,
          `Tier: ${agentTier} (required: ${minTier})`,
          `Gate Pass: ${nonce}`,
          `Expires: ${expiresAt}`,
          `Delegation: AUTHORIZED`,
        ].join("\n") }] };
      } else {
        return { content: [{ type: "text", text: [
          `GATE: BLOCKED`,
          `Agent: ${trust.name}`,
          `Score: ${trust.trust_score.toFixed(1)} (required: ${minScore})`,
          `Tier: ${agentTier} (required: ${minTier})`,
          `Delegation: DENIED`,
        ].join("\n") }], isError: true };
      }
    }

    case "garl_simulate_score": {
      if (!args.agent_id) throw new Error("agent_id is required.");
      if (!args.status) throw new Error("status is required.");
      const current = await garlFetch(`/trust/verify?agent_id=${encodeURIComponent(args.agent_id)}`);
      const currentScore = parseFloat(current.trust_score);
      const baseDelta = args.status === "success" ? 2.0 : args.status === "failure" ? -3.0 : 0.5;
      let adjustedDelta = baseDelta;
      if (baseDelta > 0 && currentScore > 80) adjustedDelta *= (1.0 - (currentScore - 80) / 40);
      else if (baseDelta < 0 && currentScore < 20) adjustedDelta *= (1.0 - (20 - currentScore) / 40);
      const projectedScore = Math.max(0, Math.min(100, currentScore + adjustedDelta));
      const currentTier = current.certification_tier || "bronze";
      const projectedTier = projectedScore >= 90 ? "enterprise" : projectedScore >= 70 ? "gold" : projectedScore >= 40 ? "silver" : "bronze";
      const tierChange = currentTier !== projectedTier ? `${currentTier} → ${projectedTier}` : "No change";
      return { content: [{ type: "text", text: [
        `Score Simulation (READ-ONLY — no data written)`,
        `Agent: ${current.name}`,
        `Current Score: ${currentScore.toFixed(1)}`,
        `Simulated Trace: ${args.status}${args.duration_ms ? ` (${args.duration_ms}ms)` : ""}`,
        `Projected Delta: ${adjustedDelta > 0 ? "+" : ""}${adjustedDelta.toFixed(2)}`,
        `Projected Score: ${projectedScore.toFixed(1)}`,
        `Tier Change: ${tierChange}`,
        ``,
        `Note: This is an estimate. Actual score calculation uses EMA and additional factors.`,
      ].join("\n") }] };
    }

    case "garl_get_trust_vector": {
      const aid = args.agent_id || AGENT_ID;
      if (!aid) throw new Error("agent_id required (or set GARL_AGENT_ID).");
      const v = await garlFetch(`/agents/${encodeURIComponent(aid)}/trust-vector`);
      const dims = v.dimensions || {};
      const counters = v.counters || {};
      const legacy = v.legacy_composite || {};
      const fmt = (n) => n === null || n === undefined ? "—" : (n * 100).toFixed(1);
      const lines = [
        `Trust Vector ${v.version || "v0.1"} for ${aid}`,
        `Computed: ${v.computed_at || "(unknown)"}`,
        ``,
        `Identity assurance:           ${fmt(dims.agent_identity_assurance)}`,
        `Code-task reliability:        ${fmt(dims.code_task_reliability)}`,
        `Security review pass-rate:    ${fmt(dims.security_review_pass_rate)}`,
        `Reversible-action success:    ${fmt(dims.reversible_action_success)}`,
        `Payment dispute rate:         ${fmt(dims.payment_dispute_rate)}`,
        `Human override rate:          ${fmt(dims.human_override_rate)}`,
        `Recency-weighted consistency: ${fmt(dims.recency_weighted_consistency)}`,
        ``,
        `Verified receipts:            ${counters.verified_receipt_count ?? 0}`,
        `Third-party attestations:     ${counters.third_party_attestation_count ?? 0}`,
        ``,
        `Legacy composite:             ${(legacy.trust_score ?? 0).toFixed(1)}/100 (${legacy.certification_tier || "bronze"})`,
        ``,
        `Note: "—" means not yet measured (e.g., payment_dispute_rate is null until payment receipts land). Treat null as "no data", not zero.`,
      ];
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    case "garl_record_action_receipt": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.action_type) throw new Error("action_type is required.");
      if (!args.side_effect) throw new Error("side_effect is required.");
      if (!args.input_hash) throw new Error("input_hash is required (64 hex chars, SHA-256 of canonical input).");
      if (!args.output_hash) throw new Error("output_hash is required (64 hex chars, SHA-256 of canonical output).");
      const body = {
        agent_id: AGENT_ID,
        runtime: args.runtime || "mcp-client",
        protocol: args.protocol || "mcp",
        action_type: args.action_type,
        input_hash: args.input_hash,
        output_hash: args.output_hash,
        side_effect: args.side_effect,
      };
      if (args.tool_server)            body.tool_server            = args.tool_server;
      if (args.capability_token_hash)  body.capability_token_hash  = args.capability_token_hash;
      if (args.policy_decision)        body.policy_decision        = args.policy_decision;
      if (args.cost)                   body.cost                   = args.cost;
      if (args.previous_receipt_hash)  body.previous_receipt_hash  = args.previous_receipt_hash;
      if (args.attestations)           body.attestations           = args.attestations;
      if (args.human_delegate)         body.human_delegate         = args.human_delegate;

      const env = await garlFetch("/receipts", { method: "POST", body: JSON.stringify(body) });
      const lines = [
        `Action Receipt v0.1 recorded.`,
        `receipt_id:     ${env.receipt_id}`,
        `action_type:    ${env.action_type}`,
        `side_effect:    ${env.side_effect}`,
        `signature:      ${(env.signature || "").slice(0, 16)}…`,
        `verify offline: GET https://api.garl.ai/api/v1/receipts/${env.receipt_id}/cert.json`,
      ];
      if (env.side_effect === "irreversible") {
        lines.push(``, `Note: This action was classified irreversible. No undo primitive will be available.`);
      }
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    case "garl_issue_capability_token": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.scope) throw new Error("scope is required.");
      if (!args.side_effect_class) throw new Error("side_effect_class is required.");
      const body = {
        agent_id: AGENT_ID,
        scope: args.scope,
        side_effect_class: args.side_effect_class,
        expires_in_seconds: args.expires_in_seconds || 3600,
      };
      if (args.spend_limit_usd !== undefined)   body.spend_limit_usd    = args.spend_limit_usd;
      if (args.merchant_allowlist)              body.merchant_allowlist = args.merchant_allowlist;
      if (args.caveats)                         body.caveats            = args.caveats;
      if (args.parent_token_hash)               body.parent_token_hash  = args.parent_token_hash;
      if (args.human_delegate)                  body.human_delegate     = args.human_delegate;

      const out = await garlFetch("/capability/issue", { method: "POST", body: JSON.stringify(body) });
      const lines = [
        `Capability token issued.`,
        `token_hash:  ${out.token_hash}`,
        `expires_at:  ${out.expires_at}`,
        `scope:       ${out.claims.scope}`,
        `side_effect: ${out.claims.side_effect_class}`,
        `token (paste this into the tool server's Authorization header):`,
        out.token,
      ];
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    case "garl_verify_capability_token": {
      if (!args.token) throw new Error("token is required.");
      const body = { token: args.token, check_revocation: args.check_revocation !== false };
      const out = await garlFetch("/capability/verify", { method: "POST", body: JSON.stringify(body) });
      if (out.valid) {
        return { content: [{ type: "text", text: [
          `Capability token VALID.`,
          `subject:     ${out.claims.sub}`,
          `scope:       ${out.claims.scope}`,
          `side_effect: ${out.claims.side_effect_class}`,
          `exp:         ${new Date(out.claims.exp * 1000).toISOString()}`,
        ].join("\n") }] };
      }
      return { content: [{ type: "text", text: `Capability token INVALID — ${out.reason}` }] };
    }

    case "garl_revoke_capability_token": {
      if (!API_KEY) throw new Error("GARL_API_KEY not configured.");
      if (!args.token_hash) throw new Error("token_hash is required.");
      const body = {
        token_hash: args.token_hash,
        reason: args.reason || "manual-revoke",
        cascade: args.cascade !== false,
      };
      const out = await garlFetch("/capability/revoke", { method: "POST", body: JSON.stringify(body) });
      return { content: [{ type: "text", text: `Revoked ${out.count} token(s) (including descendants).` }] };
    }

    case "garl_evaluate_action": {
      if (!AGENT_ID) throw new Error("GARL_AGENT_ID not configured.");
      if (!args.action_type) throw new Error("action_type is required.");
      if (!args.side_effect_class) throw new Error("side_effect_class is required.");
      const body = {
        agent_id: AGENT_ID,
        action_type: args.action_type,
        side_effect_class: args.side_effect_class,
      };
      if (args.target)              body.target              = args.target;
      if (args.requested_scope)     body.requested_scope     = args.requested_scope;
      if (args.expires_in_seconds)  body.expires_in_seconds  = args.expires_in_seconds;
      if (args.spend_limit_usd)     body.spend_limit_usd     = args.spend_limit_usd;
      if (args.merchant_allowlist)  body.merchant_allowlist  = args.merchant_allowlist;
      if (args.threshold_override !== undefined) body.threshold_override = args.threshold_override;

      const out = await garlFetch("/capability/evaluate", { method: "POST", body: JSON.stringify(body) });
      const lines = [
        `Capability Gate decision: ${out.decision.toUpperCase()}`,
        `reason:    ${out.reason}`,
      ];
      if (out.score !== null && out.score !== undefined) {
        lines.push(`score:     ${out.score.toFixed(3)} (dim: ${out.dimension})`);
        lines.push(`threshold: ${out.threshold.toFixed(3)}`);
      }
      if (out.token) {
        lines.push(``, `Capability token (good for ${args.expires_in_seconds || 3600}s):`);
        lines.push(out.token);
      }
      return { content: [{ type: "text", text: lines.join("\n") }] };
    }

    case "garl_undo_action": {
      if (!args.receipt_id) throw new Error("receipt_id is required.");
      const body = { reason: args.reason || "consumer-initiated-undo" };
      try {
        const out = await garlFetch(`/receipts/${encodeURIComponent(args.receipt_id)}/undo`, { method: "POST", body: JSON.stringify(body) });
        const lines = [
          `Undo triggered.`,
          `compensation_id: ${out.compensation_id}`,
          `status:          ${out.status}`,
          out.message,
          ``,
          `Undo payload to execute:`,
          JSON.stringify(out.undo_payload, null, 2),
        ];
        return { content: [{ type: "text", text: lines.join("\n") }] };
      } catch (err) {
        // 409 means policy refused (e.g. irreversible) — surface clearly
        return { content: [{ type: "text", text: `Undo refused: ${err.message}` }], isError: true };
      }
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
}

const server = new Server(
  { name: "garl-protocol", version: "1.4.0" },
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
    console.error("Warning: GARL_API_KEY not set. Write operations will fail. Register at https://garl.ai or use garl_register_agent tool.");
  }
  if (!AGENT_ID) {
    console.error("Warning: GARL_AGENT_ID not set. Trace submissions will fail.");
  }
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((err) => { console.error("Fatal error:", err); process.exit(1); });
