from .base import BaseProvider, CompletionResponse
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .deepseek import DeepSeekProvider
from .groq import GroqProvider
from .gemini import GeminiProvider

PROVIDERS = {
    "openai": OpenAIProvider(),
    "anthropic": AnthropicProvider(),
    "deepseek": DeepSeekProvider(),
    "groq": GroqProvider(),
    "gemini": GeminiProvider()
}

def get_provider(name: str) -> BaseProvider:
    provider = PROVIDERS.get(name)
    if not provider:
        raise ValueError(f"Unknown provider: {name}")
    return provider