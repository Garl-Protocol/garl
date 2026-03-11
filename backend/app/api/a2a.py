"""
A2A v1.0 JSON-RPC 2.0 Protocol Binding

Supports: SendMessage, GetTask
Protocol: JSON-RPC 2.0 over HTTPS
Spec ref: https://a2a-protocol.org/latest/specification/ (Section 9)
"""

import json
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
from app.services.agents import get_a2a_trust, route_agents, compare_agents, get_leaderboard, get_compliance_report

a2a_router = APIRouter(tags=["A2A Protocol"])

_task_store: dict[str, dict] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


def _jsonrpc_error(req_id, code: int, message: str, data: dict | None = None) -> dict:
    err: dict = {"code": code, "message": message}
    if data:
        err["data"] = data
    return JSONRPCResponse(jsonrpc="2.0", error=err, id=req_id).model_dump(exclude_none=True)


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


INTENT_SCHEMA = {
    "route_agent": {
        "keywords": ["route", "find agent", "recommend", "best agent", "delegate", "which agent", "suggest agent"],
        "description": "Find the most trusted agent for a given task category",
        "requires_agent_id": False,
    },
    "compare_agents": {
        "keywords": ["compare", "versus", "vs", "side by side", "difference between"],
        "description": "Compare 2+ agents across trust dimensions",
        "requires_agent_id": False,
    },
    "register_agent": {
        "keywords": ["register", "sign up", "create agent", "onboard", "new agent", "join"],
        "description": "Get instructions for agent registration",
        "requires_agent_id": False,
    },
    "leaderboard": {
        "keywords": ["leaderboard", "top agents", "ranking", "ranked", "best performing", "leaders"],
        "description": "Get the top-ranked agents",
        "requires_agent_id": False,
    },
    "verify_trace": {
        "keywords": ["verify", "check trace", "validate", "certificate", "proof", "authentic"],
        "description": "Verify a trace's cryptographic certificate",
        "requires_agent_id": False,
    },
    "compliance": {
        "keywords": ["compliance", "audit", "security report", "sla", "risk assessment"],
        "description": "Get compliance report for an agent",
        "requires_agent_id": True,
    },
    "trust_check": {
        "keywords": ["trust", "score", "check", "reputation", "tier", "certified"],
        "description": "Check trust score and certification tier",
        "requires_agent_id": True,
    },
}

CATEGORIES = ["coding", "research", "data", "automation", "sales", "other"]


def _detect_intent(text: str) -> tuple[str, dict]:
    """Rule-based intent detection using structured schema."""
    lower = text.lower()
    agent_id = _extract_did(text) or _extract_agent_id(text)
    scores: dict[str, int] = {}

    for intent_name, schema in INTENT_SCHEMA.items():
        score = sum(2 if kw in lower else 0 for kw in schema["keywords"])
        if score > 0:
            scores[intent_name] = score

    if scores:
        best_intent = max(scores, key=scores.get)  # type: ignore[arg-type]
    elif agent_id:
        best_intent = "trust_check"
    else:
        best_intent = "trust_check"

    params: dict = {}
    if best_intent == "route_agent":
        params["category"] = next((cat for cat in CATEGORIES if cat in lower), "other")
    elif best_intent == "compare_agents":
        params["agent_ids"] = re.findall(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            text, re.IGNORECASE,
        )
    elif best_intent == "leaderboard":
        params["category"] = next((cat for cat in CATEGORIES if cat in lower), None)
        try:
            limit_match = re.search(r"top\s*(\d+)", lower)
            params["limit"] = int(limit_match.group(1)) if limit_match else 5
        except (ValueError, AttributeError):
            params["limit"] = 5
    elif best_intent == "verify_trace":
        hash_match = re.search(r"[0-9a-f]{64}", text, re.IGNORECASE)
        params["trace_hash"] = hash_match.group(0) if hash_match else None
    elif best_intent in ("trust_check", "compliance"):
        params["agent_id"] = agent_id

    if agent_id and "agent_id" not in params:
        params["agent_id"] = agent_id

    return best_intent, params


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

    _task_store[task_id] = task.model_dump(exclude_none=True)
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
    _task_store[task_id] = task.model_dump(exclude_none=True)
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

    _task_store[task_id] = task.model_dump(exclude_none=True)
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


