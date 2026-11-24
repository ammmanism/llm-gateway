import asyncio
import copy
import hashlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

import faiss
import numpy as np
import yaml

from llm_gateway.cache.cache_manager import CacheManager
from llm_gateway.utils.embeddings import embedding_engine

logger = logging.getLogger(__name__)


@dataclass
class CacheLookup:
    value: Dict[str, Any]
    tier: str
    similarity: float = 1.0


@dataclass
class _Partition:
    index: Any
    entries: Dict[int, Dict[str, Any]]
    next_id: int = 0


class SemanticIndex:
    """In-process, tenant/model-partitioned FAISS semantic index."""

    def __init__(self, embedder=None, top_k: int = 5):
        self.embedder = embedder or embedding_engine
        self.top_k = top_k
        self._partitions: Dict[str, _Partition] = {}
        self._lock = asyncio.Lock()

    def _new_partition(self) -> _Partition:
        index = faiss.IndexHNSWFlat(
            self.embedder.dimension,
            16,
            faiss.METRIC_INNER_PRODUCT,
        )
        index.hnsw.efConstruction = 100
        index.hnsw.efSearch = 64
        return _Partition(faiss.IndexIDMap(index), {})

    async def _embed(self, text: str) -> np.ndarray:
        embed = getattr(self.embedder, "embed", None)
        if embed is not None:
            return np.asarray(await embed(text), dtype=np.float32)
        return np.asarray(
            await asyncio.to_thread(self.embedder.encode, text),
            dtype=np.float32,
        )

    async def search(
        self,
        namespace: str,
        text: str,
        threshold: float,
        now: float,
    ) -> Optional[CacheLookup]:
        async with self._lock:
            partition = self._partitions.get(namespace)
            if partition is None or partition.index.ntotal == 0:
                return None
            vector = np.asarray(
                [await self._embed(text)],
                dtype=np.float32,
            )
            scores, indices = partition.index.search(
                vector,
                min(self.top_k, partition.index.ntotal),
            )
            for score, internal_id in zip(scores[0], indices[0]):
                if internal_id == -1 or float(score) < threshold:
                    continue
                entry = partition.entries.get(int(internal_id))
                if entry is None or entry["expires_at"] <= now:
                    continue
                return CacheLookup(
                    value=copy.deepcopy(entry["value"]),
                    tier="semantic",
                    similarity=float(score),
                )
        return None

    async def add(
        self,
        namespace: str,
        text: str,
        value: Dict[str, Any],
        ttl: int,
        now: float,
    ) -> None:
        vector = np.asarray(
            [await self._embed(text)],
            dtype=np.float32,
        )
        async with self._lock:
            partition = self._partitions.setdefault(
                namespace,
                self._new_partition(),
            )
            internal_id = partition.next_id
            partition.next_id += 1
            partition.index.add_with_ids(
                vector,
                np.asarray([internal_id], dtype=np.int64),
            )
            partition.entries[internal_id] = {
                "value": copy.deepcopy(value),
                "expires_at": now + ttl,
            }


class TwoTierCache:
    """Exact cache first, semantic vector cache second."""

    def __init__(
        self,
        exact_cache: Optional[CacheManager] = None,
        semantic_index: Optional[SemanticIndex] = None,
        threshold: float = 0.90,
        exact_ttl: int = 3600,
        semantic_ttl: int = 86400,
        clock=None,
    ):
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("semantic similarity threshold must be between 0 and 1")
        self.exact = exact_cache or CacheManager()
        self.semantic = semantic_index or SemanticIndex()
        self.threshold = threshold
        self.exact_ttl = exact_ttl
        self.semantic_ttl = semantic_ttl
        self._clock = clock or time.monotonic

    @classmethod
    def from_config(cls, path: str = "configs/caching.yaml") -> "TwoTierCache":
        config = {}
        config_path = Path(path)
        if config_path.exists():
            config = yaml.safe_load(config_path.read_text()) or {}
        strategies = config.get("strategies", {})
        semantic = strategies.get("semantic", {})
        exact = strategies.get("exact", {})
        return cls(
            threshold=float(semantic.get("similarity_threshold", 0.90)),
            exact_ttl=int(exact.get("ttl", 3600)),
            semantic_ttl=int(semantic.get("ttl", 86400)),
        )

    @staticmethod
    def namespace(tenant_id: str, model: str, params: Dict[str, Any]) -> str:
        payload = json.dumps(
            {"tenant": tenant_id, "model": model, "params": params},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    async def get(
        self,
        text: str,
        tenant_id: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Optional[CacheLookup]:
        params = params or {}
        namespace = self.namespace(tenant_id, model, params)
        key = f"cache:exact:{namespace}:{hashlib.sha256(text.encode()).hexdigest()}"
        exact = await self.exact.get(key)
        if exact is not None:
            return CacheLookup(value=exact, tier="exact")
        return await self.semantic.search(
            namespace,
            text,
            self.threshold,
            self._clock(),
        )

    async def set(
        self,
        text: str,
        value: Dict[str, Any],
        tenant_id: str,
        model: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> None:
        params = params or {}
        namespace = self.namespace(tenant_id, model, params)
        key = f"cache:exact:{namespace}:{hashlib.sha256(text.encode()).hexdigest()}"
        await self.exact.set(key, value, ttl=self.exact_ttl)
        try:
            await self.semantic.add(
                namespace,
                text,
                value,
                self.semantic_ttl,
                self._clock(),
            )
        except Exception as exc:
            # Exact caching remains useful if embedding/indexing is unavailable.
            logger.warning("Semantic cache store failed: %s", exc)
