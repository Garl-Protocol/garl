"""
GARL Protocol — LlamaIndex Integration
Callback handler that automatically submits execution traces to GARL.

Usage:
    from garl_callback import GARLCallbackHandler

    handler = GARLCallbackHandler(api_key="garl_...", agent_id="uuid")
    Settings.callback_manager = CallbackManager([handler])
"""

import time
import requests
from typing import Any, Optional
from llama_index.core.callbacks.base_handler import BaseCallbackHandler
from llama_index.core.callbacks.schema import CBEventType, EventPayload

GARL_API = "https://api.garl.ai/api/v1"


class GARLCallbackHandler(BaseCallbackHandler):
    def __init__(
        self,
        api_key: str,
        agent_id: str,
        category: str = "research",
        api_url: str = GARL_API,
    ):
        super().__init__(event_starts_to_ignore=[], event_ends_to_ignore=[])
        self.api_key = api_key
        self.agent_id = agent_id
        self.category = category
        self.api_url = api_url
        self._start_time: Optional[float] = None
        self._task_desc: str = ""
        self._token_count: int = 0
        self._cost: float = 0.0
        self._tool_calls: list[dict] = []

    def on_event_start(
        self,
        event_type: CBEventType,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        parent_id: str = "",
        **kwargs: Any,
    ) -> str:
        if event_type == CBEventType.QUERY:
            self._start_time = time.time()
            if payload and EventPayload.QUERY_STR in payload:
                self._task_desc = str(payload[EventPayload.QUERY_STR])[:1000]
        elif event_type == CBEventType.FUNCTION_CALL:
            tool_name = ""
            if payload and "function_call" in payload:
                tool_name = payload["function_call"]
            elif payload and "tool" in payload:
                tool_name = str(payload["tool"])
            if tool_name:
                self._tool_calls.append({"name": tool_name})
        return event_id

    def on_event_end(
        self,
        event_type: CBEventType,
        payload: Optional[dict[str, Any]] = None,
        event_id: str = "",
        **kwargs: Any,
    ) -> None:
        if event_type == CBEventType.QUERY and self._start_time:
            duration_ms = int((time.time() - self._start_time) * 1000)
            status = "success"

            if payload and EventPayload.RESPONSE in payload:
                resp = payload[EventPayload.RESPONSE]
                if hasattr(resp, "response") and resp.response:
                    output = str(resp.response)[:500]
                else:
                    output = ""
                    status = "failure"
            else:
                output = ""

            trace = {
                "agent_id": self.agent_id,
                "task_description": self._task_desc or "LlamaIndex query",
                "status": status,
                "duration_ms": duration_ms,
                "category": self.category,
                "output_summary": output,
                "tool_calls": self._tool_calls,
                "metadata": {"framework": "llamaindex"},
            }

            if self._token_count > 0:
                trace["token_count"] = self._token_count
            if self._cost > 0:
                trace["cost_usd"] = self._cost

            try:
                requests.post(
                    f"{self.api_url}/verify",
                    json=trace,
                    headers={"x-api-key": self.api_key},
                    timeout=5,
                )
            except Exception:
                pass

            self._start_time = None
            self._task_desc = ""
            self._tool_calls = []
            self._token_count = 0
            self._cost = 0.0

    def start_trace(self, trace_id: Optional[str] = None) -> None:
        pass

    def end_trace(
        self,
        trace_id: Optional[str] = None,
        trace_map: Optional[dict[str, list[str]]] = None,
    ) -> None:
        pass
