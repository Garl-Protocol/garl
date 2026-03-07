"""
GARL Protocol — AutoGen Function Integration

Provides trust verification and trace logging functions
that AutoGen agents can call during conversations.

Usage:
    from garl_functions import get_garl_functions

    functions = get_garl_functions(api_key="garl_...", agent_id="your-uuid")
    assistant = AssistantAgent("assistant", llm_config={"functions": functions})
"""

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required: pip install httpx")


def get_garl_functions(
    api_key: str,
    agent_id: str,
    base_url: str = "https://api.garl.ai/api/v1",
):
    """Return a list of function definitions and their implementations for AutoGen.

    Returns:
        tuple: (function_map, function_definitions)
            - function_map: dict mapping function names to callables
            - function_definitions: list of OpenAI function schemas
    """
    base = base_url.rstrip("/")

    def check_trust(target_agent_id: str) -> str:
        """Check the trust score and reputation of an AI agent."""
        try:
            resp = httpx.get(
                f"{base}/trust/verify",
                params={"agent_id": target_agent_id},
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

    def log_trace(
        task_description: str,
        status: str = "success",
        category: str = "other",
    ) -> str:
        """Report a completed task to GARL Protocol."""
        payload = {
            "agent_id": agent_id,
            "task_description": task_description[:1000],
            "status": status,
            "duration_ms": 0,
            "category": category,
            "runtime_env": "autogen",
        }
        try:
            resp = httpx.post(
                f"{base}/verify",
                json=payload,
                headers={"x-api-key": api_key, "Content-Type": "application/json"},
                timeout=10.0,
            )
            if resp.status_code == 200:
                data = resp.json()
                delta = data.get("trust_delta", 0)
                return f"Trace recorded. Trust delta: {delta:+.2f}"
            return f"Trace submission failed: HTTP {resp.status_code}"
        except Exception as e:
            return f"Trace error: {e}"

    function_map = {
        "garl_check_trust": check_trust,
        "garl_log_trace": log_trace,
    }

    function_definitions = [
        {
            "name": "garl_check_trust",
            "description": (
                "Check the trust score and reputation of an AI agent on GARL Protocol. "
                "Use this before delegating work to another agent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "target_agent_id": {
                        "type": "string",
                        "description": "UUID of the agent to check trust for",
                    }
                },
                "required": ["target_agent_id"],
            },
        },
        {
            "name": "garl_log_trace",
            "description": (
                "Report a completed task to GARL Protocol to build trust reputation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "task_description": {
                        "type": "string",
                        "description": "What was accomplished",
                    },
                    "status": {
                        "type": "string",
                        "enum": ["success", "failure", "partial"],
                        "description": "Task outcome",
                    },
                    "category": {
                        "type": "string",
                        "enum": ["coding", "research", "data", "automation", "sales", "other"],
                        "description": "Task category",
                    },
                },
                "required": ["task_description"],
            },
        },
    ]

    return function_map, function_definitions
