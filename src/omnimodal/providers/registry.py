"""
Provider Registry
"""

from typing import Dict, Type
from .openai import OpenAIProvider
from .anthropic import AnthropicProvider
from .google import GoogleProvider
from .stability import StabilityProvider
from .replicate import ReplicateProvider
from .huggingface import HuggingFaceProvider
from .aws_bedrock import AWSBedrockProvider
from .mistral import MistralProvider
from .local import LocalProvider

class ProviderRegistry:
    _providers = {}

    @classmethod
    def register(cls, name: str, provider_class: Type):
        cls._providers[name] = provider_class

    @classmethod
    def get(cls, name: str):
        return cls._providers.get(name)

# Auto-register
ProviderRegistry.register("openai", OpenAIProvider)
ProviderRegistry.register("anthropic", AnthropicProvider)
ProviderRegistry.register("google", GoogleProvider)
ProviderRegistry.register("stability", StabilityProvider)
ProviderRegistry.register("replicate", ReplicateProvider)
ProviderRegistry.register("huggingface", HuggingFaceProvider)
ProviderRegistry.register("aws_bedrock", AWSBedrockProvider)
ProviderRegistry.register("mistral", MistralProvider)
ProviderRegistry.register("local", LocalProvider)
