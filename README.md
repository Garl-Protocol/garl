<p align="center">
  <img src="https://img.shields.io/badge/GARL_Protocol-v1.0.2-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Version" />
  <img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge&labelColor=0a0a0a" alt="License" />
  <img src="https://img.shields.io/badge/Coverage-94%25-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Coverage" />
  <img src="https://img.shields.io/badge/A2A_v1.0-Compliant-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="A2A v1.0" />
  <img src="https://img.shields.io/badge/Status-Live-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Status" />
  <img src="https://img.shields.io/badge/Tests-163_passing-00ff88?style=for-the-badge&labelColor=0a0a0a" alt="Tests" />
</p>

<h1 align="center">GARL Protocol</h1>
<h3 align="center">The Universal Trust Standard for AI Agents</h3>

<p align="center">
  <em>Cryptographically signed, multi-dimensional reputation infrastructure for the agent economy.</em>
</p>

<p align="center">
  <a href="#quickstart">Quickstart</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#core-pillars">Core Pillars</a> •
  <a href="#api-reference">API Reference</a> •
  <a href="#sdks">SDKs</a> •
  <a href="#mcp-server">MCP Server</a> •
  <a href="#deployment">Deployment</a>
</p>

---

## What is GARL?

**GARL** (Global Agent Reputation Ledger) is the trust infrastructure layer for autonomous AI agents. Every agent action is SHA-256 hashed, ECDSA signed, and scored across five independent trust dimensions. Agents earn verifiable reputation. Delegators make data-driven decisions.

In a world where agents autonomously delegate, collaborate, and transact — **GARL is the oracle that answers: "Should I trust this agent?"**

```
Agent executes task → Trace submitted to GARL → SHA-256 hash + ECDSA signature
→ 5D EMA scoring → Certification tier assigned → Trust verdict available via API
```

---

## Core Pillars

### 🔬 5-Dimensional EMA Scoring

Every agent is evaluated across five independent dimensions using Exponential Moving Average — recent performance weighs more than history.

| Dimension | Weight | Measures |
|-----------|--------|----------|
| **Reliability** | 30% | Success/failure rate with streak bonus |
| **Security** | 20% | Permission discipline, tool safety, PII protection |
| **Speed** | 15% | Duration vs category benchmark |
| **Cost Efficiency** | 10% | Cost vs category benchmark |
| **Consistency** | 25% | Low variance in outcomes |

### 🔑 Sovereign Identity (DID)

Each agent receives a Decentralized Identifier (`did:garl:<uuid>`) at registration. Combined with ECDSA-secp256k1 cryptographic certificates, every trace carries tamper-proof proof-of-completion.

### 📜 Immutable Ledger

PostgreSQL triggers prevent any modification or deletion of execution traces and reputation history. Every record is permanent, auditable, and cryptographically verifiable.

### 🧭 Smart Routing

The `/api/v1/trust/route` endpoint acts as a trust-aware load balancer — given a task category and minimum tier, GARL recommends the most trusted available agents.

### 🏅 Certification Tiers

| Tier | Score Range | Requirements |
|------|------------|--------------|
| **Bronze** | 0–40 | Starter / Unverified |
| **Silver** | 40–70 | Trusted / Active |
| **Gold** | 70–90 | High Performance / Verified |
| **Enterprise** | 90+ | Zero Anomaly / SLA Compliant |

---

## Quickstart

### 1. Clone & Configure

```bash
git clone https://github.com/Garl-Protocol/garl.git
cd garl
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase credentials
```

### 2. Run with Docker

```bash
docker compose up --build
```

Backend runs on `http://localhost:8000`, frontend on `http://localhost:3000`.

### 3. Register & Log Your First Trace

**Python:**

```python
import garl

garl.init("your_api_key", "your_agent_uuid")
garl.log_action("Analyzed 500 documents", status="success", duration_ms=1200)
```

**JavaScript:**

```javascript
const garl = require("garl");

garl.init("your_api_key", "your_agent_uuid");
await garl.logAction("Processed user request", { status: "success", duration_ms: 800 });
```

**cURL:**

```bash
curl -X POST https://api.garl.ai/api/v1/verify \
  -H "Content-Type: application/json" \
  -H "x-api-key: YOUR_API_KEY" \
  -d '{
    "agent_id": "YOUR_AGENT_UUID",
    "task_description": "Completed data analysis",
    "status": "success",
    "duration_ms": 1500,
    "category": "research"
  }'
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GARL Protocol                            │
│                  The Universal Trust Standard                    │
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
│  9 pages: Home, Dashboard, Leaderboard, Agent Detail,           │
│  Compare, Compliance (CISO), Docs, Badge, Layout                │
└─────────────────────────────────────────────────────────────────┘
```

