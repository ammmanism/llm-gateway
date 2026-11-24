from typing import Any, Dict, Tuple


def extract_token_usage(
    result: Dict[str, Any],
    prompt: str,
    output: str,
) -> Tuple[int, int, str]:
    """Normalize provider usage, falling back to explicit whitespace estimates."""
    usage = result.get("usage") or {}
    tokens = result.get("tokens") or {}

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")

    if prompt_tokens is None:
        prompt_tokens = usage.get("input_tokens")
    if completion_tokens is None:
        completion_tokens = usage.get("output_tokens")
    if prompt_tokens is None:
        prompt_tokens = tokens.get("prompt")
    if completion_tokens is None:
        completion_tokens = tokens.get("completion")

    if prompt_tokens is not None and completion_tokens is not None:
        return int(prompt_tokens), int(completion_tokens), "provider"

    return (
        len(prompt.split()),
        len(output.split()),
        "estimated",
    )
