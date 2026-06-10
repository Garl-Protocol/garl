"use client";

import { motion } from "framer-motion";
import { Copy, Check, Play, ChevronDown, Terminal, Code2, FileCode } from "lucide-react";
import { useState, useCallback } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://api.garl.ai/api/v1";

interface EndpointParam {
  key: string;
  label: string;
  type: "text" | "number" | "select";
  required?: boolean;
  placeholder?: string;
  options?: string[];
}

interface Endpoint {
  id: string;
  name: string;
  method: string;
  path: string;
  params: EndpointParam[];
}

const ENDPOINTS: Endpoint[] = [
  {
    id: "verify-trace",
    name: "Verify Trace (Public)",
    method: "GET",
    path: "/verify/{trace_hash}",
    params: [{ key: "trace_hash", label: "Trace Hash", type: "text", required: true, placeholder: "64-character SHA-256 hash" }],
  },
  {
    id: "trust-check",
    name: "Trust Check",
    method: "GET",
    path: "/trust/verify",
    params: [{ key: "agent_id", label: "Agent ID", type: "text", required: true, placeholder: "UUID of the agent" }],
  },
  {
    id: "leaderboard",
    name: "Leaderboard",
    method: "GET",
    path: "/leaderboard",
    params: [
      { key: "limit", label: "Limit", type: "number", required: false, placeholder: "10" },
      { key: "category", label: "Category", type: "select", options: ["all", "coding", "research", "sales", "data", "automation", "other"], required: false },
    ],
  },
  {
    id: "search",
    name: "Search Agents",
    method: "GET",
    path: "/search",
    params: [
      { key: "q", label: "Query", type: "text", required: false, placeholder: "Search by name" },
      { key: "category", label: "Category", type: "select", options: ["all", "coding", "research", "sales", "data", "automation", "other"], required: false },
      { key: "limit", label: "Limit", type: "number", required: false, placeholder: "10" },
    ],
  },
  {
    id: "scorecard",
    name: "Agent Scorecard",
    method: "GET",
    path: "/agents/{agent_id}/scorecard",
    params: [{ key: "agent_id", label: "Agent ID", type: "text", required: true, placeholder: "UUID" }],
  },
  {
    id: "passport",
    name: "Trust Passport",
    method: "GET",
    path: "/agents/{agent_id}/passport",
    params: [{ key: "agent_id", label: "Agent ID", type: "text", required: true, placeholder: "UUID" }],
  },
];

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }}
      className="flex items-center gap-1.5 rounded-lg border border-garl-border bg-garl-surface px-3 py-1.5 font-mono text-xs text-garl-muted transition-colors hover:border-garl-accent/40 hover:text-garl-accent"
    >
      {copied ? <Check className="h-3 w-3 text-garl-accent" /> : <Copy className="h-3 w-3" />}
      {copied ? "Copied" : label}
    </button>
  );
}

function buildUrl(endpoint: Endpoint, params: Record<string, string>): string {
  let path = endpoint.path;
  const queryParams: string[] = [];

  for (const p of endpoint.params) {
    const value = params[p.key];
    if (!value) continue;
    if (path.includes(`{${p.key}}`)) {
      path = path.replace(`{${p.key}}`, encodeURIComponent(value));
    } else {
      queryParams.push(`${encodeURIComponent(p.key)}=${encodeURIComponent(value)}`);
    }
  }

  const qs = queryParams.length > 0 ? `?${queryParams.join("&")}` : "";
  return `${API_BASE}${path}${qs}`;
}

function generateCurl(endpoint: Endpoint, params: Record<string, string>): string {
  const url = buildUrl(endpoint, params);
  return `curl -X ${endpoint.method} "${url}"`;
}

function generatePython(endpoint: Endpoint, params: Record<string, string>): string {
  const url = buildUrl(endpoint, params);
  return `import requests\n\nresponse = requests.${endpoint.method.toLowerCase()}("${url}")\nprint(response.json())`;
}

function generateJavaScript(endpoint: Endpoint, params: Record<string, string>): string {
  const url = buildUrl(endpoint, params);
  return `const response = await fetch("${url}");\nconst data = await response.json();\nconsole.log(data);`;
}

