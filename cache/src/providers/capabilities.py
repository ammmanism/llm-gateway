from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ProviderCapability:
    provider: str
    model: str
    aliases: tuple[str, ...]
    max_context_tokens: int
    supports_streaming: bool
    supports_tools: bool
    supports_json_mode: bool


CAPABILITIES: Dict[str, ProviderCapability] = {
    "gpt-4o": ProviderCapability("openai", "gpt-4o", ("gpt-4o-latest",), 128_000, False, True, True),
    "gpt-4o-mini": ProviderCapability("openai", "gpt-4o-mini", ("fast", "cheap-openai"), 128_000, False, True, True),
    "claude-sonnet-4": ProviderCapability("anthropic", "claude-sonnet-4", ("claude-4-sonnet",), 200_000, True, True, True),
    "claude-haiku-3.5": ProviderCapability("anthropic", "claude-haiku-3.5", ("haiku",), 200_000, True, True, True),
    "deepseek-v3": ProviderCapability("deepseek", "deepseek-v3", ("deepseek-chat",), 64_000, False, False, True),
    "llama-3.3-70b": ProviderCapability("groq", "llama-3.3-70b", ("llama-fast",), 128_000, False, True, True),
    "gemini-2.5-flash": ProviderCapability("gemini", "gemini-2.5-flash", ("gemini-flash",), 1_000_000, False, True, True),
}

ALIASES = {
    alias: capability.model
    for capability in CAPABILITIES.values()
    for alias in capability.aliases
}


def canonical_model(model: str) -> str:
    return ALIASES.get(model, model)


def capability_for_model(model: str) -> Optional[ProviderCapability]:
    return CAPABILITIES.get(canonical_model(model))


def model_for_provider(requested_model: str, provider_name: str, supported_models: list[str]) -> str:
    canonical = canonical_model(requested_model)
    if canonical in supported_models:
        return canonical

    capability = capability_for_model(canonical)
    if capability and capability.provider == provider_name and capability.model in supported_models:
        return capability.model

    return supported_models[0]


def provider_supports_request(
    provider_name: str,
    model: str,
    *,
    stream: bool,
    uses_tools: bool,
    uses_json_mode: bool,
) -> bool:
    capability = capability_for_model(model)
    if not capability:
        return True
    if capability.provider != provider_name:
        return True
    if stream and not capability.supports_streaming:
        return False
    if uses_tools and not capability.supports_tools:
        return False
    if uses_json_mode and not capability.supports_json_mode:
        return False
    return True
