class LocalProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "local"}

    def estimate_cost(self, request):
        return 0.0

    def estimate_latency(self, request):
        return 300
