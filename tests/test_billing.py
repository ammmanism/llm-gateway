import pytest
from src.billing.meter import UsageMeter

def test_savings_calculation():
    meter = UsageMeter()
    # 1000 in, 1000 out.
    # Naive GPT4o cost: 1000 * 0.0025/1k + 1000 * 0.010/1k = 0.0025 + 0.010 = 0.0125
    
    # Deepseek cost: 1000 * 0.00014/1k + 1000 * 0.00028/1k = 0.00042
    savings = meter.calculate_savings(1000, 1000, 0.00042)
    
    assert abs(savings - (0.0125 - 0.00042)) < 1e-6
