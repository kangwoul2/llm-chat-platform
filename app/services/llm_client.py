import asyncio
import time
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings
from app.core.observability import LLM_IN_FLIGHT
from app.services.retry import RetryPolicy, retry_async


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, message: str) -> tuple[str, float]:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def __init__(self, settings: Settings):
        self.delay = settings.mock_llm_delay_ms / 1000

    async def generate(self, message: str) -> tuple[str, float]:
        started = time.perf_counter()
        LLM_IN_FLIGHT.inc()
        try:
            await asyncio.sleep(self.delay)
        finally:
            LLM_IN_FLIGHT.dec()
        elapsed = (time.perf_counter() - started) * 1000
        return f"[mock] {message}", elapsed


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client
        self.retry_policy = RetryPolicy(max_attempts=settings.llm_retry_attempts)

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
            return True
        if isinstance(exc, httpx.HTTPStatusError):
            return exc.response.status_code == 429 or exc.response.status_code >= 500
        return False

    async def generate(self, message: str) -> tuple[str, float]:
        started = time.perf_counter()

        async def request_once():
            LLM_IN_FLIGHT.inc()
            try:
                response = await self.client.post(
                    "/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
                    json={
                        "model": self.settings.llm_model,
                        "messages": [{"role": "user", "content": message}],
                    },
                )
                response.raise_for_status()
                return response.json()
            finally:
                LLM_IN_FLIGHT.dec()

        data = await retry_async(
            request_once,
            policy=self.retry_policy,
            should_retry=self._retryable,
        )
        elapsed = (time.perf_counter() - started) * 1000
        return data["choices"][0]["message"]["content"], elapsed
