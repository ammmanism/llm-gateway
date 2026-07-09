import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

CARBON_INTENSITY = {
    "us-east": 400,
    "us-west": 200,
    "eu-west": 300,
    "eu-north": 50,
    "ap-south": 700,
    "ap-northeast": 500,
}

ENERGY_PER_TOKEN = {
    "gpt-4.1": 0.4,
    "gpt-4.1-mini": 0.15,
    "gemini-2.5-flash": 0.08,
    "gemini-2.5-pro": 0.35,
    "claude-4-sonnet": 0.3,
    "claude-4-opus": 0.7,
    "gpt-4o": 0.5,
    "gpt-4-turbo": 1.0,
    "claude-3-opus": 0.8,
    "claude-3-sonnet": 0.4,
    "claude-3-haiku": 0.1,
    "dall-e-3": 100.0,
    "stable-diffusion-3": 80.0,
    "whisper-1": 2.0,
    "tts-1": 1.0,
}


@dataclass
class CarbonEstimate:
    grams_co2: float
    energy_joules: float
    region: str
    model: str
    tokens_input: int
    tokens_output: int
    equivalent_car_km: float
    equivalent_tree_hours: float


class CarbonTracker:
    def __init__(self, default_region: str = "us-east"):
        self.default_region = default_region
        self.total_co2_grams = 0.0
        self.total_energy_joules = 0.0
        self.request_count = 0

    def estimate(
        self,
        model: str,
        tokens_input: int,
        tokens_output: int,
        region: str | None = None,
    ) -> CarbonEstimate:
        region = region or self.default_region
        intensity = CARBON_INTENSITY.get(region, 400)
        energy_per_token = ENERGY_PER_TOKEN.get(model, 0.5)

        total_tokens = tokens_input + tokens_output
        energy_joules = total_tokens * energy_per_token

        energy_kwh = energy_joules / 3_600_000
        grams_co2 = energy_kwh * intensity * 1000

        car_km = grams_co2 / 120
        tree_hours = grams_co2 / 60

        return CarbonEstimate(
            grams_co2=grams_co2,
            energy_joules=energy_joules,
            region=region,
            model=model,
            tokens_input=tokens_input,
            tokens_output=tokens_output,
            equivalent_car_km=car_km,
            equivalent_tree_hours=tree_hours,
        )

    def track(self, estimate: CarbonEstimate):
        self.total_co2_grams += estimate.grams_co2
        self.total_energy_joules += estimate.energy_joules
        self.request_count += 1

    def get_report(self) -> dict:
        return {
            "total_co2_grams": round(self.total_co2_grams, 2),
            "total_co2_kg": round(self.total_co2_grams / 1000, 4),
            "total_energy_kwh": round(self.total_energy_joules / 3_600_000, 4),
            "request_count": self.request_count,
            "avg_per_request_g": round(
                self.total_co2_grams / max(self.request_count, 1), 4
            ),
            "equivalent_car_km": round(self.total_co2_grams / 120, 2),
            "equivalent_tree_hours": round(self.total_co2_grams / 60, 2),
            "recommendations": self._get_recommendations(),
        }

    def _get_recommendations(self) -> list:
        recs = []
        if self.total_co2_grams > 1000:
            recs.append(
                "Consider using eu-north region (Sweden) for 8x lower carbon intensity"
            )
        if self.request_count > 0:
            recs.append("Enable semantic caching to reduce redundant compute")
            recs.append("Use model downgrading for simple tasks")
        return recs

    def optimize_region(
        self, model: str, tokens_input: int, tokens_output: int, allowed_regions: list
    ) -> str:
        estimates = {
            region: self.estimate(model, tokens_input, tokens_output, region)
            for region in allowed_regions
        }
        return min(estimates, key=lambda r: estimates[r].grams_co2)


class CarbonBudgetEnforcer:
    def __init__(self, max_grams_per_day: float = 1000.0):
        self.max_grams = max_grams_per_day
        self.daily_usage: dict[str, float] = {}

    def check_budget(self, user_id: str, estimated_grams: float) -> bool:
        current = self.daily_usage.get(user_id, 0)
        return current + estimated_grams <= self.max_grams

    def consume(self, user_id: str, grams: float):
        self.daily_usage[user_id] = self.daily_usage.get(user_id, 0) + grams

    def reset_daily(self):
        self.daily_usage.clear()

    async def auto_reset_daily(self):
        while True:
            await asyncio.sleep(86400)
            self.reset_daily()

    def carbon_prometheus_metric(self):
        try:
            from prometheus_client import Counter

            c = Counter("carbon_footprint_grams", "Total carbon footprint in grams")
            c.inc(self.total_co2_grams)
        except ImportError:
            pass

    def carbon_prometheus_metric(self):
        try:
            from prometheus_client import Counter
            c = Counter("carbon_footprint_grams", "Total carbon footprint in grams")
            c.inc(self.total_carbon)
        except ImportError:
            pass
