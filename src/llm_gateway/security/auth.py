import json
import os

import redis.asyncio as redis
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

from llm_gateway.auth.cached_key_store import CachedVirtualKeyStore
from llm_gateway.auth.key_store import VirtualKeyStore

security_scheme = HTTPBearer(auto_error=False)


async def require_admin_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key")
    if not credentials.credentials.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    if request is not None:
        scopes = getattr(request.state, "scopes", ())
        if scopes and "admin" not in scopes:
            raise HTTPException(status_code=403, detail="Missing scope: admin")
    return credentials.credentials


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Authenticate virtual keys, with an explicit demo-mode escape hatch."""

    def __init__(
        self,
        app,
        exclude_paths=None,
        tenant_map=None,
        key_store=None,
    ):
        super().__init__(app)
        self.exclude_paths = exclude_paths or set()
        if tenant_map is None:
            try:
                tenant_map = json.loads(os.environ.get("TENANT_API_KEYS", "{}"))
            except json.JSONDecodeError:
                tenant_map = {}
        self.tenant_map = tenant_map
        self.allow_demo_keys = os.environ.get("ALLOW_DEMO_KEYS", "false").lower() in {
            "1",
            "true",
            "yes",
        }
        self.key_store = key_store
        redis_url = os.environ.get("REDIS_URL")
        if key_store is not None and redis_url:
            self.key_store = CachedVirtualKeyStore(
                key_store,
                redis.from_url(redis_url, decode_responses=True),
            )

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        excluded = any(
            path == item or path.startswith(item.rstrip("/") + "/")
            for item in self.exclude_paths
        )
        if excluded and not path.startswith("/admin"):
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unauthorized", "mock": False},
            )

        api_key = auth_header.split(" ", 1)[1]
        if not api_key.startswith("sk-"):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API Key", "mock": False},
            )

        store = getattr(request.app.state, "virtual_key_store", None)
        if store is None:
            store = self.key_store or VirtualKeyStore()
        key = await store.get_key(api_key)
        if key is None:
            if not self.allow_demo_keys:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid API Key", "mock": False},
                )
            tenant_id = self.tenant_map.get(api_key, "default")
            key_id = "demo"
            scopes = ("generate", "costs", "admin")
            rpm_limit = tpm_limit = None
            budget_usd = None
        else:
            tenant_id = key.tenant_id
            key_id = key.key_id
            scopes = key.scopes
            rpm_limit = key.rpm_limit
            tpm_limit = key.tpm_limit
            budget_usd = key.budget_usd

        required_scope = None
        if path.startswith("/admin"):
            required_scope = "admin"
        elif path.startswith("/v1/costs"):
            required_scope = "costs"
        elif path.startswith(("/generate", "/v1/chat/completions")):
            required_scope = "generate"
        if required_scope and required_scope not in scopes:
            return JSONResponse(
                status_code=403,
                content={"detail": f"Missing scope: {required_scope}", "mock": False},
            )

        request.state.tenant_id = tenant_id
        request.state.key_id = key_id
        request.state.scopes = scopes
        request.state.rpm_limit = rpm_limit
        request.state.tpm_limit = tpm_limit
        request.state.budget_usd = budget_usd
        return await call_next(request)
