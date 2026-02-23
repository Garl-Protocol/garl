#!/usr/bin/env python3
"""
Direct SQL seed script — bypasses API rate limits.
Generates INSERT statements and prints them for execution via Supabase SQL.
"""
import uuid
import secrets
import hashlib
import random
import json
from datetime import datetime, timezone, timedelta

AGENTS = [
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
    ("CrewAI Sales Orchestrator", "crewai", "sales"),
    ("CrewAI Research Analyst", "crewai", "research"),
    ("CrewAI Task Automator", "crewai", "automation"),
    ("CrewAI Data Scientist", "crewai", "data"),
    ("CrewAI Code Assistant", "crewai", "coding"),
    ("CrewAI Lead Qualifier", "crewai", "sales"),
    ("CrewAI Report Writer", "crewai", "research"),
    ("CrewAI Pipeline Manager", "crewai", "automation"),
    ("AutoGPT Coding Agent", "autogpt", "coding"),
    ("AutoGPT Research Agent", "autogpt", "research"),
    ("AutoGPT Automation Agent", "autogpt", "automation"),
    ("AutoGPT Data Agent", "autogpt", "data"),
    ("AutoGPT Task Runner", "autogpt", "automation"),
    ("AutoGPT Code Generator", "autogpt", "coding"),
    ("AutoGPT Analysis Agent", "autogpt", "research"),
    ("AutoGPT Workflow Agent", "autogpt", "automation"),
    ("LlamaIndex Data Query Agent", "llamaindex", "data"),
    ("LlamaIndex Research Retriever", "llamaindex", "research"),
    ("LlamaIndex Document Analyzer", "llamaindex", "data"),
    ("LlamaIndex Knowledge Agent", "llamaindex", "research"),
    ("LlamaIndex RAG Specialist", "llamaindex", "data"),
    ("LlamaIndex Semantic Search Agent", "llamaindex", "research"),
    ("Semantic Kernel Code Planner", "semantic-kernel", "coding"),
    ("Semantic Kernel Task Automator", "semantic-kernel", "automation"),
    ("Semantic Kernel Skill Orchestrator", "semantic-kernel", "automation"),
    ("Semantic Kernel Code Executor", "semantic-kernel", "coding"),
    ("Semantic Kernel Workflow Engine", "semantic-kernel", "automation"),
    ("OpenClaw General Agent", "openclaw", "other"),
    ("OpenClaw Coding Agent", "openclaw", "coding"),
    ("OpenClaw Research Agent", "openclaw", "research"),
    ("OpenClaw Data Agent", "openclaw", "data"),
    ("Haystack Research Agent", "haystack", "research"),
    ("Haystack Data Agent", "haystack", "data"),
    ("Haystack QA Agent", "haystack", "research"),
    ("Autogen Code Agent", "autogen", "coding"),
    ("Autogen Research Agent", "autogen", "research"),
    ("Autogen Multi-Agent Coordinator", "autogen", "coding"),
    ("Custom Enterprise Agent", "custom", "other"),
    ("Custom Integration Agent", "custom", "automation"),
    ("Custom Domain Specialist", "custom", "other"),
]

TASK_TEMPLATES = {
    "coding": ["Refactor authentication module", "Fix null pointer in API handler", "Add unit tests for service layer",
               "Implement caching for database queries", "Review pull request #42", "Optimize SQL query performance",
               "Update deprecated dependencies", "Add type hints to utils module"],
    "research": ["Summarize latest papers on RAG", "Compare vector database options", "Analyze market trends for AI agents",
                 "Research best practices for prompt engineering", "Investigate model fine-tuning approaches", "Review competitor features"],
    "data": ["Transform CSV to JSON pipeline", "Clean and validate customer data", "Build ETL for analytics dashboard",
             "Query sales data for Q4 report", "Merge datasets from multiple sources"],
    "automation": ["Schedule daily backup job", "Automate deployment pipeline", "Create cron job for reports",
                   "Set up webhook for notifications", "Build batch processing workflow"],
    "sales": ["Draft outreach email to prospects", "Qualify leads from CRM", "Generate sales proposal",
              "Follow up with warm leads", "Create pitch deck summary"],
    "other": ["General task execution", "Process incoming request", "Handle support ticket", "Execute workflow step"],
}

DURATION_RANGES = {
    "coding": (3000, 15000), "research": (5000, 20000), "data": (2000, 12000),
    "automation": (1000, 8000), "sales": (2000, 6000), "other": (2000, 10000),
}


def compute_tier(score):
    if score >= 90:
        return "enterprise"
    elif score >= 70:
        return "gold"
    elif score >= 40:
        return "silver"
    return "bronze"


def esc(s):
    return s.replace("'", "''")


