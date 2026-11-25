"""OpenAI-compatible chat schemas and response shaping."""

import time
import uuid
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OpenAIMessage(BaseModel):
    role: str
    content: str
    name: Optional[str] = None


class StreamOptions(BaseModel):
    include_usage: bool = False


class ChatCompletionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    model: str
    messages: list[OpenAIMessage] = Field(min_length=1)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(default=1024, ge=1, le=128000)
    max_completion_tokens: Optional[int] = Field(default=None, ge=1, le=128000)
    stream: bool = False
    user: Optional[str] = None
    stream_options: Optional[StreamOptions] = None

    @field_validator("messages")
    @classmethod
    def validate_roles(cls, messages):
        allowed = {"system", "user", "assistant", "tool", "developer"}
        invalid = [message.role for message in messages if message.role not in allowed]
        if invalid:
            raise ValueError(f"unsupported message role: {invalid[0]}")
        return messages

    @property
    def effective_max_tokens(self) -> int:
        return self.max_completion_tokens or self.max_tokens or 1024


def flatten_messages(messages: list[OpenAIMessage]) -> str:
    """Preserve role boundaries without firewall-sensitive role prefixes."""
    return "\n\n".join(f"[{message.role}]\n{message.content}" for message in messages)


def completion_id() -> str:
    return f"chatcmpl-{uuid.uuid4().hex}"


def completion_response(
    result: dict[str, Any],
    request_id: str,
    model: str,
    *,
    created: Optional[int] = None,
) -> dict[str, Any]:
    prompt_tokens = int(result.get("prompt_tokens", 0))
    completion_tokens = int(result.get("completion_tokens", 0))
    return {
        "id": request_id,
        "object": "chat.completion",
        "created": created or int(time.time()),
        "model": result.get("model", model),
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": result["output"]},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "x_gateway": {
            "provider": result.get("provider"),
            "cache_hit": bool(result.get("cache_hit", False)),
            "cache_tier": result.get("cache_tier"),
            "cost_usd": float(result.get("cost_usd", 0.0)),
            "latency_ms": float(result.get("latency_ms", 0.0)),
            "mock": bool(result.get("mock", False)),
        },
    }


def stream_chunk(
    request_id: str,
    model: str,
    content: Optional[str] = None,
    *,
    role: bool = False,
    finish_reason: Optional[str] = None,
    created: Optional[int] = None,
) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if role:
        delta["role"] = "assistant"
    if content is not None:
        delta["content"] = content
    return {
        "id": request_id,
        "object": "chat.completion.chunk",
        "created": created or int(time.time()),
        "model": model,
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }


def stream_usage_chunk(
    request_id: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    *,
    created: Optional[int] = None,
) -> dict[str, Any]:
    chunk = stream_chunk(request_id, model, created=created)
    chunk["choices"] = []
    chunk["usage"] = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    return chunk


def stream_error_chunk(request_id: str, model: str, message: str) -> dict[str, Any]:
    chunk = stream_chunk(request_id, model)
    chunk["error"] = {"message": message, "type": "gateway_error"}
    return chunk
