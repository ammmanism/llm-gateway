from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from pydantic import BaseModel

class CompletionResponse(BaseModel):
    provider: str
    model: str
    response: Dict[str, Any]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    latency_ms: int

class BaseProvider(ABC):
    
    @property
    @abstractmethod
    def name(self) -> str:
        pass
        
    @property
    @abstractmethod
    def supported_models(self) -> list[str]:
        pass

    @abstractmethod
    async def complete(self, model: str, messages: list[Dict[str, Any]], params: Dict[str, Any]) -> CompletionResponse:
        """
        Execute a chat completion request against the provider.
        """
        pass
        
    @abstractmethod
    async def health_check(self) -> bool:
        """
        Verify provider connectivity and API key.
        """
        pass
        
    def calculate_cost(self, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate the cost based on pricing matrix."""
        # This will be overridden by subclasses
        return 0.0
