from llm_gateway.utils.tokenizer import count_message_tokens, count_tokens


def test_count_tokens_openai():
    # Test valid OpenAI model
    text = "Hello, world!"
    # "Hello", ",", " world", "!" -> 4 tokens in cl100k_base
    assert count_tokens("gpt-4o", text) == 4
    assert count_tokens("gpt-3.5-turbo", text) == 4

def test_count_tokens_fallback():
    # Test unknown model falls back to cl100k_base
    text = "Hello, world!"
    assert count_tokens("invalid-model-name", text) == 4

    # Empty string should return 0
    assert count_tokens("gpt-4o", "") == 0
    assert count_tokens("gpt-4o", None) == 0

def test_count_message_tokens():
    messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ]
    # Estimate message tokens
    tokens = count_message_tokens("gpt-4o", messages)
    assert tokens > 0
    # Ensure it's close to standard (e.g. system=11 tokens, user=2 tokens, plus formatting metadata)
    assert 15 <= tokens <= 25

def test_count_message_tokens_empty():
    assert count_message_tokens("gpt-4o", []) == 0
    assert count_message_tokens("gpt-4o", None) == 0
