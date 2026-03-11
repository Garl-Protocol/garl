"""
GARL Protocol — Semantic Kernel Integration
Function invocation filter that submits execution traces to GARL.

Usage:
    from garl_filter import GARLFilter

    kernel = Kernel()
    kernel.add_filter("function_invocation", GARLFilter(api_key="garl_...", agent_id="uuid"))
"""

import time
import requests
from typing import Any
from semantic_kernel.filters.filter_types import FilterTypes
from semantic_kernel.filters.functions.function_invocation_context import FunctionInvocationContext

GARL_API = "https://api.garl.ai/api/v1"


class GARLFilter:
    """Semantic Kernel function invocation filter for GARL trust scoring."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        category: str = "coding",
        api_url: str = GARL_API,
    ):
        self.api_key = api_key
        self.agent_id = agent_id
        self.category = category
        self.api_url = api_url

    async def __call__(self, context: FunctionInvocationContext, next_filter: Any) -> None:
        start = time.time()
        status = "success"
        output = ""

        try:
            await next_filter(context)
            if context.result:
                output = str(context.result.value)[:500] if context.result.value else ""
        except Exception as e:
            status = "failure"
            output = str(e)[:500]
            raise
        finally:
            duration_ms = int((time.time() - start) * 1000)

            func_name = ""
            if context.function:
                func_name = f"{context.function.plugin_name}.{context.function.name}" if context.function.plugin_name else context.function.name

            trace = {
                "agent_id": self.agent_id,
                "task_description": func_name or "Semantic Kernel function",
                "status": status,
                "duration_ms": duration_ms,
                "category": self.category,
                "output_summary": output,
                "tool_calls": [{"name": func_name}] if func_name else [],
                "metadata": {"framework": "semantic-kernel"},
            }

            try:
                requests.post(
                    f"{self.api_url}/verify",
                    json=trace,
                    headers={"x-api-key": self.api_key},
                    timeout=5,
                )
            except Exception:
                pass
