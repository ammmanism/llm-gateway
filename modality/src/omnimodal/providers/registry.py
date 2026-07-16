"""
Provider Registry
"""

from .anthropic import AnthropicProvider
from .aws_bedrock import AWSBedrockProvider
from .google import GoogleProvider
from .huggingface import HuggingFaceProvider
from .local import LocalProvider
from .mistral import MistralProvider
from .openai import OpenAIProvider
from .replicate import ReplicateProvider
from .stability import StabilityProvider


class ProviderRegistry:
    _providers = {}

    @classmethod
    def register(cls, name: str, provider_class: type):
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
