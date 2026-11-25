from locust import HttpUser, between, task


class NeurocacheUser(HttpUser):
    wait_time = between(0.2, 1.0)

    def on_start(self):
        self.api_key = "test_key_pro"

    @task(8)
    def chat_completion(self):
        self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": "gpt-4o-mini",
                "messages": [
                    {
                        "role": "user",
                        "content": "Explain semantic caching in one paragraph",
                    }
                ],
                "max_tokens": 120,
            },
        )

    @task(2)
    def cache_stats(self):
        self.client.get(
            "/v1/cache/stats", headers={"Authorization": f"Bearer {self.api_key}"}
        )
