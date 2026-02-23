#!/usr/bin/env python3
"""
GARL Protocol - Mock Run Script
Simulates 100 agents interacting and generating traces to populate the UI.

Usage:
    python scripts/mock_run.py

Requires GARL backend to be running at http://localhost:8000
"""

import random
import time
import httpx
import sys

API_BASE = "http://localhost:8000/api/v1"

AGENT_TEMPLATES = [
    # (name, framework, category, description)
    ("CodePilot-{}", "langchain", "coding", "Autonomous code generation and review agent"),
    ("ResearchBot-{}", "crewai", "research", "Deep research and summarization agent"),
    ("SalesForge-{}", "autogpt", "sales", "Outreach automation and lead qualification"),
    ("DataMiner-{}", "langchain", "data", "Data extraction, ETL, and analysis agent"),
    ("AutoFlow-{}", "crewai", "automation", "Workflow automation and task orchestration"),
    ("DebugHero-{}", "langchain", "coding", "Automated debugging and fix suggestion agent"),
    ("InsightAI-{}", "autogpt", "research", "Market intelligence and trend analysis"),
    ("PipelineBot-{}", "custom", "data", "CI/CD pipeline management agent"),
    ("DocWriter-{}", "langchain", "coding", "Documentation generation agent"),
    ("LeadGen-{}", "crewai", "sales", "B2B lead generation and scoring agent"),
]

TOOL_NAMES = [
    "web_search", "file_read", "file_write", "code_execute", "sql_query",
    "api_call", "browser_navigate", "screenshot", "pdf_parse", "email_send",
    "slack_post", "github_pr", "docker_run", "llm_call", "vector_search",
]

RUNTIME_ENVS = [
    "python-3.12-linux", "python-3.11-macos", "node-20-linux",
    "docker-python", "lambda-python", "vercel-edge",
]

TASKS = {
    "coding": [
        "Refactored authentication module with JWT support",
        "Fixed race condition in WebSocket handler",
        "Generated REST API from OpenAPI spec",
        "Migrated database schema from v2 to v3",
        "Implemented rate limiting middleware",
        "Code review for PR #1847 - payment processing",
        "Generated unit tests for user service",
        "Optimized SQL queries reducing latency by 40%",
    ],
    "research": [
        "Analyzed Q4 market trends in AI infrastructure",
        "Compiled competitive landscape report",
        "Summarized 50 academic papers on transformer architectures",
        "Generated investment thesis for Series B evaluation",
        "Conducted patent landscape analysis",
        "Customer sentiment analysis from 10K reviews",
    ],
    "sales": [
        "Qualified 200 leads from LinkedIn outreach",
        "Generated personalized email sequences for 50 accounts",
        "Created proposal deck for enterprise client",
        "Analyzed CRM data for churn prediction",
        "Automated follow-up sequences for pipeline",
    ],
    "data": [
        "ETL pipeline: ingested 1M rows from S3 to Snowflake",
        "Data quality audit on customer records",
        "Built real-time analytics dashboard",
        "Migrated data warehouse schema",
        "Anomaly detection on transaction data",
    ],
    "automation": [
        "Orchestrated multi-step deployment pipeline",
        "Automated invoice processing workflow",
        "Set up monitoring alerts for 15 services",
        "Provisioned development environments",
        "Automated compliance reporting",
    ],
}


def create_agents(count: int = 100) -> list[dict]:
    """Register agents and return their data with API keys."""
    agents = []
    print(f"\n{'='*60}")
    print(f"  GARL Protocol Mock Run - Registering {count} Agents")
    print(f"{'='*60}\n")

    for i in range(count):
        template = AGENT_TEMPLATES[i % len(AGENT_TEMPLATES)]
        name = template[0].format(i + 1)

        payload = {
            "name": name,
            "framework": template[1],
            "category": template[2],
            "description": template[3],
        }

        try:
            resp = httpx.post(f"{API_BASE}/agents", json=payload, timeout=10)
            resp.raise_for_status()
            agent = resp.json()
            agents.append(agent)
            if (i + 1) % 10 == 0:
                print(f"  Registered {i + 1}/{count} agents...")
        except httpx.HTTPError as e:
            print(f"  Failed to register {name}: {e}")

    print(f"\n  {len(agents)} agents registered successfully.\n")
    return agents


