from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool", "function"]
    content: Any = ""
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

    model_config = ConfigDict(extra="allow")


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o"
    messages: List[ChatMessage] = Field(default_factory=list)
    stream: bool = False
    max_tokens: Optional[int] = Field(default=None, gt=0)
    temperature: Optional[float] = Field(default=None, ge=0, le=2)
    top_p: Optional[float] = Field(default=None, ge=0, le=1)
    presence_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    frequency_penalty: Optional[float] = Field(default=None, ge=-2, le=2)
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Any] = None
    response_format: Optional[Dict[str, Any]] = None
    user: Optional[str] = None

    model_config = ConfigDict(extra="allow")

    @model_validator(mode="after")
    def validate_messages(self) -> "ChatCompletionRequest":
        if not self.messages:
            raise ValueError("messages must contain at least one chat message")
        return self

    def provider_params(self) -> Dict[str, Any]:
        excluded = {"model", "messages", "stream"}
        return self.model_dump(exclude_none=True, exclude=excluded)

    def as_provider_messages(self) -> List[Dict[str, Any]]:
        return [message.model_dump(exclude_none=True) for message in self.messages]

    def last_user_text(self) -> str:
        for message in reversed(self.messages):
            if message.role == "user":
                content = message.content
                if isinstance(content, str):
                    return content
                return str(content)
        return ""
