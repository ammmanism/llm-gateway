import hashlib
import logging
import time
import math
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    DRAFT = "draft"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"


@dataclass
class Variant:
    id: str
    name: str
    config: Dict[str, Any]
    traffic_percentage: float = 0.5
    impressions: int = 0
    conversions: int = 0
    total_latency_ms: float = 0
    total_cost: float = 0
    scores: List[float] = field(default_factory=list)


@dataclass
class Experiment:
    id: str
    name: str
    hypothesis: str
    metric: str
    variants: List[Variant]
    status: ExperimentStatus = ExperimentStatus.DRAFT
    min_samples: int = 100
    confidence_level: float = 0.95
    created_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None


class ExperimentEngine:
    def __init__(self):
        self.experiments: Dict[str, Experiment] = {}
        self.user_assignments: Dict[str, Dict[str, str]] = defaultdict(dict)
        self._results_cache: Dict[str, Any] = {}

    def create_experiment(
        self,
        name: str,
        hypothesis: str,
        metric: str,
        variants: List[Dict],
        min_samples: int = 100
    ) -> Experiment:
        exp_id = hashlib.sha256(f"{name}:{time.time()}".encode()).hexdigest()[:12]
        variant_objects = []
        traffic = 1.0 / len(variants)
        for i, v in enumerate(variants):
            variant_objects.append(Variant(
                id=f"{exp_id}_v{i}",
                name=v["name"],
                config=v["config"],
                traffic_percentage=traffic
            ))
        exp = Experiment(
            id=exp_id,
            name=name,
            hypothesis=hypothesis,
            metric=metric,
            variants=variant_objects,
            min_samples=min_samples
        )
        self.experiments[exp_id] = exp
        logger.info("Created experiment %s: %s", exp_id, name)
        return exp

    def get_variant(
        self,
        experiment_id: str,
        user_id: str,
        allow_shadow: bool = False
    ) -> Optional[Variant]:
        exp = self.experiments.get(experiment_id)
        if not exp or exp.status != ExperimentStatus.RUNNING:
            return None

        if user_id in self.user_assignments:
            assigned = self.user_assignments[user_id].get(experiment_id)
            if assigned:
                for v in exp.variants:
                    if v.id == assigned:
                        return v

        hash_input = f"{experiment_id}:{user_id}"
        hash_val = int(hashlib.sha256(hash_input.encode()).hexdigest(), 16)
        bucket = (hash_val % 1000) / 1000.0

        cumulative = 0.0
        for variant in exp.variants:
            cumulative += variant.traffic_percentage
            if bucket <= cumulative:
                self.user_assignments[user_id][experiment_id] = variant.id
                return variant

        return exp.variants[0]

    async def run_with_experiment(
        self,
        experiment_id: str,
        user_id: str,
        control_fn: Callable,
        treatment_fn: Callable,
        shadow: bool = False
    ) -> Any:
        variant = self.get_variant(experiment_id, user_id)
        if not variant:
            return await control_fn()

        is_control = variant == self.experiments[experiment_id].variants[0]

        if shadow and not is_control:
            asyncio.create_task(self._run_shadow(
                experiment_id, variant, treatment_fn
            ))
            return await control_fn()

        start = time.time()
        try:
            if is_control:
                result = await control_fn()
            else:
                result = await treatment_fn()
            self._record_result(experiment_id, variant, True, time.time() - start)
            return result
        except Exception as e:
            self._record_result(experiment_id, variant, False, time.time() - start)
            raise

    async def _run_shadow(self, exp_id: str, variant: Variant, fn: Callable):
        try:
            start = time.time()
            await fn()
            self._record_result(exp_id, variant, True, time.time() - start)
        except Exception:
            self._record_result(exp_id, variant, False, 0)

    def _record_result(
        self,
        exp_id: str,
        variant: Variant,
        success: bool,
        latency: float
    ):
        variant.impressions += 1
        if success:
            variant.conversions += 1
        variant.total_latency_ms += latency * 1000

    def analyze_experiment(self, experiment_id: str) -> Dict[str, Any]:
        exp = self.experiments.get(experiment_id)
        if not exp:
            return {"error": "Experiment not found"}

        if len(exp.variants) < 2:
            return {"error": "Need at least 2 variants"}

        control = exp.variants[0]
        treatment = exp.variants[1]

        if control.impressions < exp.min_samples or treatment.impressions < exp.min_samples:
            return {
                "status": "insufficient_data",
                "control_samples": control.impressions,
                "treatment_samples": treatment.impressions,
                "min_required": exp.min_samples
            }

        control_rate = control.conversions / max(control.impressions, 1)
        treatment_rate = treatment.conversions / max(treatment.impressions, 1)

        control_se = math.sqrt(control_rate * (1 - control_rate) / max(control.impressions, 1))
        treatment_se = math.sqrt(treatment_rate * (1 - treatment_rate) / max(treatment.impressions, 1))

        se_diff = math.sqrt(control_se**2 + treatment_se**2)
        z_score = (treatment_rate - control_rate) / se_diff if se_diff > 0 else 0

        from math import erf
        p_value = 2 * (1 - 0.5 * (1 + erf(abs(z_score) / math.sqrt(2))))

        relative_lift = ((treatment_rate - control_rate) / control_rate
                        if control_rate > 0 else 0)

        winner = None
        if p_value < (1 - exp.confidence_level):
            winner = treatment if treatment_rate > control_rate else control

        return {
            "experiment_id": experiment_id,
            "status": "completed" if winner else "inconclusive",
            "control": {
                "variant": control.name,
                "rate": round(control_rate, 4),
                "samples": control.impressions
            },
            "treatment": {
                "variant": treatment.name,
                "rate": round(treatment_rate, 4),
                "samples": treatment.impressions
            },
            "relative_lift": f"{relative_lift:+.2%}",
            "p_value": round(p_value, 4),
            "confidence": f"{exp.confidence_level:.0%}",
            "winner": winner.name if winner else None,
            "recommendation": (
                f"Roll out {winner.name}" if winner
                else "Continue testing or check guardrail metrics"
            )
        }

    def auto_promote(self, experiment_id: str):
        result = self.analyze_experiment(experiment_id)
        winner_name = result.get("winner")

        if not winner_name:
            return {"action": "none", "reason": "No statistically significant winner"}

        exp = self.experiments[experiment_id]
        winner = next(v for v in exp.variants if v.name == winner_name)

        current = winner.traffic_percentage
        if current < 0.5:
            winner.traffic_percentage = 0.5
        elif current < 0.75:
            winner.traffic_percentage = 0.75
        elif current < 0.9:
            winner.traffic_percentage = 0.9
        else:
            winner.traffic_percentage = 1.0
            for v in exp.variants:
                if v != winner:
                    v.traffic_percentage = 0.0
            exp.status = ExperimentStatus.COMPLETED
            exp.ended_at = time.time()

        return {
            "action": "promoted",
            "variant": winner_name,
            "new_traffic": winner.traffic_percentage
        }


import asyncio

    def check_guardrails(self, exp_id: str, max_cost_regression: float = 0.1) -> bool:
        exp = self.experiments.get(exp_id)
        if not exp or len(exp.variants) < 2:
            return True
        t = exp.variants[1]; c = exp.variants[0]
        if c.total_cost > 0 and t.total_cost > 0:
            if t.total_cost / c.total_cost > 1 + max_cost_regression:
                return False
        return True

    async def get_metadata(self, exp_id: str) -> Dict:
        exp = self.experiments.get(exp_id)
        if not exp:
            return {}
        return {"name": exp_id, "variants": len(exp.variants), "total_cost": sum(v.total_cost for v in exp.variants), "total_latency": sum(v.total_latency for v in exp.variants)}

    def prune_stale(self, max_age_days: int = 30) -> int:
        import time
        now = time.time()
        threshold = now - (max_age_days * 86400)
        stale = [eid for eid, e in self.experiments.items() if getattr(e, "created_at", 0) < threshold]
        for eid in stale:
            del self.experiments[eid]
        return len(stale)
