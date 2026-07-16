class ReplicateProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "replicate"}

    def estimate_cost(self, request):
        return 0.05

    def estimate_latency(self, request):
        return 15000
