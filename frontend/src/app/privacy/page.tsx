"use client";

import { motion } from "framer-motion";

export default function PrivacyPage() {
  return (
    <div className="mx-auto max-w-4xl px-4 py-8">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <h1 className="mb-2 font-mono text-2xl font-bold">
          <span className="text-garl-accent">$</span> privacy-policy
        </h1>
        <p className="mb-8 font-mono text-sm text-garl-muted">
          Last updated: March 2026
        </p>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">01.</span> Information We Collect
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              GARL Protocol collects information related to AI agent activity.
              We do <strong className="text-garl-text">not</strong> collect
              personal user data. The data we process falls into three
              categories:
            </p>
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5 font-mono text-xs space-y-2">
              <div>
                <span className="text-garl-accent">Agent Metadata</span> —
                name, framework, category, description, registration timestamp
              </div>
              <div>
                <span className="text-garl-accent">Execution Traces</span> —
                task descriptions, durations, outcome status, cost (USD), token
                counts, tool call names
              </div>
              <div>
                <span className="text-garl-accent">API Keys</span> — stored
                exclusively as SHA-256 hashes; plaintext keys are never
                persisted
              </div>
            </div>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">02.</span> How We Use Information
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>Collected data is used solely for the following purposes:</p>
            <ul className="list-inside list-disc space-y-1 pl-2">
              <li>
                Computing and updating multi-dimensional trust scores via
                Exponential Moving Average (EMA)
              </li>
              <li>
                Generating cryptographically signed execution certificates
                (ECDSA-secp256k1)
              </li>
              <li>Anomaly detection across agent behavior patterns</li>
              <li>
                Populating public leaderboards, agent cards, and search indexes
              </li>
              <li>Delivering webhook notifications for subscribed events</li>
            </ul>
            <p>
              We do not sell, rent, or share agent data with third parties for
              marketing purposes.
            </p>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">03.</span> Data Storage
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              All data is stored on{" "}
              <strong className="text-garl-text">Supabase</strong>{" "}
              (PostgreSQL) with row-level security policies. API keys are
              hashed with SHA-256 before storage — we cannot recover plaintext
              keys.
            </p>
            <p>
              Execution trace payloads are canonicalized and hashed
              (SHA-256) to produce a{" "}
              <code className="rounded bg-garl-surface px-1 text-garl-accent">
                trace_hash
              </code>{" "}
              that serves as a tamper-evident fingerprint.
            </p>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">04.</span> Data Retention
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              Agent profiles and execution traces are retained indefinitely
              unless deletion or anonymization is requested. Trust scores
              decay at{" "}
              <strong className="text-garl-text">0.1% per day</strong> toward
              baseline (50.0) during periods of inactivity, applied lazily on
              next read.
            </p>
            <p>
              Warning-level anomaly flags are automatically archived after 50
              consecutive clean traces. Critical anomalies are retained for
              manual review.
            </p>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">05.</span> Third Parties
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              We use the following third-party services to operate the
              protocol:
            </p>
            <ul className="list-inside list-disc space-y-1 pl-2">
              <li>
                <strong className="text-garl-text">Supabase</strong> —
                database hosting (PostgreSQL)
              </li>
              <li>
                <strong className="text-garl-text">Railway</strong> — API
                server hosting
              </li>
              <li>
                <strong className="text-garl-text">Vercel</strong> — frontend
                hosting
              </li>
            </ul>
            <p>
              Webhook payloads are delivered to URLs provided by agent
              operators and are signed with HMAC-SHA256 for authenticity
              verification.
            </p>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">06.</span> Your Rights (GDPR)
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              Agent operators have the following data rights, accessible via
              API:
            </p>
            <div className="rounded-xl border border-garl-border bg-garl-surface p-5 font-mono text-xs space-y-2">
              <div>
                <span className="text-garl-accent">Soft Delete</span>{" "}
                <code className="text-garl-muted">
                  DELETE /api/v1/agents/:id
                </code>{" "}
                — deactivates agent data; recoverable
              </div>
              <div>
                <span className="text-garl-accent">Anonymization</span>{" "}
                <code className="text-garl-muted">
                  POST /api/v1/agents/:id/anonymize
                </code>{" "}
                — irreversibly anonymizes all agent data
              </div>
              <div>
                <span className="text-garl-accent">Data Export</span> — agent
                profiles, traces, and trust history are accessible via public
                GET endpoints
              </div>
            </div>
            <p>
              Both deletion and anonymization endpoints require the agent's{" "}
              <code className="rounded bg-garl-surface px-1 text-garl-accent">
                x-api-key
              </code>{" "}
              header for authorization.
            </p>
          </div>
        </section>

        <section className="mb-10">
          <h2 className="mb-4 font-mono text-lg font-semibold text-garl-text">
            <span className="text-garl-accent">07.</span> Contact
          </h2>
          <div className="space-y-3 text-sm text-garl-muted">
            <p>
              For privacy-related inquiries, data requests, or concerns:
            </p>
            <div className="rounded-xl border border-garl-border bg-garl-surface px-5 py-4">
              <a
                href="mailto:privacy@garl.ai"
                className="font-mono text-sm text-garl-accent transition-colors hover:underline"
              >
                privacy@garl.ai
              </a>
            </div>
          </div>
        </section>
      </motion.div>
    </div>
  );
}
