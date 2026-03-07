"""
GARL Protocol — CrewAI Tool Integration

Provides a trust verification tool that CrewAI agents can use
to check other agents' trustworthiness before delegation.

Usage:
    from garl_tool import GarlTrustTool

    tool = GarlTrustTool(api_key="garl_...", agent_id="your-uuid")
    crew = Crew(agents=[...], tools=[tool])
"""

import time
import threading
from typing import Type

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required: pip install httpx")

try:
    from crewai.tools import BaseTool
    from pydantic import BaseModel, Field
except ImportError:
    raise ImportError(
        "crewai and pydantic are required: pip install crewai pydantic"
    )


class TrustCheckInput(BaseModel):
    agent_id: str = Field(description="UUID of the agent to check trust for")


class GarlTrustTool(BaseTool):
    """CrewAI tool that checks an agent's trust score on GARL Protocol."""

    name: str = "garl_trust_check"
    description: str = (
        "Check the trust score and reputation of an AI agent on GARL Protocol. "
        "Returns trust score (0-100), certification tier, risk level, "
        "and a recommendation (trusted/caution/do_not_delegate). "
        "Use this before delegating work to another agent."
    )
    args_schema: Type[BaseModel] = TrustCheckInput

    api_key: str = ""
    garl_agent_id: str = ""
    base_url: str = "https://api.garl.ai/api/v1"

    def __init__(self, api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
        super().__init__(api_key=api_key, garl_agent_id=agent_id, base_url=base_url.rstrip("/"))

    def _run(self, agent_id: str) -> str:
        try:
            resp = httpx.get(
                f"{self.base_url}/trust/verify",
                params={"agent_id": agent_id},
                timeout=10.0,
            )
            if resp.status_code != 200:
                return f"Trust check failed: HTTP {resp.status_code}"

            data = resp.json()
            score = data.get("trust_score", 0)
            tier = data.get("certification_tier", "unknown")
            risk = data.get("risk_level", "unknown")
            rec = data.get("recommendation", "unknown")
            dims = data.get("dimensions", {})

            lines = [
                f"Trust Score: {score}/100 ({tier} tier)",
                f"Risk Level: {risk}",
                f"Recommendation: {rec}",
            ]
            if dims:
                lines.append("Dimensions:")
                for k, v in dims.items():
                    lines.append(f"  {k}: {v}")

            return "\n".join(lines)
        except Exception as e:
            return f"Trust check error: {e}"


class GarlTraceTool(BaseTool):
    """CrewAI tool that reports task completions to GARL Protocol."""

    name: str = "garl_log_trace"
    description: str = (
        "Report a completed task to GARL Protocol to build your trust reputation. "
        "Provide a description of what was done, the status (success/failure/partial), "
        "and optionally the category (coding/research/data/automation/sales/other)."
    )
    args_schema: Type[BaseModel] = type(
        "TraceInput",
        (BaseModel,),
        {
            "__annotations__": {
                "task_description": str,
                "status": str,
                "category": str,
            },
            "task_description": Field(description="What was accomplished"),
            "status": Field(default="success", description="success, failure, or partial"),
            "category": Field(default="other", description="coding, research, data, automation, sales, or other"),
        },
    )

    api_key: str = ""
    garl_agent_id: str = ""
    base_url: str = "https://api.garl.ai/api/v1"

    def __init__(self, api_key: str, agent_id: str, base_url: str = "https://api.garl.ai/api/v1"):
        super().__init__(api_key=api_key, garl_agent_id=agent_id, base_url=base_url.rstrip("/"))

    def _run(self, task_description: str, status: str = "success", category: str = "other") -> str:
        payload = {
            "agent_id": self.garl_agent_id,
            "task_description": task_description[:1000],
            "status": status,
            "duration_ms": 0,
            "category": category,
            "runtime_env": "crewai",
        }
        try:
            resp = httpx.post(
                f"{self.base_url}/verify",
                json=payload,
                headers={"x-api-key": self.api_key, "Content-Type": "application/json"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                delta = data.get("trust_delta", 0)
                return f"Trace recorded. Trust delta: {delta:+.2f}"
            return f"Trace submission failed: HTTP {resp.status_code}"
        except Exception as e:
            return f"Trace error: {e}"
