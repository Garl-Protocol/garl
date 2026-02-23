"""
GARL Protocol — LangChain Callback Handler

Automatically sends execution traces to GARL after LangChain chain/tool runs.

Usage:
    from garl_callback import GarlCallbackHandler

    handler = GarlCallbackHandler(api_key="garl_...", agent_id="your-uuid")
    chain.invoke({"input": "..."}, config={"callbacks": [handler]})
"""

import time
import threading
from typing import Any
from uuid import UUID

try:
    import httpx
except ImportError:
    raise ImportError("httpx is required: pip install httpx")

try:
    from langchain_core.callbacks import BaseCallbackHandler
except ImportError:
    try:
        from langchain.callbacks.base import BaseCallbackHandler
    except ImportError:
        raise ImportError(
            "langchain-core or langchain is required: pip install langchain-core"
        )


class GarlCallbackHandler(BaseCallbackHandler):
    """LangChain callback handler that auto-reports execution traces to GARL."""

    def __init__(
        self,
        api_key: str,
        agent_id: str,
        base_url: str = "https://api.garl.ai/api/v1",
        category: str = "coding",
        async_send: bool = True,
    ):
        super().__init__()
        self.api_key = api_key
        self.agent_id = agent_id
        self.base_url = base_url.rstrip("/")
        self.category = category
        self.async_send = async_send
        self._chain_start_time: float | None = None
        self._tool_start_times: dict[str, float] = {}
        self._tool_calls: list[dict[str, Any]] = []

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._chain_start_time = time.time()
        self._tool_calls = []

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        self._tool_start_times[str(run_id)] = time.time()

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        start = self._tool_start_times.pop(str(run_id), time.time())
        duration = int((time.time() - start) * 1000)
        name = kwargs.get("name", "unknown_tool")
        self._tool_calls.append({
            "name": name,
            "duration_ms": duration,
        })

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        if self._chain_start_time is None:
            return
        duration_ms = int((time.time() - self._chain_start_time) * 1000)
        self._send_trace("success", duration_ms, "Chain completed")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: UUID,
        **kwargs: Any,
    ) -> None:
        duration_ms = 0
        if self._chain_start_time:
            duration_ms = int((time.time() - self._chain_start_time) * 1000)
        self._send_trace("failure", duration_ms, f"Error: {type(error).__name__}")

    def _send_trace(self, status: str, duration_ms: int, description: str) -> None:
        payload = {
            "agent_id": self.agent_id,
            "task_description": description,
            "status": status,
            "duration_ms": duration_ms,
            "category": self.category,
            "runtime_env": "langchain",
        }
        if self._tool_calls:
            payload["tool_calls"] = self._tool_calls

        if self.async_send:
            threading.Thread(
                target=self._post_trace, args=(payload,), daemon=True
            ).start()
        else:
            self._post_trace(payload)

        self._chain_start_time = None
        self._tool_calls = []

    def _post_trace(self, payload: dict) -> None:
        try:
            httpx.post(
                f"{self.base_url}/verify",
                json=payload,
                headers={
                    "x-api-key": self.api_key,
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
        except Exception:
            pass
