"""
Base Modality Adapter
"""

from abc import ABC, abstractmethod
from typing import List, Any, Optional
from dataclasses import dataclass

@dataclass
class ModalityResponse:
    content: Any
    mime_type: str
    model: str
    provider: str
    cost: float
    from_cache: bool = False

class BaseModalityAdapter(ABC):
    """Abstract base class for all modality adapters."""

    @abstractmethod
    async def generate(self, inputs: List[Any], provider: str = "openai", **kwargs) -> ModalityResponse:
        """Generate output from inputs."""
        pass

    @abstractmethod
    async def generate_stream(self, inputs: List[Any], **kwargs):
        """Stream generation."""
        pass

    @abstractmethod
    async def close(self):
        """Cleanup resources."""
        pass
