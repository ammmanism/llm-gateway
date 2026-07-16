import math
import random
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class CircuitBreaker:
    state: str = "CLOSED" # CLOSED, OPEN, HALF_OPEN
    failure_count: int = 0
    success_count: int = 0
    last_failure_at: Optional[datetime] = None
    cooldown_seconds: float = 30.0
    
    def record_failure(self):
        self.failure_count += 1
        self.last_failure_at = datetime.utcnow()
        if self.failure_count >= 5:
            self.state = "OPEN"
            
    def record_success(self):
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= 3:
                self.state = "CLOSED"
                self.failure_count = 0
                self.success_count = 0

class EWMATracker:
    def __init__(self, alpha: float, initial_value: float):
        self.alpha = alpha
        self.value = initial_value
        self.last_updated = datetime.utcnow()
        
    def update(self, observation: float) -> float:
        now = datetime.utcnow()
        elapsed = (now - self.last_updated).total_seconds()
        
        # Time decay towards baseline if no observations
        if elapsed > 300:
            decay = math.exp(-elapsed / 600)
            # Assuming 0 is a good baseline for errors, and some default for latency
            # We'll just decay towards 0 for simplicity here or could maintain an initial
            self.value = self.value * decay
            
        self.value = self.alpha * observation + (1 - self.alpha) * self.value
        self.last_updated = now
        return self.value

@dataclass
class ProviderState:
    name: str
    models: List[str]
    cost_per_1k_input: float
    cost_per_1k_output: float
    ewma_latency: EWMATracker
    ewma_error_rate: EWMATracker
    circuit: CircuitBreaker
    quality_score: float = 0.8
    
    @property
    def is_available(self) -> bool:
        if self.circuit.state == "CLOSED":
            return True
        if self.circuit.state == "OPEN":
            if not self.circuit.last_failure_at:
                self.circuit.state = "HALF_OPEN"
                self.circuit.success_count = 0
                return True
            if (datetime.utcnow() - self.circuit.last_failure_at).total_seconds() > self.circuit.cooldown_seconds:
                self.circuit.state = "HALF_OPEN"
                self.circuit.success_count = 0
                return True
            return False
        return True # HALF_OPEN

class SmartRouter:
    def __init__(self):
        # Initialize some default states
        self.providers = {
            "openai": ProviderState("openai", ["gpt-4o", "gpt-4o-mini"], 0.0025, 0.010, EWMATracker(0.2, 500.0), EWMATracker(0.15, 0.0), CircuitBreaker(), 0.95),
            "anthropic": ProviderState("anthropic", ["claude-sonnet-4", "claude-haiku-3.5"], 0.003, 0.015, EWMATracker(0.2, 600.0), EWMATracker(0.15, 0.0), CircuitBreaker(), 0.96),
            "deepseek": ProviderState("deepseek", ["deepseek-v3"], 0.00014, 0.00028, EWMATracker(0.2, 800.0), EWMATracker(0.15, 0.0), CircuitBreaker(), 0.85),
            "groq": ProviderState("groq", ["llama-3.3-70b"], 0.00059, 0.00079, EWMATracker(0.2, 200.0), EWMATracker(0.15, 0.0), CircuitBreaker(), 0.82),
            "gemini": ProviderState("gemini", ["gemini-2.5-flash"], 0.00015, 0.00035, EWMATracker(0.2, 400.0), EWMATracker(0.15, 0.0), CircuitBreaker(), 0.88),
        }
        
    def _normalize(self, value: float, all_values: List[float], invert: bool = True) -> float:
        if not all_values:
            return 0.5
        min_v, max_v = min(all_values), max(all_values)
        if max_v == min_v:
            return 1.0 if invert else 0.0
        norm = (value - min_v) / (max_v - min_v)
        return 1.0 - norm if invert else norm

    def route(self, request_tokens: int, quality_threshold: float = 0.8, weights: Optional[Dict[str, float]] = None) -> ProviderState:
        if not weights:
            weights = {"cost": 0.5, "latency": 0.3, "reliability": 0.2}
            
        available = [p for p in self.providers.values() if p.is_available and p.quality_score >= quality_threshold]
        
        if not available:
            raise Exception("No available providers meeting criteria")
            
        # A/B Testing (10% exploration)
        if random.random() < 0.10:
            # Thompson sampling approximation
            return random.choice(available)
            
        costs = [p.cost_per_1k_input for p in available]
        latencies = [p.ewma_latency.value for p in available]
        
        best_score = -1.0
        best_provider = None
        
        for p in available:
            cost_score = self._normalize(p.cost_per_1k_input, costs)
            latency_score = self._normalize(p.ewma_latency.value, latencies)
            reliability_score = 1.0 - p.ewma_error_rate.value
            
            score = (weights["cost"] * cost_score + 
                     weights["latency"] * latency_score + 
                     weights["reliability"] * reliability_score)
                     
            if score > best_score:
                best_score = score
                best_provider = p
                
        if best_provider is None:
            raise Exception("No available providers meeting criteria")
        return best_provider

smart_router = SmartRouter()