def simulate_traces(agents: list[dict], traces_per_agent: int = 15):
    """Submit traces for each agent."""
    total = len(agents) * traces_per_agent
    completed = 0

    print(f"{'='*60}")
    print(f"  Generating ~{total} Execution Traces")
    print(f"{'='*60}\n")

    for agent in agents:
        category = agent.get("category", "other")
        tasks = TASKS.get(category, TASKS["automation"])

        # Each agent has a "reliability profile"
        reliability = random.uniform(0.4, 0.95)

        for _ in range(traces_per_agent):
            roll = random.random()
            if roll < reliability:
                status = "success"
            elif roll < reliability + (1 - reliability) * 0.3:
                status = "partial"
            else:
                status = "failure"

            task = random.choice(tasks)
            duration = random.randint(200, 30000)

            num_tools = random.randint(1, 5)
            tool_calls = [
                {
                    "name": random.choice(TOOL_NAMES),
                    "duration_ms": random.randint(50, duration // max(num_tools, 1)),
                }
                for _ in range(num_tools)
            ]

            cost = round(random.uniform(0.001, 0.25), 5) if random.random() > 0.3 else 0

            payload = {
                "agent_id": agent["id"],
                "task_description": task,
                "status": status,
                "duration_ms": duration,
                "category": category,
                "input_summary": f"Input for: {task[:50]}",
                "output_summary": f"Output: {'completed' if status == 'success' else 'error/partial'}",
                "runtime_env": random.choice(RUNTIME_ENVS),
                "tool_calls": tool_calls,
                "cost_usd": cost,
            }

            try:
                resp = httpx.post(
                    f"{API_BASE}/verify",
                    json=payload,
                    headers={"x-api-key": agent["api_key"]},
                    timeout=10,
                )
                resp.raise_for_status()
                completed += 1

                if completed % 100 == 0:
                    print(f"  Submitted {completed}/{total} traces...")
            except httpx.HTTPError as e:
                print(f"  Trace failed for {agent['name']}: {e}")

            time.sleep(0.02)  # gentle pacing

    print(f"\n  {completed}/{total} traces submitted successfully.\n")


def print_leaderboard():
    """Fetch and display the leaderboard."""
    print(f"{'='*60}")
    print(f"  GARL Leaderboard - Top 15 Agents")
    print(f"{'='*60}\n")

    try:
        resp = httpx.get(f"{API_BASE}/leaderboard?limit=15", timeout=10)
        resp.raise_for_status()
        entries = resp.json()

        print(f"  {'Rank':<6}{'Agent':<25}{'Score':<10}{'Traces':<10}{'Success%':<10}")
        print(f"  {'-'*55}")

        for entry in entries:
            print(
                f"  {entry['rank']:<6}"
                f"{entry['name'][:24]:<25}"
                f"{entry['trust_score']:<10}"
                f"{entry['total_traces']:<10}"
                f"{entry['success_rate']:<10}"
            )
    except httpx.HTTPError as e:
        print(f"  Failed to fetch leaderboard: {e}")

    print()


def main():
    print("\n" + "=" * 60)
    print("  GARL PROTOCOL - Mock Simulation Runner")
    print("=" * 60)

    # Check if backend is running
    try:
        resp = httpx.get(f"http://localhost:8000/health", timeout=5)
        resp.raise_for_status()
        print("  Backend is running.\n")
    except httpx.HTTPError:
        print("  ERROR: Backend not running at http://localhost:8000")
        print("  Start it with: cd backend && uvicorn app.main:app --reload")
        sys.exit(1)

    agent_count = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    traces_per = int(sys.argv[2]) if len(sys.argv) > 2 else 15

    agents = create_agents(agent_count)
    if not agents:
        print("  No agents created. Exiting.")
        sys.exit(1)

    simulate_traces(agents, traces_per)
    print_leaderboard()

    stats_resp = httpx.get(f"{API_BASE}/stats", timeout=10)
    if stats_resp.status_code == 200:
        stats = stats_resp.json()
        print(f"  Protocol Stats:")
        print(f"    Total Agents:  {stats['total_agents']}")
        print(f"    Total Traces:  {stats['total_traces']}")
        if stats.get("top_agent"):
            print(f"    Top Agent:     {stats['top_agent']['name']} ({stats['top_agent']['trust_score']})")

    print(f"\n  Mock run complete. Open http://localhost:3000 to view the dashboard.\n")


if __name__ == "__main__":
    main()
