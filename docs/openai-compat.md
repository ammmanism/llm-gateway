# OpenAI-compatible API

`POST /v1/chat/completions` accepts the OpenAI chat-completion request shape and
returns OpenAI-compatible responses.

```python
import os
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8000/v1",
    api_key=os.environ["GATEWAY_API_KEY"],
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain vector databases"}],
)
print(response.choices[0].message.content)
```

## Streaming

Set `stream=True`. The gateway emits:

1. an initial assistant-role chunk,
2. content chunks,
3. a final `finish_reason="stop"` chunk,
4. a usage chunk,
5. `data: [DONE]`.

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Explain vector databases"}],
    stream=True,
    stream_options={"include_usage": True},
)
for chunk in stream:
    if chunk.choices and chunk.choices[0].delta.content:
        print(chunk.choices[0].delta.content, end="")
```

Both OpenAI streaming and the legacy `/generate/stream` endpoint use the same
accounted pipeline: per-key rate/budget reservations, tiktoken usage estimates,
cost reconciliation, ledger writes, metrics, and cleanup on failure/disconnect.

## Compatibility scope

- Text `system`, `developer`, `user`, `assistant`, and `tool` roles are accepted.
- Messages are flattened into role-delimited prompt text because provider
  adapters currently accept a single prompt string.
- Tool calling, structured outputs, image inputs, and logprobs are not adapted.
- Unknown OpenAI request fields are ignored for forward compatibility.

Evidence: `data/evidence/streaming_accounting.csv` compares 20 non-streaming and
20 streaming requests with identical token/cost accounting.
