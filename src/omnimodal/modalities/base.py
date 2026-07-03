"""
Base Modality Adapter
Unified abstract interface for all modality adapters.
"""

from abc import ABC, abstractmethod
from typing import Any, List, Dict, Union


class BaseModalityAdapter(ABC):
    """
    Base abstract class for provider adapters.
    """
    
    @abstractmethod
    async def generate(self, inputs: List[Any], provider: str, **kwargs) -> Any:
        """Generate content based on inputs."""
        pass
    
    @abstractmethod
    async def close(self) -> None:
        """Release connection pools and clients."""
        pass
