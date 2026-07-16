class MistralProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "mistral"}

    def estimate_cost(self, request):
        return 0.0003

    def estimate_latency(self, request):
        return 700
