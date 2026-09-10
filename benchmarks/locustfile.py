from locust import HttpUser, between, task


class LLMBackendUser(HttpUser):
    wait_time = between(0.1, 0.5)

    @task(1)
    def sync_baseline(self):
        self.client.post("/api/v1/chat/sync-baseline", json={"message": "benchmark"}, name="sync-baseline")

    @task(1)
    def async_chat(self):
        self.client.post("/api/v1/chat/async", json={"message": "benchmark"}, name="async-chat")
