from typing import List

FALLBACK_CHAINS = {
    "tier_a": ["openai", "anthropic", "deepseek"],
    "tier_b": ["groq", "gemini", "deepseek", "openai"],
    "explicit": [] # populated dynamically
}

def get_fallback_chain(tier: str, primary_provider: str) -> List[str]:
    """
    Get a list of providers to try if the primary fails.
    """
    chain = FALLBACK_CHAINS.get(tier, FALLBACK_CHAINS["tier_b"])
    # Put primary first, then others, avoiding duplicates
    result = [primary_provider]
    for p in chain:
        if p != primary_provider:
            result.append(p)
    return result
