from fastapi import Request, HTTPException, Depends
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import JSONResponse
import os

security_scheme = HTTPBearer(auto_error=False)


async def require_admin_api_key(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Missing API key")
    api_key = credentials.credentials
    if not api_key.startswith("sk-"):
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


class APIKeyAuthMiddleware(BaseHTTPMiddleware):
    """Middleware for API key authentication."""
    def __init__(self, app, exclude_paths=None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or set()

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self.exclude_paths:
            return await call_next(request)

        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Unauthorized", "mock": False})
        
        # Simple mock validation
        api_key = auth_header.split(" ")[1]
        if not api_key.startswith("sk-"):
            return JSONResponse(status_code=401, content={"detail": "Invalid API Key", "mock": False})
        
        # Attach tenant_id to state
        request.state.tenant_id = "default"
        
        return await call_next(request)
