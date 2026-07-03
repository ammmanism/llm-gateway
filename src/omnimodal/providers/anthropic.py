"""
Anthropic Provider
"""

class AnthropicProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "anthropic"}

    def estimate_cost(self, request):
        return 0.015

    def estimate_latency(self, request):
        return 1200
