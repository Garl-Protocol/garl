#!/usr/bin/env python3
"""
GARL Protocol v1.0 — Agent seed script.

Creates 50 curated agents from known AI frameworks and
sends 5-15 random traces for each to establish initial scores.
"""
import random
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx

import os

BASE_URL = os.environ.get("GARL_BASE_URL", "http://localhost:8000")

# 50 curated agents: (name, framework, category)
AGENTS = [
    # 10 LangChain agents
    ("LangChain Code Reviewer", "langchain", "coding"),
    ("LangChain Research Assistant", "langchain", "research"),
    ("LangChain Data Pipeline Agent", "langchain", "data"),
    ("LangChain Automation Orchestrator", "langchain", "automation"),
    ("LangChain Sales Outreach Bot", "langchain", "sales"),
    ("LangChain Bug Fixer", "langchain", "coding"),
    ("LangChain Documentation Generator", "langchain", "coding"),
    ("LangChain API Integrator", "langchain", "coding"),
    ("LangChain ETL Specialist", "langchain", "data"),
    ("LangChain Workflow Designer", "langchain", "automation"),
    # 8 CrewAI agents
    ("CrewAI Sales Orchestrator", "crewai", "sales"),
    ("CrewAI Research Analyst", "crewai", "research"),
    ("CrewAI Task Automator", "crewai", "automation"),
    ("CrewAI Data Scientist", "crewai", "data"),
    ("CrewAI Code Assistant", "crewai", "coding"),
    ("CrewAI Lead Qualifier", "crewai", "sales"),
    ("CrewAI Report Writer", "crewai", "research"),
    ("CrewAI Pipeline Manager", "crewai", "automation"),
    # 8 AutoGPT agents
    ("AutoGPT Coding Agent", "autogpt", "coding"),
    ("AutoGPT Research Agent", "autogpt", "research"),
    ("AutoGPT Automation Agent", "autogpt", "automation"),
    ("AutoGPT Data Agent", "autogpt", "data"),
    ("AutoGPT Task Runner", "autogpt", "automation"),
    ("AutoGPT Code Generator", "autogpt", "coding"),
    ("AutoGPT Analysis Agent", "autogpt", "research"),
    ("AutoGPT Workflow Agent", "autogpt", "automation"),
    # 6 LlamaIndex agents
    ("LlamaIndex Data Query Agent", "llamaindex", "data"),
    ("LlamaIndex Research Retriever", "llamaindex", "research"),
    ("LlamaIndex Document Analyzer", "llamaindex", "data"),
    ("LlamaIndex Knowledge Agent", "llamaindex", "research"),
    ("LlamaIndex RAG Specialist", "llamaindex", "data"),
    ("LlamaIndex Semantic Search Agent", "llamaindex", "research"),
    # 5 Semantic Kernel agents
    ("Semantic Kernel Code Planner", "semantic-kernel", "coding"),
    ("Semantic Kernel Task Automator", "semantic-kernel", "automation"),
    ("Semantic Kernel Skill Orchestrator", "semantic-kernel", "automation"),
    ("Semantic Kernel Code Executor", "semantic-kernel", "coding"),
    ("Semantic Kernel Workflow Engine", "semantic-kernel", "automation"),
    # 4 OpenClaw agents
    ("OpenClaw General Agent", "openclaw", "other"),
    ("OpenClaw Coding Agent", "openclaw", "coding"),
    ("OpenClaw Research Agent", "openclaw", "research"),
    ("OpenClaw Data Agent", "openclaw", "data"),
    # 3 Haystack agents
    ("Haystack Research Agent", "haystack", "research"),
    ("Haystack Data Agent", "haystack", "data"),
    ("Haystack QA Agent", "haystack", "research"),
    # 3 Autogen agents
    ("Autogen Code Agent", "autogen", "coding"),
    ("Autogen Research Agent", "autogen", "research"),
    ("Autogen Multi-Agent Coordinator", "autogen", "coding"),
    # 3 Custom framework agents
    ("Custom Enterprise Agent", "custom", "other"),
    ("Custom Integration Agent", "custom", "automation"),
    ("Custom Domain Specialist", "custom", "other"),
]

# Trace task descriptions (by category)
TASK_TEMPLATES = {
    "coding": [
        "Refactor the authentication module",
        "Fix null pointer in API handler",
        "Add unit tests for service layer",
        "Implement caching for database queries",
        "Review pull request #42",
        "Optimize SQL query performance",
        "Update deprecated dependencies",
        "Add type hints to utils module",
    ],
    "research": [
        "Summarize latest papers on RAG",
        "Compare vector database options",
        "Analyze market trends for AI agents",
        "Research best practices for prompt engineering",
        "Investigate model fine-tuning approaches",
        "Review competitor product features",
    ],
    "data": [
        "Transform CSV to JSON pipeline",
        "Clean and validate customer data",
        "Build ETL for analytics dashboard",
        "Query sales data for Q4 report",
        "Merge datasets from multiple sources",
    ],
    "automation": [
        "Schedule daily backup job",
        "Automate deployment pipeline",
        "Create cron job for reports",
        "Set up webhook for notifications",
        "Build batch processing workflow",
    ],
    "sales": [
        "Draft outreach email to prospects",
        "Qualify leads from CRM",
        "Generate sales proposal",
        "Follow up with warm leads",
        "Create pitch deck summary",
    ],
    "other": [
        "General task execution",
        "Process incoming request",
        "Handle support ticket",
        "Execute workflow step",
    ],
}

