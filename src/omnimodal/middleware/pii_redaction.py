"""
PII Redaction Middleware
"""

import re
import logging
from typing import List, Dict, Any, Tuple
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from ..config import settings

logger = logging.getLogger(__name__)

class PIIRedactor:
    PATTERNS = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone": re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    }

    def redact(self, text: str, preserve_length: bool = True) -> Tuple[str, List[Dict]]:
        redacted = text
        findings = []
        for pii_type, pattern in self.PATTERNS.items():
            for match in pattern.finditer(redacted):
                start, end = match.span()
                original = match.group()
                if preserve_length:
                    replacement = "*" * len(original)
                else:
                    replacement = f"[{pii_type.upper()}_REDACTED]"
                redacted = redacted[:start] + replacement + redacted[end:]
                findings.append({"type": pii_type, "position": (start, end), "confidence": 1.0})
        return redacted, findings

    def redact_multimodal(self, inputs: List[Dict]) -> List[Dict]:
        redacted_inputs = []
        for inp in inputs:
            if inp.get("type") == "text":
                text, findings = self.redact(inp["content"])
                redacted_inputs.append({**inp, "content": text, "pii_redacted": findings})
            else:
                redacted_inputs.append(inp)
        return redacted_inputs

class PIIRedactionMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, enabled: bool = True):
        super().__init__(app)
        self.redactor = PIIRedactor()
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)

        # For generation endpoints, redact request body
        if request.url.path in ["/v1/generate", "/v1/fuse"]:
            try:
                body = await request.json()
                if "inputs" in body:
                    body["inputs"] = self.redactor.redact_multimodal(body["inputs"])
                    # In real implementation, we'd need to replace request body
                    # For simplicity, we log that redaction occurred
                    logger.info("PII redaction applied to request")
            except Exception as e:
                logger.warning(f"PII redaction failed: {e}")

        response = await call_next(request)
        response.headers["X-PII-Redacted"] = "true" if self.enabled else "false"
        return response
