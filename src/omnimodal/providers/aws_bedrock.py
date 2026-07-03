class AWSBedrockProvider:
    def health_check(self):
        return {"status": "healthy", "provider": "aws_bedrock"}

    def estimate_cost(self, request):
        return 0.001

    def estimate_latency(self, request):
        return 900
