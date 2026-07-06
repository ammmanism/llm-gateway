"""
Authentication Middleware
Validates API keys and tokens.
"""

from fastapi import HTTPException, Request
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_api_key(request: Request):
    """
    Verify API key matches configured systems.
    """
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing API Key in headers (X-API-Key)"
        )
    # Placeholder validation
    if api_key != "omni_test_key":
        raise HTTPException(
            status_code=403,
            detail="Invalid API Key"
        )
    return api_key
