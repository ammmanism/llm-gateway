from fastapi import APIRouter, Depends, Request, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, List
import secrets
import hashlib
import json
import uuid
from llm_gateway.security.auth import require_admin_api_key

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin_api_key)])


def _row_get(row, key, default=None):
    try:
        return row[key]
    except (KeyError, TypeError):
        return default

class TenantCreate(BaseModel):
    name: str
    tier: str = Field(default="free", description="free, pro, or enterprise")
    rate_limit_rpm: int = 20
    rate_limit_tpm: int = 10000
    spend_cap_usd: Optional[float] = 10.0
    alert_threshold: Optional[float] = 8.0
    routing_weights: Optional[Dict[str, float]] = None
    allowed_models: Optional[List[str]] = None
    cache_threshold: float = 0.92
    cache_ttl_hours: int = 24

class TenantResponse(BaseModel):
    id: str
    name: str
    tier: str
    rate_limit_rpm: int
    rate_limit_tpm: int
    spend_cap_usd: Optional[float]
    alert_threshold: Optional[float]
    routing_weights: Optional[Dict[str, float]]
    allowed_models: Optional[List[str]]
    cache_threshold: float
    cache_ttl_hours: int
    is_active: bool

@router.post("/tenants", status_code=status.HTTP_201_CREATED)
async def create_tenant(request: Request, tenant_in: TenantCreate):
    pg_pool = request.app.state.pg_pool
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
        
    api_key = f"nc_{secrets.token_hex(16)}"
    api_key_hash = hashlib.sha256(api_key.encode()).hexdigest()
    tenant_id = str(uuid.uuid4())
    
    try:
        async with pg_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tenants (
                    id, api_key_hash, name, tier, rate_limit_rpm, rate_limit_tpm,
                    spend_cap_usd, alert_threshold, allowed_models, cache_threshold, cache_ttl_hours,
                    routing_weights
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                tenant_id,
                api_key_hash,
                tenant_in.name,
                tenant_in.tier,
                tenant_in.rate_limit_rpm,
                tenant_in.rate_limit_tpm,
                tenant_in.spend_cap_usd,
                tenant_in.alert_threshold,
                tenant_in.allowed_models,
                tenant_in.cache_threshold,
                tenant_in.cache_ttl_hours,
                json.dumps(tenant_in.routing_weights) if tenant_in.routing_weights else None
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
        
    return {
        "status": "success",
        "api_key": api_key,
        "tenant_id": tenant_id,
        "message": "Write down the api_key. It will not be shown again."
    }

@router.get("/tenants", response_model=List[TenantResponse])
async def list_tenants(request: Request):
    pg_pool = request.app.state.pg_pool
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
        
    try:
        async with pg_pool.acquire() as conn:
            rows = await conn.fetch("SELECT * FROM tenants")
            tenants = []
            for row in rows:
                tenants.append(
                    TenantResponse(
                        id=str(row["id"]),
                        name=row["name"],
                        tier=row["tier"],
                        rate_limit_rpm=row["rate_limit_rpm"],
                        rate_limit_tpm=row["rate_limit_tpm"],
                        spend_cap_usd=float(row["spend_cap_usd"]) if row["spend_cap_usd"] is not None else None,
                        alert_threshold=float(row["alert_threshold"]) if row["alert_threshold"] is not None else None,
                        routing_weights=json.loads(_row_get(row, "routing_weights")) if isinstance(_row_get(row, "routing_weights"), str) else _row_get(row, "routing_weights"),
                        allowed_models=_row_get(row, "allowed_models"),
                        cache_threshold=_row_get(row, "cache_threshold", 0.92),
                        cache_ttl_hours=_row_get(row, "cache_ttl_hours", 24),
                        is_active=row["is_active"]
                    )
                )
            return tenants
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")

@router.delete("/tenants/{tenant_id}", status_code=status.HTTP_200_OK)
async def delete_tenant(request: Request, tenant_id: str):
    pg_pool = request.app.state.pg_pool
    tenant_manager = request.app.state.tenant_manager
    if not pg_pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
        
    try:
        async with pg_pool.acquire() as conn:
            row = await conn.fetchrow("SELECT api_key_hash FROM tenants WHERE id = $1", tenant_id)
            if not row:
                raise HTTPException(status_code=404, detail="Tenant not found")
                
            api_key_hash = row["api_key_hash"]
            
            await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
            
            if tenant_manager and tenant_manager.redis:
                await tenant_manager.redis.delete(f"tenant:{api_key_hash}")
                
            return {"status": "success", "message": f"Tenant {tenant_id} deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {e}")
