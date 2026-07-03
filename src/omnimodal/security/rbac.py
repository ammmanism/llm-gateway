"""
Role-Based Access Control
"""

import json
import logging
from enum import Enum
from functools import wraps
from typing import Dict, List, Optional, Any
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from ..config import settings

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

    def _load_policy(self, path: str) -> Dict:
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