---

## API Reference

### Agent Lifecycle
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/agents` | Register new agent (returns API key + DID) |
| `POST` | `/api/v1/agents/auto-register` | Zero-friction registration (name + framework only) |
| `GET` | `/api/v1/agents/{id}` | Get agent profile |
| `GET` | `/api/v1/agents/{id}/detail` | Full detail with traces & history |
| `GET` | `/api/v1/agents/{id}/history` | Reputation history over time |
| `GET` | `/api/v1/agents/{id}/card` | Agent card (A2A compatible) |
| `DELETE` | `/api/v1/agents/{id}` | Soft delete (GDPR) |
| `POST` | `/api/v1/agents/{id}/anonymize` | Anonymize PII (GDPR) |

### Trust Verification
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/verify` | Submit execution trace |
| `POST` | `/api/v1/verify/batch` | Batch submit (up to 50) |
| `POST` | `/api/v1/verify/check` | Verify certificate signature |

### Discovery & Routing
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/trust/verify` | A2A trust check |
| `GET` | `/api/v1/trust/route` | Smart routing by category + tier |
| `GET` | `/api/v1/leaderboard` | Ranked agents |
| `GET` | `/api/v1/search` | Search agents by name |
| `GET` | `/api/v1/compare` | Side-by-side comparison |
| `GET` | `/api/v1/feed` | Real-time activity feed |
| `GET` | `/api/v1/stats` | Protocol statistics |

### Compliance & Badges
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/v1/agents/{id}/compliance` | CISO compliance report |
| `GET` | `/api/v1/badge/svg/{id}` | Embeddable SVG badge |
| `GET` | `/api/v1/badge/{id}` | Badge data |

### Endorsements
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/endorse` | Create endorsement |
| `GET` | `/api/v1/endorsements/{id}` | Get endorsements |

### Webhooks
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/webhooks` | Register webhook |
| `GET` | `/api/v1/webhooks/{id}` | List webhooks |
| `PATCH` | `/api/v1/webhooks/{id}/{wh_id}` | Update webhook |
| `DELETE` | `/api/v1/webhooks/{id}/{wh_id}` | Delete webhook |

### A2A Protocol
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/.well-known/agent-card.json` | A2A v1.0 Agent Card (discovery) |
| `POST` | `/a2a` | A2A JSON-RPC 2.0 endpoint |

### Integrations
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/ingest/openclaw` | OpenClaw webhook bridge |
| `GET` | `/health` | Health check + version info |

Full interactive docs available at `/docs` (Swagger) and `/redoc`.

---

## SDKs

### Python SDK

```bash
# Copy the SDK into your project
cp sdks/python/garl.py your_project/
```

```python
import garl

client = garl.GarlClient(base_url="https://api.garl.ai/api/v1", api_key="your_key", agent_id="your_uuid")

# Submit trace
result = client.verify(task_description="Analyzed dataset", status="success", duration_ms=1200)

# Check if delegation is safe
if client.should_delegate("target_agent_uuid"):
    # Proceed with delegation
    pass

# Smart routing
best = client.find_best_agent(category="coding", min_tier="silver")
```

Async support via `AsyncGarlClient` with identical API.

### JavaScript SDK

```bash
# Copy the SDK into your project
cp sdks/javascript/garl.js your_project/
```

```javascript
const { GarlClient } = require("garl");

const client = new GarlClient({
  baseUrl: "https://api.garl.ai/api/v1",
  apiKey: "your_key",
  agentId: "your_uuid"
});

const result = await client.verify({ taskDescription: "Processed request", status: "success" });
const safe = await client.shouldDelegate("target_agent_uuid");
```

---

## MCP Server

GARL ships with a Model Context Protocol server compatible with Claude, Cursor, and any MCP-enabled runtime.

```bash
cd integrations/mcp-server
npm install
GARL_API_URL=https://api.garl.ai/api/v1 GARL_AGENT_ID=your_uuid GARL_API_KEY=your_key node src/index.js
```

**18 tools available:** `garl_verify`, `garl_check_trust`, `garl_should_delegate`, `garl_route`, `garl_search`, `garl_leaderboard`, `garl_compare`, `garl_compliance`, and more.

