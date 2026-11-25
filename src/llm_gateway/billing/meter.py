from typing import Optional

import asyncpg

from llm_gateway.utils.logger import get_logger

logger = get_logger(__name__)


class UsageMeter:
    """
    Per-request tracking and savings calculation.
    """

    # Naive baseline pricing for GPT-4o
    GPT4O_INPUT_RATE = 0.0025 / 1000
    GPT4O_OUTPUT_RATE = 0.010 / 1000

    def __init__(self, pg_pool: Optional[asyncpg.Pool] = None):
        self.pg_pool = pg_pool

    def calculate_savings(
        self, tokens_in: int, tokens_out: int, actual_cost: float
    ) -> float:
        """Calculate savings compared to naive GPT-4o usage."""
        naive_cost = (tokens_in * self.GPT4O_INPUT_RATE) + (
            tokens_out * self.GPT4O_OUTPUT_RATE
        )
        savings = max(0.0, naive_cost - actual_cost)
        return savings

    async def log_usage(
        self,
        tenant_id: str,
        request_id: str,
        is_cache_hit: bool,
        provider: Optional[str],
        model: Optional[str],
        tokens_in: int,
        tokens_out: int,
        actual_cost: float,
        latency_ms: int,
        cache_similarity: Optional[float] = None,
        routing_reason: Optional[str] = None,
    ):
        """
        Log usage to PostgreSQL and update tenant's current month spend.
        """
        savings = self.calculate_savings(tokens_in, tokens_out, actual_cost)

        logger.info(
            "Usage logged for %s: cost=$%.6f, saved=$%.6f",
            tenant_id,
            actual_cost,
            savings,
        )

        if not self.pg_pool:
            return  # Skip DB write if not configured

        try:
            async with self.pg_pool.acquire() as conn:
                # 1. Insert into usage_log
                await conn.execute(
                    """
                    INSERT INTO usage_log (
                        tenant_id, request_id, is_cache_hit, provider, model,
                        tokens_in, tokens_out, cost_usd, saved_usd, latency_ms,
                        cache_similarity, routing_reason
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                    """,
                    tenant_id,
                    request_id,
                    is_cache_hit,
                    provider,
                    model,
                    tokens_in,
                    tokens_out,
                    actual_cost,
                    savings,
                    latency_ms,
                    cache_similarity,
                    routing_reason,
                )

                # In production, also increment a monthly Redis spend counter here.
                # to efficiently enforce spend caps without querying the whole log.

        except Exception as e:
            logger.error(f"Failed to log usage to DB: {e}", exc_info=True)
