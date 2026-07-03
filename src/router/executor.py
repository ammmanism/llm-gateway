import asyncio
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import httpx

from src.config import settings
from src.providers import get_provider
from src.providers.base import CompletionResponse
from src.providers.capabilities import model_for_provider, provider_supports_request
from src.router.smart_router import smart_router
from src.observability.metrics import PROVIDER_FAILURES
from src.utils.logger import get_logger

logger = get_logger(__name__)


class ProviderExecutionError(Exception):
    def __init__(self, provider: str, error_type: str, message: str):
        super().__init__(message)
        self.provider = provider
        self.error_type = error_type


@dataclass
class ProviderAttempt:
    provider: str
    model: str
    status: str
    error_type: Optional[str] = None
    message: Optional[str] = None


@dataclass
class FallbackResult:
    response: CompletionResponse
    provider: str
    model: str
    attempts: List[ProviderAttempt]


def classify_provider_error(error: Exception) -> str:
    if isinstance(error, asyncio.TimeoutError):
        return "timeout"
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.HTTPStatusError):
        status = error.response.status_code
        if status == 429:
            return "rate_limited"
        if 500 <= status <= 599:
            return "provider_5xx"
        if 400 <= status <= 499:
            return "provider_4xx"
    if isinstance(error, httpx.TransportError):
        return "network"
    if isinstance(error, NotImplementedError):
        return "unsupported"
    return "unknown"


def _eligible_chain(
    chain: Iterable[str],
    requested_model: str,
    *,
    stream: bool,
    uses_tools: bool,
    uses_json_mode: bool,
) -> List[str]:
    eligible = []
    for provider_name in chain:
        provider = get_provider(provider_name)
        provider_model = model_for_provider(requested_model, provider_name, provider.supported_models)
        if provider_supports_request(
            provider_name,
            provider_model,
            stream=stream,
            uses_tools=uses_tools,
            uses_json_mode=uses_json_mode,
        ):
            eligible.append(provider_name)
    return eligible


async def complete_with_fallback(
    chain: Iterable[str],
    requested_model: str,
    messages: list[Dict[str, Any]],
    params: Dict[str, Any],
    *,
    stream: bool = False,
    uses_tools: bool = False,
    uses_json_mode: bool = False,
) -> FallbackResult:
    attempts: List[ProviderAttempt] = []
    eligible_chain = _eligible_chain(
        chain,
        requested_model,
        stream=stream,
        uses_tools=uses_tools,
        uses_json_mode=uses_json_mode,
    )

    for provider_name in eligible_chain[: settings.MAX_FALLBACK_ATTEMPTS]:
        provider = get_provider(provider_name)
        provider_model = model_for_provider(requested_model, provider_name, provider.supported_models)
        timeout = settings.PROVIDER_TIMEOUT_SECONDS if not attempts else settings.PROVIDER_FALLBACK_TIMEOUT_SECONDS

        try:
            response = await asyncio.wait_for(
                provider.complete(provider_model, messages, params),
                timeout=timeout,
            )
            smart_router.providers[provider_name].circuit.record_success()
            smart_router.providers[provider_name].ewma_latency.update(response.latency_ms)
            smart_router.providers[provider_name].ewma_error_rate.update(0.0)
            attempts.append(ProviderAttempt(provider_name, provider_model, "success"))
            return FallbackResult(response, provider_name, provider_model, attempts)
        except Exception as exc:
            error_type = classify_provider_error(exc)
            logger.warning("Provider %s failed with %s: %s", provider_name, error_type, exc)
            PROVIDER_FAILURES.labels(provider=provider_name, error_type=error_type).inc()
            smart_router.providers[provider_name].circuit.record_failure()
            smart_router.providers[provider_name].ewma_error_rate.update(1.0)
            attempts.append(ProviderAttempt(provider_name, provider_model, "failed", error_type, str(exc)))

    if not attempts:
        raise ProviderExecutionError("none", "unsupported", "No providers support this request")

    last = attempts[-1]
    raise ProviderExecutionError(last.provider, last.error_type or "unknown", last.message or "All providers failed")