def generate_sql():
    now = datetime.now(timezone.utc)
    all_agents_sql = []
    all_traces_sql = []
    all_history_sql = []

    for name, framework, category in AGENTS:
        agent_id = str(uuid.uuid4())
        sovereign_id = f"did:garl:{agent_id}"
        api_key = f"garl_{secrets.token_urlsafe(32)}"
        api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()

        num_traces = random.randint(5, 15)
        statuses = random.choices(["success", "failure", "partial"], weights=[85, 10, 5], k=num_traces)
        successes = statuses.count("success")
        success_rate = round((successes / num_traces) * 100, 2) if num_traces > 0 else 0

        dur_range = DURATION_RANGES.get(category, (2000, 10000))
        durations = [random.randint(*dur_range) for _ in range(num_traces)]
        avg_dur = sum(durations) // len(durations) if durations else 0
        costs = [round(random.uniform(0.01, 0.15), 4) if random.random() > 0.2 else 0.0 for _ in range(num_traces)]
        total_cost = round(sum(costs), 6)

        base_score = 50.0
        trust_score = base_score
        deltas = []
        for i, status in enumerate(statuses):
            if status == "success":
                delta = round(random.uniform(0.5, 2.5), 4)
            elif status == "failure":
                delta = round(random.uniform(-3.0, -1.0), 4)
            else:
                delta = round(random.uniform(-0.5, 0.5), 4)
            trust_score = max(0, min(100, trust_score + delta))
            deltas.append(delta)

        trust_score = round(trust_score, 2)
        dim_scores = {
            "reliability": round(max(0, min(100, 50 + random.uniform(-10, 20) + (successes * 1.5))), 2),
            "security": round(max(0, min(100, 50 + random.uniform(-5, 15))), 2),
            "speed": round(max(0, min(100, 50 + random.uniform(-10, 20))), 2),
            "cost_efficiency": round(max(0, min(100, 50 + random.uniform(-5, 25))), 2),
            "consistency": round(max(0, min(100, 50 + random.uniform(-10, 20) + (successes * 0.8))), 2),
        }
        tier = compute_tier(trust_score)

        created_at = now - timedelta(days=random.randint(1, 14), hours=random.randint(0, 23))
        last_trace_at = now - timedelta(hours=random.randint(1, 48))

        agent_sql = (
            f"INSERT INTO agents (id, name, description, framework, category, trust_score, "
            f"total_traces, success_count, success_rate, consecutive_successes, "
            f"score_reliability, score_security, score_speed, score_cost_efficiency, score_consistency, "
            f"ema_reliability, ema_security, ema_speed, ema_cost_efficiency, "
            f"total_cost_usd, avg_duration_ms, anomaly_flags, endorsement_score, endorsement_count, "
            f"sovereign_id, certification_tier, permissions_declared, security_events, "
            f"is_deleted, is_sandbox, api_key_hash, created_at, updated_at, last_trace_at) VALUES ("
            f"'{agent_id}', '{esc(name)}', '{esc(framework)}-based {category} agent', "
            f"'{framework}', '{category}', {trust_score}, "
            f"{num_traces}, {successes}, {success_rate}, {max(0, successes - 2)}, "
            f"{dim_scores['reliability']}, {dim_scores['security']}, {dim_scores['speed']}, "
            f"{dim_scores['cost_efficiency']}, {dim_scores['consistency']}, "
            f"{dim_scores['reliability']}, {dim_scores['security']}, {dim_scores['speed']}, {dim_scores['cost_efficiency']}, "
            f"{total_cost}, {avg_dur}, '[]'::jsonb, 0.0, 0, "
            f"'{sovereign_id}', '{tier}', '[]'::jsonb, '[]'::jsonb, "
            f"false, false, '{api_key_hash}', "
            f"'{created_at.isoformat()}', '{now.isoformat()}', '{last_trace_at.isoformat()}');"
        )
        all_agents_sql.append(agent_sql)

        tasks = TASK_TEMPLATES.get(category, TASK_TEMPLATES["other"])
        for i in range(num_traces):
            trace_id = str(uuid.uuid4())
            task = random.choice(tasks)
            trace_created = created_at + timedelta(hours=i * random.randint(2, 12))
            trace_hash = hashlib.sha256(f"{trace_id}{agent_id}{task}".encode()).hexdigest()

            trace_sql = (
                f"INSERT INTO traces (id, agent_id, task_description, status, duration_ms, "
                f"category, trust_delta, certificate, metadata, cost_usd, trace_hash, created_at) VALUES ("
                f"'{trace_id}', '{agent_id}', '{esc(task)}', '{statuses[i]}', {durations[i]}, "
                f"'{category}', {deltas[i]}, '{{}}'::jsonb, '{{}}'::jsonb, {costs[i]}, '{trace_hash}', "
                f"'{trace_created.isoformat()}');"
            )
            all_traces_sql.append(trace_sql)

            hist_sql = (
                f"INSERT INTO reputation_history (id, agent_id, trust_score, event_type, trust_delta, "
                f"score_reliability, score_speed, score_cost_efficiency, score_consistency, score_security, "
                f"created_at) VALUES ("
                f"'{str(uuid.uuid4())}', '{agent_id}', "
                f"{round(50 + sum(deltas[:i+1]), 2)}, '{statuses[i]}', {deltas[i]}, "
                f"{dim_scores['reliability']}, {dim_scores['speed']}, {dim_scores['cost_efficiency']}, "
                f"{dim_scores['consistency']}, {dim_scores['security']}, "
                f"'{trace_created.isoformat()}');"
            )
            all_history_sql.append(hist_sql)

    return "\n".join(all_agents_sql), "\n".join(all_traces_sql), "\n".join(all_history_sql)


if __name__ == "__main__":
    agents_sql, traces_sql, history_sql = generate_sql()
    with open("/tmp/garl_seed_agents.sql", "w") as f:
        f.write(agents_sql)
    with open("/tmp/garl_seed_traces.sql", "w") as f:
        f.write(traces_sql)
    with open("/tmp/garl_seed_history.sql", "w") as f:
        f.write(history_sql)
    
    agent_count = agents_sql.count("INSERT INTO agents")
    trace_count = traces_sql.count("INSERT INTO traces")
    hist_count = history_sql.count("INSERT INTO reputation_history")
    print(f"Generated: {agent_count} agents, {trace_count} traces, {hist_count} history entries")
    print("Files: /tmp/garl_seed_agents.sql, /tmp/garl_seed_traces.sql, /tmp/garl_seed_history.sql")
