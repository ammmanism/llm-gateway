from datetime import datetime, timedelta

from llm_gateway.cache.drift_detector import DriftDetector
from llm_gateway.cache.ttl import calculate_ttl, get_ttl_seconds


def test_ttl_calculation():
    ttl_dt = calculate_ttl(tenant_ttl_hours=10)
    assert ttl_dt > datetime.utcnow()
    assert get_ttl_seconds(tenant_ttl_hours=10) == 36000


def test_drift_detector():
    detector = DriftDetector(threshold=0.7)

    # Very old, inconsistent, volatile query should drift
    created_at = datetime.utcnow() - timedelta(hours=20)
    score = detector.compute_drift_score(
        created_at, 24, "What is the current stock price of Apple?", 0.1
    )

    assert score > 0.7
    assert detector.should_invalidate(score)

    # New, consistent, non-volatile query should not drift
    created_at = datetime.utcnow()
    score = detector.compute_drift_score(created_at, 24, "What is photosynthesis?", 1.0)

    assert score < 0.2
    assert not detector.should_invalidate(score)
