class StabilityProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "stability"}

    def estimate_cost(self, request):
        return 0.01

    def estimate_latency(self, request):
        return 5000
