class GoogleProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "google"}

    def estimate_cost(self, request):
        return 0.0005

    def estimate_latency(self, request):
        return 1000
