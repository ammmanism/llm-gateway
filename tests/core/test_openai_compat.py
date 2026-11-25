import pytest
from openai.types.chat import ChatCompletion, ChatCompletionChunk
from pydantic import ValidationError

from llm_gateway.core.openai_compat import (
    ChatCompletionRequest,
    OpenAIMessage,
    completion_response,
    flatten_messages,
    stream_chunk,
    stream_usage_chunk,
)


def test_request_parses_openai_fields_and_token_limit():
    request = ChatCompletionRequest(
        model="gpt-4o",
        messages=[{"role": "user", "content": "hello"}],
        max_completion_tokens=128,
        stream=True,
        stream_options={"include_usage": True},
    )

    assert request.effective_max_tokens == 128
    assert request.stream is True
    assert request.stream_options.include_usage is True


def test_request_rejects_unknown_role():
    with pytest.raises(ValidationError):
        ChatCompletionRequest(
            model="gpt-4o",
            messages=[{"role": "invalid", "content": "hello"}],
        )


def test_flatten_messages_preserves_role_boundaries():
    messages = [
        OpenAIMessage(role="system", content="be concise"),
        OpenAIMessage(role="user", content="hello"),
    ]

    assert flatten_messages(messages) == "[system]\nbe concise\n\n[user]\nhello"


def test_completion_response_is_accepted_by_openai_sdk():
    response = completion_response(
        {
            "output": "hi",
            "model": "gpt-4o",
            "provider": "openai",
            "prompt_tokens": 5,
            "completion_tokens": 2,
            "cost_usd": 0.0001,
            "latency_ms": 12.5,
        },
        "chatcmpl-test",
        "gpt-4o",
        created=123,
    )

    parsed = ChatCompletion.model_validate(response)

    assert parsed.id == "chatcmpl-test"
    assert parsed.created == 123
    assert parsed.choices[0].message.content == "hi"
    assert parsed.usage.total_tokens == 7


def test_stream_chunks_are_accepted_by_openai_sdk():
    role_chunk = stream_chunk("chatcmpl-test", "gpt-4o", role=True)
    content_chunk = stream_chunk("chatcmpl-test", "gpt-4o", content="hi")
    usage_chunk = stream_usage_chunk("chatcmpl-test", "gpt-4o", 5, 2)

    assert ChatCompletionChunk.model_validate(role_chunk).choices[0].delta.role == (
        "assistant"
    )
    assert ChatCompletionChunk.model_validate(content_chunk).choices[
        0
    ].delta.content == ("hi")
    parsed_usage = ChatCompletionChunk.model_validate(usage_chunk)
    assert parsed_usage.choices == []
    assert parsed_usage.usage.total_tokens == 7
