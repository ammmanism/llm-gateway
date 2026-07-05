"""
Semantic Router
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
import time

from ..config import settings, ProviderConfig
from ..exceptions import ProviderError
from ..core.deduplication import RequestCoalescer
from ..core.concurrency import AdaptiveConcurrencyLimiter
from .circuit_breaker import CircuitBreaker, CircuitState

logger = logging.getLogger(__name__)

class QualityTier(Enum):
    DRAFT = "draft"
    STANDARD = "standard"
    PREMIUM = "premium"
    ENTERPRISE = "enterprise"

@dataclass
class RouteDecision:
    provider: str
    model: str
    estimated_cost: float
    estimated_latency_ms: int
    quality_score: float
    confidence: float
    modality: str = "text"

class SemanticRouter:
    """
    The brain of OmniModal. Uses multi-objective optimization.
    """

    def __init__(self):
        self.provider_scores: Dict[str, Dict[str, float]] = {}
        self.quality_matrix = self._init_quality_matrix()
        self.latency_estimates = self._init_latency_estimates()
        self.cost_models = self._init_cost_models()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.coalescer: Optional[RequestCoalescer] = None
        self.concurrency_limiter: Optional[AdaptiveConcurrencyLimiter] = None
        self.load_weights()

    def _init_quality_matrix(self) -> Dict[str, Dict[str, float]]:
        return {
            "openai": {"text": 9.5, "image": 8.5, "audio": 9.0, "video": 0.0},
            "anthropic": {"text": 9.3, "image": 0.0, "audio": 0.0, "video": 0.0},
            "google": {"text": 8.8, "image": 8.0, "audio": 7.5, "video": 8.5},
            "stability": {"text": 0.0, "image": 7.5, "audio": 0.0, "video": 0.0},
            "replicate": {"text": 0.0, "image": 0.0, "audio": 0.0, "video": 8.0},
            "local": {"text": 6.5, "image": 5.0, "audio": 0.0, "video": 0.0},
            "huggingface": {"text": 7.0, "image": 7.0, "audio": 6.0, "video": 0.0},
            "aws_bedrock": {"text": 8.5, "image": 0.0, "audio": 0.0, "video": 0.0},
            "mistral": {"text": 8.0, "image": 0.0, "audio": 0.0, "video": 0.0},
        }

    def _init_latency_estimates(self) -> Dict[str, int]:
        return {
            "openai": 800,
            "anthropic": 1200,
            "google": 1000,
            "stability": 5000,
            "replicate": 15000,
            "local": 50,
            "huggingface": 1200,
            "aws_bedrock": 900,
            "mistral": 700,
        }

    def _init_cost_models(self) -> Dict[str, Dict]:
        return {
            "openai": {"text_input": 0.005, "text_output": 0.015, "image": 0.04, "audio": 0.006},
            "anthropic": {"text_input": 0.015, "text_output": 0.075},
            "google": {"text_input": 0.0005, "text_output": 0.0015, "image": 0.02},
            "stability": {"image": 0.01},
            "replicate": {"video": 0.05},
            "local": {"text_input": 0.0, "text_output": 0.0},
            "huggingface": {"text_input": 0.0001, "text_output": 0.0002},
            "aws_bedrock": {"text_input": 0.001, "text_output": 0.002},
            "mistral": {"text_input": 0.0003, "text_output": 0.001},
        }

    def load_weights(self):
        """Load custom provider weights from config."""
        # Implementation would parse provider_weights.yaml and adjust matrices
        pass

    async def warmup(self):
        if settings.core.enable_deduplication:
            self.coalescer = RequestCoalescer(
                exact_ttl_seconds=settings.core.dedup_exact_ttl_seconds,
                semantic_ttl_seconds=settings.core.dedup_semantic_ttl_seconds,
                max_batch_size=settings.core.dedup_max_batch_size
            )
        if settings.core.enable_concurrency_limiting:
            self.concurrency_limiter = AdaptiveConcurrencyLimiter()
        await asyncio.sleep(0.1)

    def _get_circuit(self, provider: str) -> CircuitBreaker:
        if provider not in self.circuit_breakers:
            self.circuit_breakers[provider] = CircuitBreaker(
                failure_threshold=settings.routing.circuit_breaker_threshold,
                recovery_timeout=settings.routing.circuit_breaker_timeout_seconds
            )
        return self.circuit_breakers[provider]

    async def select(
        self,
        modality: str,
        quality: str = "standard",
        cost_budget: Optional[float] = None,
        latency_budget: Optional[int] = None,
        task_complexity: int = 5,
        prompt: Optional[str] = None,
        params: Optional[Dict] = None,
    ) -> RouteDecision:
        if self.coalescer and prompt:
            cached = self.coalescer.exact_inflight.get(
                self.coalescer._hash_request(modality, prompt, params or {})
            )
            if cached:
                logger.info("Reusing inflight request for %s", prompt[:50])

        if self.concurrency_limiter:
            acquired = await self.concurrency_limiter.wait_and_acquire(modality)
            if not acquired:
                logger.warning("Concurrency limit reached for %s, proceeding anyway", modality)

        candidates = self._get_candidates(modality)

        # Filter by budget
        if cost_budget:
            candidates = [c for c in candidates
                         if self._estimate_cost(c, modality) <= cost_budget]

        if latency_budget:
            candidates = [c for c in candidates
                         if self.latency_estimates.get(c, 99999) <= latency_budget]

        # Quality threshold
        min_quality = self._quality_threshold(quality)
        quality_candidates = [c for c in candidates
                             if self.quality_matrix.get(c, {}).get(modality, 0) >= min_quality]

        if quality_candidates:
            candidates = quality_candidates
        elif not candidates:
            # Fallback to any available provider if budget filters wiped out all candidates
            candidates = self._get_candidates(modality, ignore_quality=True)
            if cost_budget:
                candidates.sort(key=lambda c: self._estimate_cost(c, modality))
            elif latency_budget:
                candidates.sort(key=lambda c: self.latency_estimates.get(c, 99999))

        # Score each candidate
        scored = []
        for provider in candidates:
            # Skip if circuit is open
            cb = self._get_circuit(provider)
            if not cb.can_execute():
                continue

            quality_score = self.quality_matrix[provider].get(modality, 0)
            cost = self._estimate_cost(provider, modality, task_complexity)
            latency = self.latency_estimates.get(provider, 1000)
            reliability = self._reliability_score(provider)

            # Multi-objective score
            score = (
                0.4 * (quality_score / 10) +
                0.3 * (1 - min(cost / 0.1, 1)) +
                0.2 * (1 - min(latency / 5000, 1)) +
                0.1 * reliability
            )

            scored.append((provider, score, quality_score, cost, latency))

        if not scored:
            raise ProviderError("No available providers")

        scored.sort(key=lambda x: x[1], reverse=True)
        best = scored[0]

        return RouteDecision(
            provider=best[0],
            model=self._default_model(best[0], modality),
            estimated_cost=best[3],
            estimated_latency_ms=best[4],
            quality_score=best[2],
            confidence=best[1],
            modality=modality
        )

    def _get_candidates(self, modality: str, ignore_quality: bool = False) -> List[str]:
        candidates = []
        for provider, scores in self.quality_matrix.items():
            if scores.get(modality, 0) > 0 or ignore_quality:
                if settings.providers.get(provider, ProviderConfig(name=provider, api_key_env="DUMMY")).enabled:
                    candidates.append(provider)
        return candidates

    def _estimate_cost(self, provider: str, modality: str, complexity: int = 5) -> float:
        model = self.cost_models.get(provider, {})
        base = model.get(modality) or model.get(f"{modality}_input") or model.get(f"{modality}_output") or 0.01
        return base * (1 + (complexity - 5) * 0.1)

    def _quality_threshold(self, tier: str) -> float:
        thresholds = {
            "draft": 5.0,
            "standard": 7.0,
            "premium": 8.5,
            "enterprise": 9.0
        }
        return thresholds.get(tier, 7.0)

    def _reliability_score(self, provider: str) -> float:
        # In production: query metrics from Prometheus
        return 0.98

    def _default_model(self, provider: str, modality: str) -> str:
        defaults = {
            "openai": {"text": "gpt-4o", "image": "dall-e-3", "audio": "whisper-1"},
            "anthropic": {"text": "claude-3-opus"},
            "google": {"text": "gemini-pro", "image": "gemini-pro-vision"},
            "stability": {"image": "stable-diffusion-3"},
            "replicate": {"video": "stable-video-diffusion"},
            "local": {"text": "llama-3-70b"},
            "huggingface": {"text": "meta-llama/Llama-2-70b-chat-hf"},
            "aws_bedrock": {"text": "amazon.titan-tg1-large"},
            "mistral": {"text": "mistral-large-latest"},
        }
        return defaults.get(provider, {}).get(modality, "unknown")

    def update_circuit_state(self, provider: str, state: str):
        cb = self._get_circuit(provider)
        if state == "OPEN":
            cb.state = CircuitState.OPEN
            cb.last_failure_time = time.time()
        elif state == "CLOSED":
            cb.state = CircuitState.CLOSED
        elif state == "HALF_OPEN":
            cb.state = CircuitState.HALF_OPEN

    def get_coalescer_stats(self) -> Dict:
        if self.coalescer:
            return self.coalescer.get_stats()
        return {}

    def get_concurrency_stats(self) -> Dict:
        if self.concurrency_limiter:
            return self.concurrency_limiter.get_stats()
        return {}