# Category benchmark durations (ms) — for fast/medium/slow variation
DURATION_RANGES = {
    "coding": (3000, 15000),
    "research": (5000, 20000),
    "data": (2000, 12000),
    "automation": (1000, 8000),
    "sales": (2000, 6000),
    "other": (2000, 10000),
}


def create_agent(client: httpx.Client, name: str, framework: str, category: str) -> dict | None:
    """Creates a single agent and returns it with API key."""
    payload = {
        "name": name,
        "description": f"{framework}-based {category} agent",
        "framework": framework,
        "category": category,
    }
    try:
        resp = client.post(f"{BASE_URL}/api/v1/agents", json=payload, timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"  Error ({name}): {e}")
        return None


def submit_trace(
    client: httpx.Client,
    agent_id: str,
    api_key: str,
    category: str,
) -> bool:
    """Sends a single trace."""
    tasks = TASK_TEMPLATES.get(category, TASK_TEMPLATES["other"])
    task = random.choice(tasks)
    status = random.choices(
        ["success", "failure", "partial"],
        weights=[85, 10, 5],
    )[0]
    duration_range = DURATION_RANGES.get(category, (2000, 10000))
    duration_ms = random.randint(*duration_range)
    cost_usd = round(random.uniform(0.01, 0.15), 4) if random.random() > 0.2 else 0.0

    payload = {
        "agent_id": agent_id,
        "task_description": task,
        "status": status,
        "duration_ms": duration_ms,
        "category": category,
        "cost_usd": cost_usd,
    }
    try:
        resp = client.post(
            f"{BASE_URL}/api/v1/verify",
            json=payload,
            headers={"x-api-key": api_key},
            timeout=10.0,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"    Trace error: {e}")
        return False


def main():
    """Main seed process."""
    import time as _time
    print("GARL Protocol v1.0 — Agent Seed Script")
    print("=" * 50)
    print(f"Target: {BASE_URL}")
    print()

    created = []
    failed = []

    with httpx.Client() as client:
        # Health check first
        try:
            health = client.get(f"{BASE_URL}/health", timeout=5.0)
            if health.status_code != 200:
                print("Warning: Backend not responding or unhealthy. Continuing...")
        except Exception as e:
            print(f"ERROR: Cannot connect to backend ({BASE_URL}): {e}")
            print("Please start the backend: uvicorn app.main:app --reload")
            sys.exit(1)

        # Create 50 agents (rate limit aware)
        print("Creating agents...")
        reg_count = 0
        for idx, (name, framework, category) in enumerate(AGENTS):
            reg_count += 1
            if reg_count > 1 and reg_count % 4 == 0:
                print(f"  [Rate limit pause — {idx}/{len(AGENTS)} done, waiting 62s...]")
                _time.sleep(62)

            agent = create_agent(client, name, framework, category)
            if agent:
                created.append(agent)
                print(f"  ✓ {name}")
            else:
                # Retry once after waiting
                _time.sleep(62)
                agent = create_agent(client, name, framework, category)
                if agent:
                    created.append(agent)
                    print(f"  ✓ {name} (retry)")
                    reg_count = 0
                else:
                    failed.append(name)
                    print(f"  ✗ {name}")

        print()
        print(f"Created: {len(created)}, Failed: {len(failed)}")
        print()

        # Send 5-15 traces for each agent (rate limit: 20 per 60s for write)
        print("Sending traces...")
        total_traces = 0
        write_counter = 0
        for agent in created:
            agent_id = agent["id"]
            api_key = agent.get("api_key")
            if not api_key:
                print(f"  ⚠ {agent['name']}: No API key, skipping")
                continue

            category = agent.get("category", "other")
            num_traces = random.randint(5, 15)
            success_count = 0
            for _ in range(num_traces):
                write_counter += 1
                if write_counter % 18 == 0:
                    _time.sleep(62)
                if submit_trace(client, agent_id, api_key, category):
                    success_count += 1

            total_traces += success_count
            print(f"  {agent['name']}: {success_count}/{num_traces} trace")

        print()
        print("=" * 50)
        print("SUMMARY")
        print("=" * 50)
        print(f"Total agents: {len(created)}")
        print(f"Failed registrations: {len(failed)}")
        print(f"Traces sent: {total_traces}")
        print()
        print("Seed process completed.")


if __name__ == "__main__":
    main()
