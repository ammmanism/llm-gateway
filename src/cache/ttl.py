from datetime import datetime, timedelta
import math
from typing import Optional

def calculate_ttl(tenant_ttl_hours: Optional[int] = None, default_ttl_hours: int = 24) -> datetime:
    """
    Calculate the expiration datetime based on TTL hours.
    """
    ttl = tenant_ttl_hours if tenant_ttl_hours is not None else default_ttl_hours
    return datetime.utcnow() + timedelta(hours=ttl)

def get_ttl_seconds(tenant_ttl_hours: Optional[int] = None, default_ttl_hours: int = 24) -> int:
    """
    Calculate the TTL in seconds.
    """
    ttl = tenant_ttl_hours if tenant_ttl_hours is not None else default_ttl_hours
    return ttl * 3600