"""
Role-Based Access Control
"""

import json
import logging
from enum import Enum
from functools import wraps

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

class Role(Enum):
    ADMIN = "admin"
    DEVELOPER = "developer"
    VIEWER = "viewer"
    BILLING = "billing"

class RBACMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, policy_file: str = "config/rbac_policies.json"):
        super().__init__(app)
        self.policy = self._load_policy(policy_file)

    def _load_policy(self, path: str) -> dict:
        try:
            with open(path) as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Could not load RBAC policy: {e}")
            # Default policy
            return {
                "roles": {
                    "admin": {"permissions": ["*"]},
                    "developer": {"permissions": ["generate", "fuse", "transcribe", "cost_report"]},
                    "viewer": {"permissions": ["health", "providers"]},
                    "billing": {"permissions": ["cost_report", "budget_alerts"]}
                },
                "default_role": "developer"
            }

    async def dispatch(self, request: Request, call_next):
        # Extract user role from API key or JWT
        # For simplicity, we read from header "X-Role" (in production, validate token)
        user_role = request.headers.get("X-Role", self.policy.get("default_role", "developer"))
        # Validate role exists
        if user_role not in self.policy["roles"]:
            user_role = self.policy.get("default_role", "developer")
        request.state.user_role = user_role
        request.state.permissions = self.policy["roles"][user_role]["permissions"]
        response = await call_next(request)
        return response

def require_role(required_role: Role):
    """Decorator to enforce role-based access."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Find request object in args or kwargs
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break
            if not request:
                for key, val in kwargs.items():
                    if isinstance(val, Request):
                        request = val
                        break
            if not request:
                # Fallback: check if first arg is request
                if args and isinstance(args[0], Request):
                    request = args[0]

            if request:
                user_role = getattr(request.state, "user_role", None)
                if user_role is None:
                    raise HTTPException(401, "Authentication required")
                if user_role != required_role.value and "admin" not in user_role:
                    # Check if role has permission via '*' wildcard
                    permissions = getattr(request.state, "permissions", [])
                    if "*" not in permissions:
                        raise HTTPException(403, "Insufficient permissions")
            return await func(*args, **kwargs)
        return wrapper
    return decorator
