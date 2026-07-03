"""
Provider Registry
Maintains list of available provider configurations.
"""

from typing import Dict, Any


class ProviderRegistry:
    """
    Registry for modality adapters and providers.
    """
    
    def __init__(self):
        self.providers: Dict[str, Any] = {}

    def register(self, provider: Any):
        """Register a provider adapter."""
        self.providers[provider.name] = provider

    def get(self, name: str) -> Any:
        """Retrieve registered provider."""
        return self.providers.get(name)
