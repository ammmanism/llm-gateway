import hashlib
import json
import re
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

import asyncpg
import faiss
import numpy as np
import redis.asyncio as redis

from llm_gateway.cache.drift_detector import DriftDetector
from llm_gateway.config import settings
from llm_gateway.utils.embeddings import embedding_engine
from llm_gateway.utils.logger import get_logger

logger = get_logger(__name__)


class SemanticCache:
    """
    Orchestrates FAISS (L1), Redis (L2), and PostgreSQL (L3) caching.
    """

    def __init__(self):
        self.dimension = 384
        # HNSW configuration
        self.M = 32
        self.efConstruction = 200
        self.efSearch = 128

        self.index = None
        self.redis_client = None
        self.pg_pool = None
        self.id_map = {}  # Maps FAISS internal IDs to entry UUIDs
        self.reverse_id_map = {}  # Maps entry UUIDs to FAISS internal IDs
        self._next_internal_id = 0
        self.drift_detector = DriftDetector()

    async def initialize(self):
        """Initialize connections and load index"""
        logger.info("Initializing SemanticCache")

        # 1. Init FAISS
        hnsw_index = faiss.IndexHNSWFlat(
            self.dimension, self.M, faiss.METRIC_INNER_PRODUCT
        )
        hnsw_index.hnsw.efConstruction = self.efConstruction
        hnsw_index.hnsw.efSearch = self.efSearch
        self.index = faiss.IndexIDMap(hnsw_index)

        # 2. Init Redis
        self.redis_client = await redis.from_url(
            settings.REDIS_URL, decode_responses=True
        )

        # 3. Init PostgreSQL
        self.pg_pool = await asyncpg.create_pool(settings.DATABASE_URL)

        # TODO: Load warm cache from PostgreSQL into FAISS and Redis
        logger.info("SemanticCache initialized")

    async def close(self):
        """Close connections"""
        if self.redis_client:
            await self.redis_client.aclose()
        if self.pg_pool:
            await self.pg_pool.close()

    def _compute_metadata_hash(
        self, model: str, params: Dict[str, Any], namespace: str
    ) -> str:
        """Hash request parameters to prevent cross-configuration hits."""
        hash_dict = {"model": model, "params": params, "namespace": namespace}
        hash_str = json.dumps(hash_dict, sort_keys=True)
        return hashlib.sha256(hash_str.encode("utf-8")).hexdigest()

    def _compute_prompt_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _redact_prompt(self, text: str) -> str:
        if not settings.CACHE_REDACTION_ENABLED:
            return text
        redacted = re.sub(r"[\w.+-]+@[\w-]+\.[\w.-]+", "[email]", text)
        redacted = re.sub(r"\b(?:\d[ -]*?){13,19}\b", "[card]", redacted)
        redacted = re.sub(r"\b\d{3}-\d{2}-\d{4}\b", "[ssn]", redacted)
        return redacted

    async def check_cache(
        self,
        text: str,
        model: str,
        params: Dict[str, Any],
        tenant_id: str,
        threshold: float = 0.92,
        namespace: str = "default",
    ) -> Tuple[bool, Optional[Dict[str, Any]], Optional[float]]:
        """
        Check if a semantically similar query exists in cache.
        Returns: (is_hit, cached_response, similarity_score)
        """
        if self.index.ntotal == 0:
            return False, None, None

        vector = await embedding_engine.embed(text)
        vector = np.array([vector], dtype=np.float32)  # Reshape for FAISS

        metadata_hash = self._compute_metadata_hash(model, params, namespace)
        prompt_hash = self._compute_prompt_hash(text)

        # 1. FAISS Search (L1)
        # Search top 5 to handle hash collisions / tenant separation manually
        distances, indices = self.index.search(vector, k=5)

        for i in range(len(indices[0])):
            faiss_id = indices[0][i]
            score = distances[0][i]

            if faiss_id == -1 or score < threshold:
                continue  # No more valid matches or below threshold

            entry_id = self.id_map.get(faiss_id)
            if not entry_id:
                continue

            # 2. Redis Lookup (L2)
            redis_key = f"cache:response:{entry_id}"
            cached_data_str = await self.redis_client.get(redis_key)

            if cached_data_str:
                cached_data = json.loads(cached_data_str)
                # Verify tenant, namespace, and metadata hash. The exact
                # prompt hash is retained for auditing and exact-match paths.
                if (
                    cached_data.get("tenant_id") == tenant_id
                    and cached_data.get("metadata_hash") == metadata_hash
                ):
                    if cached_data.get("namespace", "default") != namespace:
                        continue
                    if (
                        cached_data.get("prompt_hash")
                        and cached_data.get("prompt_hash") != prompt_hash
                    ):
                        logger.debug(
                            "Semantic hit differs from exact prompt hash for entry %s",
                            entry_id,
                        )
                    if settings.CACHE_DRIFT_INVALIDATION_ENABLED:
                        created_at_raw = cached_data.get("created_at")
                        if created_at_raw:
                            created_at = datetime.fromisoformat(created_at_raw)
                            drift_score = self.drift_detector.compute_drift_score(
                                created_at,
                                cached_data.get(
                                    "ttl_hours", settings.DEFAULT_CACHE_TTL_HOURS
                                ),
                                cached_data.get("query_text", text),
                            )
                            if self.drift_detector.should_invalidate(drift_score):
                                await self.redis_client.delete(redis_key)
                                logger.info(
                                    "Invalidated drifted cache entry %s", entry_id
                                )
                                continue
                    logger.info(f"Cache HIT for tenant {tenant_id}, score: {score:.4f}")

                    # Update hit count asynchronously (fire and forget)
                    import asyncio

                    asyncio.create_task(self._increment_hit_count(entry_id))

                    return True, cached_data.get("response"), score

        return False, None, None

    async def store_cache(
        self,
        text: str,
        model: str,
        params: Dict[str, Any],
        response: Dict[str, Any],
        tenant_id: str,
        provider: str,
        tokens_in: int,
        tokens_out: int,
        cost_usd: float,
        ttl_seconds: int,
        namespace: str = "default",
    ):
        """
        Store a new response in cache asynchronously (fire-and-forget).
        """
        try:
            entry_id = str(uuid.uuid4())
            vector = await embedding_engine.embed(text)
            metadata_hash = self._compute_metadata_hash(model, params, namespace)
            prompt_hash = self._compute_prompt_hash(text)
            redacted_text = self._redact_prompt(text)

            # 1. Update FAISS (L1)
            faiss_id = self._next_internal_id
            self._next_internal_id += 1

            vector_np = np.array([vector], dtype=np.float32)
            faiss_ids_np = np.array([faiss_id], dtype=np.int64)
            self.index.add_with_ids(vector_np, faiss_ids_np)

            self.id_map[faiss_id] = entry_id
            self.reverse_id_map[entry_id] = faiss_id

            # 2. Update Redis (L2)
            redis_key = f"cache:response:{entry_id}"
            cache_payload = {
                "id": entry_id,
                "tenant_id": tenant_id,
                "namespace": namespace,
                "metadata_hash": metadata_hash,
                "prompt_hash": prompt_hash,
                "query_text": redacted_text,
                "response": response,
                "created_at": datetime.utcnow().isoformat(),
                "ttl_hours": max(1, int(ttl_seconds / 3600)),
            }
            await self.redis_client.setex(
                redis_key, ttl_seconds, json.dumps(cache_payload)
            )

            # 3. Update PostgreSQL (L3)
            if self.pg_pool:
                expires_at = datetime.utcnow() + __import__("datetime").timedelta(
                    seconds=ttl_seconds
                )
                async with self.pg_pool.acquire() as conn:
                    # Tests without pgvector accept JSON here; production
                    # deployments use the vector column.
                    await conn.execute(
                        """
                        INSERT INTO cache_entries (
                            id, tenant_id, namespace, embedding, metadata_hash,
                            prompt_hash, query_text, response_text, model,
                            provider, tokens_in, tokens_out, cost_usd, expires_at
                        ) VALUES (
                            $1, $2, $3, $4::vector, $5, $6, $7, $8,
                            $9, $10, $11, $12, $13, $14
                        )
                        """,
                        entry_id,
                        tenant_id,
                        namespace,
                        vector.tolist(),
                        metadata_hash,
                        prompt_hash,
                        redacted_text,
                        json.dumps(response),
                        model,
                        provider,
                        tokens_in,
                        tokens_out,
                        cost_usd,
                        expires_at,
                    )

            logger.info(f"Stored cache entry {entry_id} for tenant {tenant_id}")

        except Exception as e:
            logger.error(f"Failed to store cache entry: {e}", exc_info=True)

    async def _increment_hit_count(self, entry_id: str):
        """Async increment of hit count in Redis and PG"""
        try:
            # We can use a separate redis key or just update PG
            if self.pg_pool:
                async with self.pg_pool.acquire() as conn:
                    await conn.execute(
                        (
                            "UPDATE cache_entries SET hit_count = hit_count + 1 "
                            "WHERE id = $1"
                        ),
                        entry_id,
                    )
        except Exception as e:
            logger.error(f"Failed to increment hit count for {entry_id}: {e}")


semantic_cache = SemanticCache()
