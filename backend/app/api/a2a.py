"""
A2A v1.0 JSON-RPC 2.0 Protocol Binding

Supports: SendMessage, GetTask
Protocol: JSON-RPC 2.0 over HTTPS
Spec ref: https://a2a-protocol.org/latest/specification/ (Section 9)
"""

import re
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request

from app.models.a2a_schemas import (
    A2ATaskState,
    A2AMessageRole,
    A2APart,
    A2AMessage,
    A2ATaskStatus,
    A2AArtifact,
    A2ATask,
    SendMessageResponse,
    JSONRPCRequest,
    JSONRPCResponse,
)
from app.services.agents import get_a2a_trust, route_agents, compare_agents

a2a_router = APIRouter(tags=["A2A Protocol"])

_task_store: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _jsonrpc_error(req_id, code: int, message: str, data: dict | None = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data:
        err["data"] = data
    return JSONRPCResponse(jsonrpc="2.0", error=err, id=req_id).model_dump()


def _extract_agent_id(text: str) -> str | None:
    """Extract UUID from free-form text."""
    match = re.search(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
        text,
        re.IGNORECASE,
    )
    return match.group(0) if match else None


def _extract_did(text: str) -> str | None:
    """Extract did:garl:UUID from text."""
    match = re.search(r"did:garl:([0-9a-f-]{36})", text, re.IGNORECASE)
    return match.group(1) if match else None


def _detect_intent(text: str) -> tuple[str, dict]:
    """Detect which GARL skill to invoke from free-form text."""
    lower = text.lower()

    agent_id = _extract_did(text) or _extract_agent_id(text)

    if any(kw in lower for kw in ["route", "find agent", "recommend", "best agent", "delegate"]):
        category = "other"
        for cat in ["coding", "research", "data", "automation", "sales"]:
            if cat in lower:
                category = cat
                break
        return "route_agent", {"category": category}

    if any(kw in lower for kw in ["compare", "versus", "vs", "side by side"]):
        ids = re.findall(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            text,
            re.IGNORECASE,
        )
        return "compare_agents", {"agent_ids": ids}

    if any(kw in lower for kw in ["register", "sign up", "create agent", "onboard"]):
        return "register_agent", {}

    if agent_id:
        return "trust_check", {"agent_id": agent_id}

    return "trust_check", {"query": text}


def _build_trust_check_result(agent_id: str) -> SendMessageResponse:
    """Execute trust_check skill and wrap result in A2A SendMessageResponse."""
    trust_data = get_a2a_trust(agent_id)
    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    now = _now_iso()

    if not trust_data:
        task = A2ATask(
            id=task_id,
            contextId=context_id,
            status=A2ATaskStatus(
                state=A2ATaskState.COMPLETED,
                timestamp=now,
            ),
            artifacts=[
                A2AArtifact(
                    artifactId=str(uuid.uuid4()),
                    name="Trust Verification Result",
                    parts=[
                        A2APart(
                            data={
                                "registered": False,
                                "agent_id": agent_id,
                                "trust_score": 0,
                                "risk_level": "unknown",
                                "recommendation": "unknown",
                                "message": "This agent is not registered on GARL Protocol.",
                                "register_url": "https://api.garl.ai/api/v1/agents/auto-register",
                            },
                            mediaType="application/json",
                        )
                    ],
                )
            ],
        )
    else:
        trust_data["registered"] = True
        task = A2ATask(
            id=task_id,
            contextId=context_id,
            status=A2ATaskStatus(
                state=A2ATaskState.COMPLETED,
                timestamp=now,
            ),
            artifacts=[
                A2AArtifact(
                    artifactId=str(uuid.uuid4()),
                    name="Trust Verification Result",
                    parts=[
                        A2APart(data=trust_data, mediaType="application/json")
                    ],
                )
            ],
        )

    _task_store[task_id] = task.model_dump()
    return SendMessageResponse(task=task)


def _build_route_result(category: str) -> SendMessageResponse:
    """Execute route_agent skill."""
    route_data = route_agents(category, "silver", 3)
    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    now = _now_iso()

    task = A2ATask(
        id=task_id,
        contextId=context_id,
        status=A2ATaskStatus(state=A2ATaskState.COMPLETED, timestamp=now),
        artifacts=[
            A2AArtifact(
                artifactId=str(uuid.uuid4()),
                name="Agent Routing Recommendations",
                parts=[A2APart(data=route_data, mediaType="application/json")],
            )
        ],
    )
    _task_store[task_id] = task.model_dump()
    return SendMessageResponse(task=task)


def _build_compare_result(agent_ids: list[str]) -> SendMessageResponse:
    """Execute compare_agents skill."""
    task_id = str(uuid.uuid4())
    context_id = str(uuid.uuid4())
    now = _now_iso()

    if len(agent_ids) < 2:
        task = A2ATask(
            id=task_id,
            contextId=context_id,
            status=A2ATaskStatus(
                state=A2ATaskState.FAILED,
                timestamp=now,
                message=A2AMessage(
                    messageId=str(uuid.uuid4()),
                    role=A2AMessageRole.AGENT,
                    parts=[A2APart(text="At least 2 agent IDs required for comparison.")],
                ),
            ),
        )
    else:
        comparison = compare_agents(agent_ids)
        task = A2ATask(
            id=task_id,
            contextId=context_id,
            status=A2ATaskStatus(state=A2ATaskState.COMPLETED, timestamp=now),
            artifacts=[
                A2AArtifact(
                    artifactId=str(uuid.uuid4()),
                    name="Agent Comparison",
                    parts=[A2APart(data={"agents": comparison}, mediaType="application/json")],
                )
            ],
        )

    _task_store[task_id] = task.model_dump()
    return SendMessageResponse(task=task)


def _build_register_info() -> SendMessageResponse:
    """Return registration instructions as an A2A Message (no task needed)."""
    return SendMessageResponse(
        message=A2AMessage(
            messageId=str(uuid.uuid4()),
            role=A2AMessageRole.AGENT,
            parts=[
                A2APart(
                    data={
                        "action": "Register your agent on GARL Protocol",
                        "endpoint": "POST https://api.garl.ai/api/v1/agents/auto-register",
                        "required_fields": ["name"],
                        "optional_fields": ["framework", "category", "description"],
                        "example": {"name": "my-agent", "framework": "langchain"},
                        "documentation": "https://garl.ai/docs",
                    },
                    mediaType="application/json",
                )
            ],
        )
    )


def _handle_send_message(params: dict, req_id) -> dict:
    """Handle SendMessage JSON-RPC method."""
    message_data = params.get("message")
    if not message_data:
        return _jsonrpc_error(req_id, -32602, "InvalidParams", {"detail": "message field is required"})

    parts = message_data.get("parts", [])
    if not parts:
        return _jsonrpc_error(req_id, -32602, "InvalidParams", {"detail": "message.parts must not be empty"})

    message_id = message_data.get("messageId")
    if not message_id:
        return _jsonrpc_error(req_id, -32602, "InvalidParams", {"detail": "message.messageId is required"})

    text_content = ""
    for part in parts:
        if "text" in part and part["text"]:
            text_content += part["text"] + " "
        elif "data" in part and part["data"]:
            if "agent_id" in part["data"]:
                text_content += f"check trust {part['data']['agent_id']} "

    text_content = text_content.strip()
    if not text_content:
        return _jsonrpc_error(
            req_id, -32602, "InvalidParams",
            {"detail": "No actionable content found in message parts"},
        )

    intent, intent_params = _detect_intent(text_content)

    if intent == "trust_check":
        agent_id = intent_params.get("agent_id")
        if not agent_id:
            return _jsonrpc_error(
                req_id, -32602, "InvalidParams",
                {"detail": "Could not extract agent ID from message. Provide a UUID or did:garl:UUID."},
            )
        response = _build_trust_check_result(agent_id)

    elif intent == "route_agent":
        response = _build_route_result(intent_params.get("category", "other"))

    elif intent == "compare_agents":
        response = _build_compare_result(intent_params.get("agent_ids", []))

    elif intent == "register_agent":
        response = _build_register_info()

    else:
        return _jsonrpc_error(req_id, -32602, "InvalidParams", {"detail": "Could not determine intent."})

    return JSONRPCResponse(
        jsonrpc="2.0",
        result=response.model_dump(exclude_none=True),
        id=req_id,
    ).model_dump(exclude_none=True)


def _handle_get_task(params: dict, req_id) -> dict:
    """Handle GetTask JSON-RPC method."""
    task_id = params.get("id")
    if not task_id:
        return _jsonrpc_error(req_id, -32602, "InvalidParams", {"detail": "id field is required"})

    task_data = _task_store.get(task_id)
    if not task_data:
        return _jsonrpc_error(req_id, -32001, "TaskNotFoundError", {"taskId": task_id})

    return JSONRPCResponse(
        jsonrpc="2.0",
        result=task_data,
        id=req_id,
    ).model_dump(exclude_none=True)


_METHOD_HANDLERS = {
    "SendMessage": _handle_send_message,
    "GetTask": _handle_get_task,
}


@a2a_router.post("/a2a")
async def a2a_jsonrpc(request: Request):
    """A2A v1.0 JSON-RPC 2.0 endpoint."""
    try:
        body = await request.json()
    except Exception:
        return _jsonrpc_error(None, -32700, "ParseError", {"detail": "Invalid JSON"})

    req_id = body.get("id")
    jsonrpc = body.get("jsonrpc")
    method = body.get("method")
    params = body.get("params", {})

    if jsonrpc != "2.0":
        return _jsonrpc_error(req_id, -32600, "InvalidRequest", {"detail": "jsonrpc must be '2.0'"})

    if not method:
        return _jsonrpc_error(req_id, -32600, "InvalidRequest", {"detail": "method is required"})

    handler = _METHOD_HANDLERS.get(method)
    if not handler:
        return _jsonrpc_error(
            req_id, -32601, "MethodNotFound",
            {"detail": f"Method '{method}' not found. Supported: {list(_METHOD_HANDLERS.keys())}"},
        )

    try:
        return handler(params, req_id)
    except Exception as exc:
        return _jsonrpc_error(req_id, -32603, "InternalError", {"detail": str(exc)})
