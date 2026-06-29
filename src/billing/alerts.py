from src.utils.logger import get_logger

logger = get_logger(__name__)

class AlertEngine:
    """
    Fires alerts when tenant spend approaches their cap.
    """
    
    ALERT_LEVELS = [
        (0.50, "info",     "You've used 50% of your monthly budget"),
        (0.75, "warning",  "You've used 75% of your monthly budget"),
        (0.90, "critical", "You've used 90% of your monthly budget - approaching limit"),
        (1.00, "blocked",  "Monthly budget exhausted - requests will be rejected"),
    ]
    
    async def check_and_alert(self, tenant_id: str, current_spend: float, spend_cap: float) -> bool:
        """
        Check spend against cap and fire alerts if thresholds are crossed.
        Returns True if blocked (>= 100%), False otherwise.
        """
        if spend_cap <= 0:
            return False
            
        ratio = current_spend / spend_cap
        
        # In a real system, we'd check if we already fired this alert level for this month
        # to avoid spamming. Here we just log for demonstration.
        
        for threshold, level, msg in reversed(self.ALERT_LEVELS):
            if ratio >= threshold:
                logger.warning(f"ALERT [{level}] for Tenant {tenant_id}: {msg} (Spend: ${current_spend:.2f}/${spend_cap:.2f})")
                
                if threshold >= 1.0:
                    return True # Blocked
                break # Only fire highest triggered alert
                
        return False
