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
