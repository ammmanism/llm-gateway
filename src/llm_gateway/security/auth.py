import json
import os

from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.middleware.base import BaseHTTPMiddleware

security_scheme = HTTPBearer(auto_error=False)


async def require_admin_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key")
    if not credentials.credentials.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return credentials.credentials


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Mock API-key authentication with optional explicit tenant mapping."""

    def __init__(self, app, exclude_paths=None, tenant_map=None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or set()
        if tenant_map is None:
            try:
                tenant_map = json.loads(os.environ.get("TENANT_API_KEYS", "{}"))
            except json.JSONDecodeError:
                tenant_map = {}
        self.tenant_map = tenant_map

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if any(
            path == excluded or path.startswith(excluded.rstrip("/") + "/")
            for excluded in self.exclude_paths
        ):
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

        request.state.tenant_id = self.tenant_map.get(api_key, "default")
        return await call_next(request)
