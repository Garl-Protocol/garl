from __future__ import annotations

from enum import Enum
from pydantic import BaseModel


class A2ATaskState(str, Enum):
    UNSPECIFIED = "TASK_STATE_UNSPECIFIED"
    SUBMITTED = "TASK_STATE_SUBMITTED"
    WORKING = "TASK_STATE_WORKING"
    COMPLETED = "TASK_STATE_COMPLETED"
    FAILED = "TASK_STATE_FAILED"
    CANCELED = "TASK_STATE_CANCELED"
    INPUT_REQUIRED = "TASK_STATE_INPUT_REQUIRED"
    AUTH_REQUIRED = "TASK_STATE_AUTH_REQUIRED"
    REJECTED = "TASK_STATE_REJECTED"


class A2AMessageRole(str, Enum):
    USER = "ROLE_USER"
    AGENT = "ROLE_AGENT"


class A2APart(BaseModel):
    text: str | None = None
    data: dict | None = None
    url: str | None = None
    raw: str | None = None
    filename: str | None = None
    mediaType: str | None = None


class A2AMessage(BaseModel):
    messageId: str
    role: A2AMessageRole
    parts: list[A2APart]
    contextId: str | None = None
    taskId: str | None = None
    metadata: dict | None = None
    extensions: list[str] | None = None


class A2ATaskStatus(BaseModel):
    state: A2ATaskState
    timestamp: str | None = None
    message: A2AMessage | None = None


class A2AArtifact(BaseModel):
    artifactId: str
    name: str | None = None
    description: str | None = None
    parts: list[A2APart]
    metadata: dict | None = None
    extensions: list[str] | None = None


class A2ATask(BaseModel):
    id: str
    contextId: str
    status: A2ATaskStatus
    artifacts: list[A2AArtifact] | None = None
    history: list[A2AMessage] | None = None
    metadata: dict | None = None


class SendMessageConfiguration(BaseModel):
    acceptedOutputModes: list[str] | None = None
    blocking: bool | None = None
    historyLength: int | None = None
    pushNotificationConfig: dict | None = None


class SendMessageRequest(BaseModel):
    message: A2AMessage
    configuration: SendMessageConfiguration | None = None


class SendMessageResponse(BaseModel):
    task: A2ATask | None = None
    message: A2AMessage | None = None


class GetTaskRequest(BaseModel):
    id: str
    historyLength: int | None = None


class JSONRPCRequest(BaseModel):
    jsonrpc: str = "2.0"
    method: str
    params: dict | None = None
    id: str | int


class JSONRPCResponse(BaseModel):
    jsonrpc: str = "2.0"
    result: dict | None = None
    error: dict | None = None
    id: str | int | None = None


class JSONRPCError(BaseModel):
    code: int
    message: str
    data: dict | None = None
