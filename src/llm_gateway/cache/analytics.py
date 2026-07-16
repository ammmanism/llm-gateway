import asyncpg
from typing import Any, Dict, List, cast

async def get_cache_analytics(pg_pool: asyncpg.Pool, tenant_id: str) -> Dict[str, Any]:
    """
    Generate analytics and performance stats for the tenant's cache from PostgreSQL usage logs.
    """
    stats: Dict[str, Any] = {
        "tenant_id": tenant_id,
        "total_requests": 0,
        "cache_hits": 0,
        "cache_misses": 0,
        "cache_hit_rate": 0.0,
        "total_saved_usd": 0.0,
        "avg_hit_latency_ms": 0.0,
        "avg_miss_latency_ms": 0.0,
        "top_queries": []
    }
    
    if pg_pool is None:
        return stats
        
    try:
        async with pg_pool.acquire() as conn:
            # 1. Fetch aggregation stats from usage_log
            row = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_requests,
                    SUM(CASE WHEN is_cache_hit = TRUE THEN 1 ELSE 0 END) as cache_hits,
                    SUM(CASE WHEN is_cache_hit = FALSE THEN 1 ELSE 0 END) as cache_misses,
                    SUM(saved_usd) as total_saved_usd,
                    AVG(CASE WHEN is_cache_hit = TRUE THEN latency_ms ELSE NULL END) as avg_hit_latency,
                    AVG(CASE WHEN is_cache_hit = FALSE THEN latency_ms ELSE NULL END) as avg_miss_latency
                FROM usage_log
                WHERE tenant_id = $1::uuid
                """,
                tenant_id
            )
            
            if row and row["total_requests"] > 0:
                stats["total_requests"] = row["total_requests"]
                stats["cache_hits"] = row["cache_hits"] or 0
                stats["cache_misses"] = row["cache_misses"] or 0
                cache_hits = int(stats["cache_hits"])
                total_requests = int(stats["total_requests"])
                stats["cache_hit_rate"] = cache_hits / total_requests
                stats["total_saved_usd"] = float(row["total_saved_usd"] or 0.0)
                stats["avg_hit_latency_ms"] = float(row["avg_hit_latency"] or 0.0)
                stats["avg_miss_latency_ms"] = float(row["avg_miss_latency"] or 0.0)
                
            # 2. Fetch top 5 queries by hit count
            top_rows = await conn.fetch(
                """
                SELECT query_text, hit_count, model, provider, cost_usd
                FROM cache_entries
                WHERE tenant_id = $1::uuid AND invalidated_at IS NULL
                ORDER BY hit_count DESC
                LIMIT 5
                """,
                tenant_id
            )
            
            for trow in top_rows:
                top_queries = cast(List[Dict[str, Any]], stats["top_queries"])
                top_queries.append({
                    "query": trow["query_text"],
                    "hit_count": trow["hit_count"] or 0,
                    "model": trow["model"],
                    "provider": trow["provider"],
                    "cost_usd": float(trow["cost_usd"] or 0.0)
                })
                
    except Exception:
        pass
        
    return stats
