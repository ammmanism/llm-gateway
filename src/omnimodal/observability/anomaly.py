"""
Anomaly Detection
"""

import numpy as np
from typing import List, Optional

class CostAnomalyDetector:
    def __init__(self, window: int = 100, z_threshold: float = 3.0):
        self.history: List[float] = []
        self.window = window
        self.threshold = z_threshold

    def record(self, cost: float):
        self.history.append(cost)
        if len(self.history) > self.window * 2:
            self.history = self.history[-self.window:]

    def is_anomaly(self, cost: float) -> bool:
        if len(self.history) < self.window:
            return False
        recent = self.history[-self.window:]
        mean = np.mean(recent)
        std = np.std(recent) + 1e-9
        z_score = (cost - mean) / std
