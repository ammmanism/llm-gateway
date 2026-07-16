"""
Fallback Chain & Circuit Breaker
"""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..config import settings
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)


@dataclass
class FallbackResult:
    content: str
    provider: str
    model: str
    cost: float
    from_cache: bool
    fallback_used: bool
    latency_ms: int
    attempts: int
    mime_type: str = "text/plain"


class FallbackChain:
    """
    Orchestrates fallback across multiple providers.
    """

    def __init__(self):
        self.circuit_breakers: dict[str, CircuitBreaker] = {}
        self.fallback_chains = {
            "text": ["openai", "anthropic", "google", "huggingface", "local"],
            "image": ["openai", "stability", "google", "local"],
            "audio": ["openai", "google", "local"],
            "video": ["replicate", "google", "local"],
        }
        self.degradation_map = {
            "video": "image",
            "image": "text",
        }

    def _get_circuit(self, provider: str) -> CircuitBreaker:
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = CircuitBreaker(
                failure_threshold=settings.routing.circuit_breaker_threshold,
                recovery_timeout=settings.routing.circuit_breaker_timeout_seconds,
            )
        return self.circuit_breakers[provider]

    async def execute(
        self,
        primary: Any,
        operation: Callable,
        max_attempts: int = 3,
        timeout: float = 30.0,
    ) -> FallbackResult:
        """
        Execute operation with fallback chain.
        """
        providers = self.fallback_chains.get(primary.modality, [primary.provider])
        start_time = time.time()

        last_error = None
        for attempt, provider in enumerate(providers[:max_attempts]):
            circuit = self._get_circuit(provider)

            if not circuit.can_execute():
                logger.warning(f"Circuit open for {provider}, skipping")
                continue

            try:
                # Execute with timeout
                result = await asyncio.wait_for(operation(provider), timeout=timeout)

                circuit.record_success()
                logger.info(f"Success with {provider} after {attempt+1} attempts")

                return FallbackResult(
                    content=result.content,
                    provider=provider,
                    model=result.model,
                    cost=result.cost,
                    from_cache=getattr(result, "from_cache", False),
                    fallback_used=(attempt > 0),
                    latency_ms=int((time.time() - start_time) * 1000),
                    attempts=attempt + 1,
                    mime_type=getattr(result, "mime_type", "text/plain"),
                )

            except TimeoutError:
                circuit.record_failure()
                last_error = f"Timeout on {provider}"
                logger.warning(f"Timeout on {provider}")
            except Exception as e:
                circuit.record_failure()
                last_error = str(e)
                logger.warning(f"Error on {provider}: {e}")

        # All providers failed — attempt graceful degradation
        return await self._degrade(primary, operation, last_error)

    async def _degrade(
        self, primary: Any, operation: Callable, error: str
    ) -> FallbackResult:
        modality = getattr(primary, "modality", "text")

        if modality in self.degradation_map:
            simpler = self.degradation_map[modality]
            logger.warning(
                f"Degrading from {modality} to {simpler} due to error: {error}"
            )
            return FallbackResult(
                content=f"[DEGRADED to {simpler}] {error}",
                provider="degradation",
                model="none",
                cost=0.0,
                from_cache=False,
                fallback_used=True,
                latency_ms=0,
                attempts=0,
                mime_type="text/plain",
            )

        # Final fallback: queue for async retry
        return FallbackResult(
            content=f"[QUEUED for retry] {error}",
            provider="queue",
            model="none",
            cost=0.0,
            from_cache=False,
            fallback_used=True,
            latency_ms=0,
            attempts=0,
            mime_type="text/plain",
        )

    def get_health_status(self) -> dict[str, str]:
        return {
            provider: cb.state.name for provider, cb in self.circuit_breakers.items()
        }
