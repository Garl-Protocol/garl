# Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        GARL Protocol                            │
│      Cryptographic verification for AI agent actions             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │
│  │  Python   │   │   JS     │   │   MCP    │   │   A2A    │    │
│  │   SDK     │   │   SDK    │   │  Server  │   │ JSON-RPC │    │
│  └────┬─────┘   └────┬─────┘   └────┬─────┘   └────┬─────┘    │
│       │              │              │              │            │
│       └──────────────┴──────────────┴──────────────┘            │
│                          │                                      │
│                    ┌─────▼─────┐                                │
│                    │  FastAPI  │  32 REST + A2A JSON-RPC         │
│                    │  Backend  │  Rate Limited + CORS            │
│                    └─────┬─────┘                                │
│                          │                                      │
│          ┌───────────────┼───────────────┐                      │
│          │               │               │                      │
│    ┌─────▼─────┐  ┌─────▼─────┐  ┌─────▼─────┐               │
│    │ Reputation│  │  Signing  │  │  Webhook  │               │
│    │  Engine   │  │  Engine   │  │  Engine   │               │
│    │           │  │           │  │           │               │
│    │ • 5D EMA  │  │ • SHA-256 │  │ • HMAC    │               │
│    │ • Anomaly │  │ • ECDSA   │  │ • Retry   │               │
│    │ • Decay   │  │ • secp256k│  │ • CRUD    │               │
│    │ • Tiers   │  │           │  │           │               │
│    └─────┬─────┘  └─────┬─────┘  └─────┬─────┘               │
│          │               │               │                      │
│          └───────────────┼───────────────┘                      │
│                          │                                      │
│                    ┌─────▼─────┐                                │
│                    │ Supabase  │  PostgreSQL + RLS              │
│                    │           │  Immutable Triggers            │
│                    │ • agents  │  Row Level Security            │
│                    │ • traces  │                                │
│                    │ • rep_hist│                                │
│                    │ • webhook │                                │
│                    │ • endorse │                                │
│                    └───────────┘                                │
│                                                                 │
├─────────────────────────────────────────────────────────────────┤
│  Frontend: Next.js 14 + Tailwind CSS                            │
│  9 pages: Home, Dashboard, Leaderboard, Playground,              │
│  Compare, Compliance, Docs, Privacy, Simulator                   │
└─────────────────────────────────────────────────────────────────┘
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 14 + Tailwind CSS + Framer Motion |
| Database | Supabase (PostgreSQL) with RLS |
| Cryptography | ECDSA secp256k1 + SHA-256 |
| SDKs | Python (sync/async) + JavaScript |
| MCP | Node.js MCP Server (12 named tools + batch variants) |
| Containers | Docker + Docker Compose |

## Project Structure

```
garl/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/routes.py    # 32 REST endpoints
│   │   ├── api/mcp.py       # Remote MCP endpoint
│   │   ├── core/            # Config, signing, Supabase client
│   │   ├── models/          # Pydantic schemas
│   │   └── services/        # Business logic (agents, traces, reputation)
│   ├── tests/               # Pytest suite
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                # Next.js 14 application
│   ├── src/app/             # 9 routes
│   ├── src/lib/             # API client, utilities
│   └── Dockerfile
├── sdks/
│   ├── python/garl.py       # Python SDK (sync + async)
│   └── javascript/garl.js   # JavaScript SDK
├── integrations/
│   ├── mcp-server/          # MCP Server (12 named tools + batch variants)
│   ├── github-action/       # GitHub Action Trust Gate
│   └── langchain/           # LangChain Callback Handler
├── docs/                    # Documentation
├── supabase/
│   ├── schema.sql           # Database schema (5 tables)
│   └── migrations/          # Migration files
├── docker-compose.yml
└── README.md
```

## Core Pillars

### 5-Dimensional EMA Scoring

Every agent is evaluated across five independent dimensions using Exponential Moving Average — recent performance weighs more than history.

| Dimension | Weight | Measures |
|-----------|--------|----------|
| **Reliability** | 30% | Success/failure rate with streak bonus |
| **Security** | 20% | Permission discipline, tool safety, PII protection |
| **Speed** | 15% | Duration vs category benchmark |
| **Cost Efficiency** | 10% | Cost vs category benchmark |
| **Consistency** | 25% | Low variance in outcomes |

### Sovereign Identity (DID)

Each agent receives a Decentralized Identifier (`did:garl:<uuid>`) at registration. Combined with ECDSA-secp256k1 cryptographic certificates, every trace carries tamper-proof proof-of-completion.

### Immutable Ledger

PostgreSQL triggers prevent any modification or deletion of execution traces and reputation history. Every record is permanent, auditable, and cryptographically verifiable.

### Certification Tiers

| Tier | Score Range | Requirements |
|------|------------|--------------|
| **Bronze** | 0–40 | Starter / Unverified |
| **Silver** | 40–70 | Trusted / Active |
| **Gold** | 70–90 | High Performance / Verified |
| **Enterprise** | 90+ | Zero Anomaly / SLA Compliant |
