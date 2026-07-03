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
