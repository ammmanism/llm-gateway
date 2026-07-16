class HuggingFaceProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "huggingface"}

    def estimate_cost(self, request):
        return 0.0001

    def estimate_latency(self, request):
        return 1200
