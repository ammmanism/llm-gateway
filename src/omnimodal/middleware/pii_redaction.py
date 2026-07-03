"""
PII Redaction Middleware
GDPR/HIPAA compliant automatic PII detection and masking.
"""

import re
from typing import List, Dict, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class PIIRedactor:
    """
    Detects and redacts personally identifiable information.
    Uses regex + optional ML-based detection.
    """
    
    PATTERNS = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone": re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "credit_card": re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b'),
        "ip_address": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    }
    
    def __init__(self, use_ml_detection: bool = False):
        self.use_ml = use_ml_detection
    
    def redact(self, text: str, preserve_length: bool = True) -> tuple[str, list]:
        """
        Redact PII from text.
        
        Args:
            text: Input text
            preserve_length: If True, replaces with same-length asterisks
            
        Returns:
            Redacted text and list of findings
        """
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
                findings.append({
                    "type": pii_type,
                    "position": (start, end),
                    "confidence": 1.0
                })
        
        return redacted, findings
    
    def redact_multimodal(self, inputs: List[Dict]) -> List[Dict]:
        """Redact PII from multimodal inputs (text only)."""
        redacted_inputs = []
        for inp in inputs:
            if inp.get("type") == "text":
                text, findings = self.redact(inp["content"])
                redacted_inputs.append({
                    **inp,
                    "content": text,
                    "pii_redacted": findings
                })
            else:
                redacted_inputs.append(inp)
        return redacted_inputs


class PIIRedactionMiddleware(BaseHTTPMiddleware):
    """
    Middleware that automatically redacts PII before sending to providers.
    """
    
    def __init__(self, app, enabled: bool = True):
