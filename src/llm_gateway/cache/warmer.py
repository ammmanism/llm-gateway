import json

from llm_gateway.cache.semantic import semantic_cache
from llm_gateway.providers.factory import ProviderFactory
from llm_gateway.utils.tokenizer import count_tokens

get_provider = ProviderFactory.get_provider


async def warm_cache_from_jsonl(file_content: str, tenant_id: str) -> int:
    """
    Parse JSONL content and warm the cache.
    JSONL format: {"query": "...", "response": "...", "model": "...", "provider": "..."}
    Returns number of successfully cached entries.
    """
    count = 0
    lines = file_content.strip().split("\n")
    for line in lines:
        if not line.strip():
            continue
        try:
            data = json.loads(line)
            query = data.get("query")
            response = data.get("response")
            model = data.get("model", "gpt-4o")
            provider = data.get("provider", "openai")

            if not query or not response:
                continue

            # Wrap string responses in the standard chat-completion structure.
            if isinstance(response, str):
                response = {
                    "id": "chatcmpl-warmed",
                    "object": "chat.completion",
                    "choices": [
                        {
                            "index": 0,
                            "message": {"role": "assistant", "content": response},
                            "finish_reason": "stop",
                        }
                    ],
                }

            # Calculate tokens
            tokens_in = count_tokens(model, query)
            response_content = response["choices"][0]["message"]["content"]
            tokens_out = count_tokens(model, response_content)

            # Calculate cost
            cost = 0.0
            try:
                p_obj = get_provider(provider)
                cost = p_obj.calculate_cost(model, tokens_in, tokens_out)
            except Exception:
                pass

            # Store in cache
            await semantic_cache.store_cache(
                text=query,
                model=model,
                params={},
                response=response,
                tenant_id=tenant_id,
                provider=provider,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost,
                ttl_seconds=3600 * 24 * 30,  # Default 30 days for warmed cache
            )
            count += 1
        except Exception:
            pass
    return count
