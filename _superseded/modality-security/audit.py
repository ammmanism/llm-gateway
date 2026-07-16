"""
Audit Logging
"""

import json
import logging
import time
from typing import Any

from fastapi import Request

from ..config import settings

logger = logging.getLogger("audit")


class AuditLogger:
    @staticmethod
    async def log_request(
        request: Request, response: Any, cost_usd: float, provider: str, modality: str
    ):
        """Log request details to audit backend."""
        entry = {
            "timestamp": time.time(),
            "request_id": getattr(request.state, "request_id", "unknown"),
            "user": getattr(request.state, "user_role", "anonymous"),
            "method": request.method,
            "path": request.url.path,
            "modality": modality,
            "provider": provider,
            "cost_usd": cost_usd,
            "status_code": (
                response.status_code if hasattr(response, "status_code") else 200
            ),
            "client_ip": request.client.host if request.client else "unknown",
            "headers": dict(request.headers) if settings.debug else {},
        }
        if settings.security.audit_log_backend == "console":
            logger.info(json.dumps(entry))
        elif settings.security.audit_log_backend == "elasticsearch":
            # Send to Elasticsearch
            pass
        elif settings.security.audit_log_backend == "cloudtrail":
            # Send to AWS CloudTrail
            pass
        # Store in database etc.