def _build_leaderboard_result(category: str | None, limit: int) -> SendMessageResponse:
    """Execute leaderboard skill."""
    lb_data = get_leaderboard(category=category, limit=min(limit, 10), offset=0)
    task_id = str(uuid.uuid4())
    now = _now_iso()
    task = A2ATask(
        id=task_id,
        contextId=str(uuid.uuid4()),
        status=A2ATaskStatus(state=A2ATaskState.COMPLETED, timestamp=now),
        artifacts=[
            A2AArtifact(
                artifactId=str(uuid.uuid4()),
                name="Leaderboard",
                parts=[A2APart(data=lb_data, mediaType="application/json")],
            )
        ],
    )
    _task_store[task_id] = task.model_dump(exclude_none=True)
    return SendMessageResponse(task=task)


def _build_verify_result(trace_hash: str) -> SendMessageResponse:
    """Execute verify_trace skill."""
    from app.core.supabase_client import get_supabase
    from app.core.signing import sign_trace, verify_signature, get_public_key_hex

    db = get_supabase()
    res = db.table("traces").select("*").eq("trace_hash", trace_hash).execute()
    task_id = str(uuid.uuid4())
    now = _now_iso()

    if not res.data:
        data = {"verified": False, "trace_hash": trace_hash, "message": "Trace not found"}
    else:
        trace = res.data[0]
        trace_data = {
            "trace_id": trace["id"], "agent_id": trace["agent_id"],
            "status": trace.get("status", ""), "category": trace.get("category", "other"),
        }
        cert = sign_trace(trace_data)
        data = {"verified": verify_signature(cert), "trace_hash": trace_hash,
                "agent_id": trace["agent_id"], "public_key": get_public_key_hex()}

    task = A2ATask(
        id=task_id, contextId=str(uuid.uuid4()),
        status=A2ATaskStatus(state=A2ATaskState.COMPLETED, timestamp=now),
        artifacts=[A2AArtifact(
            artifactId=str(uuid.uuid4()), name="Trace Verification",
            parts=[A2APart(data=data, mediaType="application/json")],
        )],
    )
    _task_store[task_id] = task.model_dump(exclude_none=True)
    return SendMessageResponse(task=task)


def _build_compliance_result(agent_id: str) -> SendMessageResponse:
    """Execute compliance skill."""
    report = get_compliance_report(agent_id)
    task_id = str(uuid.uuid4())
    now = _now_iso()

    if not report:
        data = {"found": False, "agent_id": agent_id, "message": "Agent not found"}
    else:
        data = report

    task = A2ATask(
        id=task_id, contextId=str(uuid.uuid4()),
        status=A2ATaskStatus(state=A2ATaskState.COMPLETED, timestamp=now),
        artifacts=[A2AArtifact(
            artifactId=str(uuid.uuid4()), name="Compliance Report",
            parts=[A2APart(data=data, mediaType="application/json")],
        )],
    )
    _task_store[task_id] = task.model_dump(exclude_none=True)
    return SendMessageResponse(task=task)


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
        if not isinstance(part, dict):
            continue
        if "text" in part and part["text"]:
            text_content += part["text"] + " "
        elif "data" in part:
            raw = part["data"]
            if isinstance(raw, str):
                try:
                    raw = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
            if not isinstance(raw, dict):
                continue
            d = raw
            if "agent_id" in d:
                text_content += f"check trust {d['agent_id']} "
            if "skill" in d or "action" in d:
                skill = d.get("skill") or d.get("action", "")
                text_content += f"{skill} "
            if "category" in d:
                text_content += f"{d['category']} "
            if "agent_ids" in d and isinstance(d["agent_ids"], list):
                text_content += "compare " + " ".join(str(i) for i in d["agent_ids"]) + " "

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

    elif intent == "leaderboard":
        response = _build_leaderboard_result(
            intent_params.get("category"),
            intent_params.get("limit", 5),
        )

    elif intent == "verify_trace":
        trace_hash = intent_params.get("trace_hash")
        if not trace_hash:
            return _jsonrpc_error(
                req_id, -32602, "InvalidParams",
                {"detail": "Provide a 64-character trace hash to verify."},
            )
        response = _build_verify_result(trace_hash)

    elif intent == "compliance":
        agent_id = intent_params.get("agent_id")
        if not agent_id:
            return _jsonrpc_error(
                req_id, -32602, "InvalidParams",
                {"detail": "Provide an agent ID for compliance check."},
            )
        response = _build_compliance_result(agent_id)

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
