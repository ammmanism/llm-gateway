import asyncio
import hashlib
import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class InFlightRequest:
    future: asyncio.Future
    timestamp: float
    request_hash: str
    modality: str


class RequestCoalescer:
    def __init__(
        self,
        exact_ttl_seconds: float = 30.0,
        semantic_ttl_seconds: float = 5.0,
        max_batch_size: int = 10,
    ):
        self.exact_inflight: dict[str, InFlightRequest] = {}
        self.semantic_inflight: dict[str, asyncio.Future] = {}
        self.batch_queues: dict[str, list] = defaultdict(list)
        self.batch_timers: dict[str, asyncio.Task | None] = {}

        self.exact_ttl = exact_ttl_seconds
        self.semantic_ttl = semantic_ttl_seconds
        self.max_batch_size = max_batch_size

        self.coalesced_count = 0
        self.batched_count = 0

    def _hash_request(self, modality: str, prompt: str, params: dict) -> str:
        key = f"{modality}:{prompt}:{sorted(params.items())}"
        return hashlib.sha256(key.encode()).hexdigest()[:16]

    def _semantic_hash(self, modality: str, prompt: str) -> str:
        words = prompt.lower().split()[:5]
        return f"{modality}:{'_'.join(words)}:{len(prompt)}"

    async def execute_or_wait(
        self,
        modality: str,
        prompt: str,
        params: dict,
        executor: Callable,
        priority: int = 0,
        use_semantic: bool = True,
    ) -> Any:
        request_hash = self._hash_request(modality, prompt, params)

        if request_hash in self.exact_inflight:
            inflight = self.exact_inflight[request_hash]
            self.coalesced_count += 1
            logger.info("Coalescing exact match: %s", request_hash[:8])
            return await inflight.future

        if use_semantic:
            semantic_hash = self._semantic_hash(modality, prompt)
            if semantic_hash in self.semantic_inflight:
                self.coalesced_count += 1
                logger.info("Coalescing semantic match: %s", semantic_hash)
                return await self.semantic_inflight[semantic_hash]

        future = asyncio.get_event_loop().create_future()
        inflight = InFlightRequest(
            future=future,
            timestamp=asyncio.get_event_loop().time(),
            request_hash=request_hash,
            modality=modality,
        )
        self.exact_inflight[request_hash] = inflight

        semantic_future = None
        if use_semantic:
            semantic_hash = self._semantic_hash(modality, prompt)
            self.semantic_inflight[semantic_hash] = future
            semantic_future = semantic_hash

        try:
            result = await executor()
            future.set_result(result)
            return result
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            asyncio.create_task(
                self._cleanup_after_ttl(request_hash, semantic_future, self.exact_ttl)
            )

    async def _cleanup_after_ttl(
        self, exact_hash: str, semantic_hash: str | None, ttl: float
    ):
        await asyncio.sleep(ttl)
        self.exact_inflight.pop(exact_hash, None)
        if semantic_hash:
            self.semantic_inflight.pop(semantic_hash, None)

    async def execute_batched(
        self,
        batch_key: str,
        request: dict,
        batch_executor: Callable[[list], list],
        max_wait_ms: float = 50.0,
    ) -> Any:
        queue = self.batch_queues[batch_key]
        future = asyncio.get_event_loop().create_future()
        queue.append((request, future))

        if batch_key not in self.batch_timers or self.batch_timers[batch_key] is None:
            self.batch_timers[batch_key] = asyncio.create_task(
                self._batch_flush(batch_key, batch_executor, max_wait_ms)
            )

        if len(queue) >= self.max_batch_size:
            timer = self.batch_timers.get(batch_key)
            if timer and not timer.done():
                timer.cancel()
            await self._batch_flush(batch_key, batch_executor, 0)

        return await future

    async def _batch_flush(
        self, batch_key: str, batch_executor: Callable, max_wait_ms: float
    ):
        if max_wait_ms > 0:
            await asyncio.sleep(max_wait_ms / 1000)

        queue = self.batch_queues[batch_key]
        if not queue:
            self.batch_timers[batch_key] = None
            return

        requests, futures = zip(*queue, strict=False)
        queue.clear()
        self.batch_timers[batch_key] = None

        try:
            self.batched_count += len(requests)
            results = await batch_executor(list(requests))
            for future, result in zip(futures, results, strict=False):
                if not future.done():
                    future.set_result(result)
        except Exception as e:
            for future in futures:
                if not future.done():
                    future.set_exception(e)

    def get_stats(self) -> dict[str, int]:
        return {
            "coalesced_requests": self.coalesced_count,
            "batched_requests": self.batched_count,
            "exact_inflight": len(self.exact_inflight),
            "semantic_inflight": len(self.semantic_inflight),
            "active_batches": len([q for q in self.batch_queues.values() if q]),
        }

    _semantic_hash_cache: dict[str, str] = {}

    def _cached_semantic_hash(self, modality: str, prompt: str) -> str:
        cache_key = f"{modality}:{prompt}"
        if cache_key not in self._semantic_hash_cache:
            self._semantic_hash_cache[cache_key] = self._semantic_hash(modality, prompt)
        return self._semantic_hash_cache[cache_key]

    def _compute_fingerprint(self, content: str) -> str:
        import hashlib

        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    _semantic_hash_cache: dict[str, str] = {}

    def _cached_semantic_hash(self, modality: str, prompt: str) -> str:
        cache_key = f"{modality}:{prompt}"
        if cache_key not in self._semantic_hash_cache:
            self._semantic_hash_cache[cache_key] = self._semantic_hash(modality, prompt)
        return self._semantic_hash_cache[cache_key]

    def _compute_fingerprint(self, content: str) -> str:
        import hashlib
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def is_duplicate_content(self, content: str) -> bool:
        fp = self._compute_fingerprint(content)
        if fp in self._seen_hashes:
            return True
        self._seen_hashes.add(fp)
        return False