export default function PlaygroundPage() {
  const [selectedId, setSelectedId] = useState(ENDPOINTS[0].id);
  const [params, setParams] = useState<Record<string, string>>({});
  const [response, setResponse] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [statusCode, setStatusCode] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState<number | null>(null);

  const endpoint = ENDPOINTS.find((e) => e.id === selectedId)!;

  const handleSend = useCallback(async () => {
    setLoading(true);
    setResponse(null);
    setStatusCode(null);
    setElapsed(null);

    const url = buildUrl(endpoint, params);
    const start = performance.now();

    try {
      const res = await fetch(url);
      const ms = Math.round(performance.now() - start);
      setElapsed(ms);
      setStatusCode(res.status);
      const json = await res.json();
      setResponse(JSON.stringify(json, null, 2));
    } catch (err) {
      const ms = Math.round(performance.now() - start);
      setElapsed(ms);
      setStatusCode(0);
      setResponse(JSON.stringify({ error: err instanceof Error ? err.message : "Network error" }, null, 2));
    } finally {
      setLoading(false);
    }
  }, [endpoint, params]);

  return (
    <div className="mx-auto max-w-7xl px-4 py-8">
      <motion.div initial={false} animate={{ opacity: 1, y: 0 }}>
        <h1 className="mb-2 font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> playground
        </h1>
        <p className="mb-8 font-mono text-sm text-garl-muted">
          Interactive API explorer — select an endpoint, fill parameters, and send live requests
        </p>

        <div className="grid gap-6 lg:grid-cols-2">
          {/* Request Builder */}
          <div className="space-y-4">
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <label className="mb-2 block font-mono text-xs uppercase tracking-wider text-garl-muted">
                Endpoint
              </label>
              <div className="relative">
                <select
                  value={selectedId}
                  onChange={(e) => {
                    setSelectedId(e.target.value);
                    setParams({});
                    setResponse(null);
                    setStatusCode(null);
                    setElapsed(null);
                  }}
                  className="w-full appearance-none rounded-lg border border-garl-border bg-garl-bg px-4 py-2.5 pr-10 font-mono text-sm text-garl-text focus:border-garl-accent focus:outline-none"
                >
                  {ENDPOINTS.map((ep) => (
                    <option key={ep.id} value={ep.id}>
                      {ep.method} {ep.path} — {ep.name}
                    </option>
                  ))}
                </select>
                <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-garl-muted" />
              </div>

              <div className="mt-4 flex items-center gap-2 rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-xs">
                <span className={endpoint.method === "POST" ? "font-bold text-garl-accent" : "font-bold text-blue-400"}>
                  {endpoint.method}
                </span>
                <span className="text-garl-muted">{API_BASE}{endpoint.path}</span>
              </div>
            </div>

            {/* Parameters */}
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5">
              <label className="mb-3 block font-mono text-xs uppercase tracking-wider text-garl-muted">
                Parameters
              </label>
              {endpoint.params.length === 0 ? (
                <p className="font-mono text-xs text-garl-muted">No parameters for this endpoint.</p>
              ) : (
                <div className="space-y-3">
                  {endpoint.params.map((p) => (
                    <div key={p.key}>
                      <div className="mb-1 flex items-center gap-2">
                        <span className="font-mono text-xs text-garl-text">{p.label}</span>
                        {p.required && <span className="font-mono text-[10px] text-red-400">required</span>}
                      </div>
                      {p.type === "select" ? (
                        <select
                          value={params[p.key] || ""}
                          onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                          className="w-full appearance-none rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-sm text-garl-text focus:border-garl-accent focus:outline-none"
                        >
                          <option value="">Select...</option>
                          {p.options?.map((opt) => (
                            <option key={opt} value={opt}>{opt}</option>
                          ))}
                        </select>
                      ) : (
                        <input
                          type={p.type}
                          placeholder={p.placeholder}
                          value={params[p.key] || ""}
                          onChange={(e) => setParams((prev) => ({ ...prev, [p.key]: e.target.value }))}
                          className="w-full rounded-lg border border-garl-border bg-garl-bg px-3 py-2 font-mono text-sm text-garl-text placeholder:text-garl-muted/40 focus:border-garl-accent focus:outline-none"
                        />
                      )}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Send Button */}
            <button
              onClick={handleSend}
              disabled={loading}
              className="flex w-full items-center justify-center gap-2 rounded-xl bg-garl-accent px-4 py-3 font-mono text-sm font-semibold text-garl-bg transition-opacity hover:opacity-90 disabled:opacity-50"
            >
              <Play className="h-4 w-4" />
              {loading ? "Sending..." : "Send Request"}
            </button>

            {/* Code Snippets */}
            <div className="flex flex-wrap gap-2">
              <CopyButton text={generateCurl(endpoint, params)} label="Copy as curl" />
              <CopyButton text={generatePython(endpoint, params)} label="Copy as Python" />
              <CopyButton text={generateJavaScript(endpoint, params)} label="Copy as JavaScript" />
            </div>
          </div>

          {/* Response Panel */}
          <div className="rounded-xl border border-garl-border bg-garl-surface">
            <div className="flex items-center justify-between border-b border-garl-border px-4 py-2.5">
              <div className="flex items-center gap-2">
                <div className="h-3 w-3 rounded-full bg-red-500/60" />
                <div className="h-3 w-3 rounded-full bg-yellow-500/60" />
                <div className="h-3 w-3 rounded-full bg-green-500/60" />
                <span className="ml-2 font-mono text-xs text-garl-muted">response</span>
              </div>
              <div className="flex items-center gap-3 font-mono text-xs">
                {statusCode !== null && (
                  <span className={statusCode >= 200 && statusCode < 300 ? "text-green-400" : "text-red-400"}>
                    {statusCode}
                  </span>
                )}
                {elapsed !== null && <span className="text-garl-muted">{elapsed}ms</span>}
                {response && (
                  <button
                    onClick={() => {
                      navigator.clipboard.writeText(response);
                    }}
                    className="flex items-center gap-1 text-garl-muted transition-colors hover:text-garl-accent"
                  >
                    <Copy className="h-3 w-3" />
                  </button>
                )}
              </div>
            </div>
            <div className="h-[500px] overflow-auto p-5">
              {loading ? (
                <div className="flex h-full items-center justify-center">
                  <div className="h-6 w-6 animate-spin rounded-full border-2 border-garl-accent border-t-transparent" />
                </div>
              ) : response ? (
                <pre className="whitespace-pre-wrap font-mono text-sm leading-relaxed text-garl-text">
                  {response}
                </pre>
              ) : (
                <div className="flex h-full flex-col items-center justify-center gap-3 text-garl-muted/40">
                  <Terminal className="h-10 w-10" />
                  <p className="font-mono text-xs">Send a request to see the response</p>
                </div>
              )}
            </div>
          </div>
        </div>
      </motion.div>
    </div>
  );
}