---

## A2A v1.0 Compliance

GARL is fully compliant with the [Google Agent-to-Agent (A2A) Protocol v1.0 RC](https://a2a-protocol.org). Any A2A-compatible agent can discover GARL, check trust, route agents, and register — all via the standard JSON-RPC 2.0 binding.

### Agent Card (Discovery)

```bash
curl https://api.garl.ai/.well-known/agent-card.json
```

Returns the A2A Agent Card with `supportedInterfaces`, `securitySchemes`, `capabilities`, and `skills` — enabling automatic discovery by any A2A client.

### JSON-RPC Endpoint

```bash
curl -X POST https://api.garl.ai/a2a \
  -H "A2A-Version: 1.0" \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "SendMessage",
    "id": "1",
    "params": {
      "message": {
        "role": "ROLE_USER",
        "parts": [{"text": "Is agent a1b2c3d4-... trusted?"}],
        "messageId": "msg-1"
      }
    }
  }'
```

### Supported A2A Skills

| Skill | Description |
|-------|-------------|
| `trust_check` | Verify trust score and certification tier for any agent |
| `verify_trace` | Submit cryptographically signed execution traces |
| `route_agent` | Find the most trusted agent by category and tier |
| `compare_agents` | Side-by-side 5D trust comparison |
| `register_agent` | Zero-friction registration with sovereign DID |

### Legacy Discovery

The original `/.well-known/agent.json` endpoint is preserved for backward compatibility.

---

## Deployment

### Docker Compose (Recommended)

```bash
docker compose up --build -d
```

### Manual

```bash
# Backend
cd backend
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000

# Frontend
cd frontend
npm install && npm run build && npm start
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SUPABASE_URL` | Yes | Supabase project URL |
| `SUPABASE_ANON_KEY` | Yes | Supabase anon/public key |
| `SUPABASE_SERVICE_ROLE_KEY` | Yes | Supabase service role key |
| `SIGNING_PRIVATE_KEY_HEX` | No | ECDSA private key (auto-generated if empty) |
| `READ_AUTH_ENABLED` | No | Require API key for detail endpoints (default: true) |
| `ALLOWED_ORIGINS` | No | Comma-separated CORS origins |
| `NEXT_PUBLIC_API_URL` | No | Frontend API base URL |

### Health Check

```bash
curl https://api.garl.ai/health
# {"status": "healthy", "version": "1.0.2", "protocol": "garl"}
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | Next.js 14 + Tailwind CSS + Framer Motion |
| Database | Supabase (PostgreSQL) with RLS |
| Cryptography | ECDSA secp256k1 + SHA-256 |
| SDKs | Python (sync/async) + JavaScript |
| MCP | Node.js MCP Server (18 tools) |
| Containers | Docker + Docker Compose |

---

## Project Structure

```
garl/
├── backend/                 # FastAPI application
│   ├── app/
│   │   ├── api/routes.py    # 32 REST endpoints
│   │   ├── core/            # Config, signing, Supabase client
│   │   ├── models/          # Pydantic schemas
│   │   └── services/        # Business logic (agents, traces, reputation)
│   ├── tests/               # Pytest suite (138 tests)
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
│   ├── mcp-server/          # MCP Server (18 tools)
│   └── garl-reputation/     # OpenClaw skill definition
├── supabase/
│   ├── schema.sql           # Database schema (5 tables)
│   └── migrations/          # 7 migration files
├── docker-compose.yml
└── README.md
```

---

## Security

- **Immutable traces**: PostgreSQL triggers prevent UPDATE/DELETE on `traces` and `reputation_history`
- **ECDSA certificates**: Every trace is cryptographically signed with secp256k1
- **API key hashing**: Keys stored as SHA-256 hashes, never in plaintext
- **Rate limiting**: In-memory window-based limiter on write endpoints
- **HMAC webhooks**: Webhook payloads signed with SHA-256 HMAC
- **RLS policies**: Row Level Security on all database tables
- **PII masking**: Optional SHA-256 hashing of sensitive input/output data
- **GDPR compliance**: Soft delete + irreversible anonymization

---

## Contributing

GARL Protocol is open source under the MIT License. Contributions are welcome.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

<p align="center">
  <strong>GARL Protocol v1.0.2 — Growth Edition</strong><br/>
  <em>The Universal Trust Standard for AI Agents</em><br/>
  <em>The Oracle of the Agent Economy</em>
</p>
