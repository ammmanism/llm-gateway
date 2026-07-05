import asyncio
import time
import logging
import math
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ConcurrencyWindow:
    provider: str
    current_limit: int = 10
    min_limit: int = 1
    max_limit: int = 1000
    additive_increment: int = 1
    multiplicative_decrease: float = 0.5
    in_flight: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_adjustment: float = field(default_factory=time.time)
    smoothed_rtt: float = 0.5
    rtt_var: float = 0.1
    total_requests: int = 0
    total_rejected: int = 0


class AdaptiveConcurrencyLimiter:
    def __init__(self):
        self.windows: Dict[str, ConcurrencyWindow] = {}
        self.locks: Dict[str, asyncio.Lock] = {}

    def _get_window(self, provider: str) -> ConcurrencyWindow:
        if provider not in self.windows:
            self.windows[provider] = ConcurrencyWindow(provider=provider)
            self.locks[provider] = asyncio.Lock()
        return self.windows[provider]

    async def acquire(self, provider: str, timeout: Optional[float] = None) -> bool:
        window = self._get_window(provider)
        async with self.locks[provider]:
            if window.in_flight >= window.current_limit:
                window.total_rejected += 1
                return False
            window.in_flight += 1
            window.total_requests += 1
            return True

    async def wait_and_acquire(
        self,
        provider: str,
        max_wait_seconds: float = 30.0
    ) -> bool:
        window = self._get_window(provider)
        start = time.time()
        timeout = min(max_wait_seconds, window.smoothed_rtt * 3)

        while time.time() - start < timeout:
            if await self.acquire(provider):
                return True
            await asyncio.sleep(window.smoothed_rtt / 10)
        return False

    def release(self, provider: str, success: bool, latency_ms: float):
        window = self._get_window(provider)

        async def _update():
            async with self.locks[provider]:
                window.in_flight = max(0, window.in_flight - 1)
                rtt = latency_ms / 1000.0
                if window.smoothed_rtt == 0:
                    window.smoothed_rtt = rtt
                else:
                    alpha = 0.875
                    window.smoothed_rtt = alpha * window.smoothed_rtt + (1 - alpha) * rtt

                if success:
                    window.success_count += 1
                    if window.success_count % 10 == 0:
                        window.current_limit = min(
                            window.max_limit,
                            window.current_limit + window.additive_increment
                        )
                        logger.info(
                            "%s: Window increased to %d (RTT: %.3fs)",
                            provider, window.current_limit, window.smoothed_rtt
                        )
                else:
                    window.failure_count += 1
                    old_limit = window.current_limit
                    window.current_limit = max(
                        window.min_limit,
                        math.floor(window.current_limit * window.multiplicative_decrease)
                    )
                    window.success_count = 0
                    logger.warning(
                        "%s: Window decreased %d -> %d (failure)",
                        provider, old_limit, window.current_limit
                    )

        asyncio.create_task(_update())

    def handle_rate_limit(self, provider: str, retry_after: Optional[float] = None):
        window = self._get_window(provider)

        async def _backoff():
            async with self.locks[provider]:
                old_limit = window.current_limit
                window.current_limit = max(1, window.current_limit // 4)
                window.success_count = 0
                backoff = retry_after or window.smoothed_rtt * 2
                logger.warning(
                    "%s: Rate limited! Window %d -> %d, backoff %.1fs",
                    provider, old_limit, window.current_limit, backoff
                )
                original_max = window.max_limit
                window.max_limit = window.current_limit
                await asyncio.sleep(backoff)
                window.max_limit = original_max

        asyncio.create_task(_backoff())

    def get_stats(self) -> Dict[str, Dict]:
        return {
            name: {
                "limit": w.current_limit,
                "in_flight": w.in_flight,
                "rtt": round(w.smoothed_rtt, 3),
                "success_rate": w.success_count / max(w.total_requests, 1),
                "rejection_rate": w.total_rejected / max(w.total_requests, 1)
            }
            for name, w in self.windows.items()
        }

    _base_backoff: float = 0.1
    _max_backoff: float = 10.0

    async def _adaptive_backoff(self, attempt: int) -> float:
        load = self.current_load
        factor = 1.0 + (load / max(1, self.max_concurrent))
        delay = min(self._base_backoff * (2 ** attempt) * factor, self._max_backoff)
        await asyncio.sleep(delay)
        return delay
