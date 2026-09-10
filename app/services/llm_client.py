import asyncio
import time
from abc import ABC, abstractmethod

import httpx

from app.core.config import Settings


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, message: str) -> tuple[str, float]:
        raise NotImplementedError


class MockLLMClient(LLMClient):
    def __init__(self, settings: Settings):
        self.delay = settings.mock_llm_delay_ms / 1000

    async def generate(self, message: str) -> tuple[str, float]:
        started = time.perf_counter()
        await asyncio.sleep(self.delay)
        elapsed = (time.perf_counter() - started) * 1000
        return f"[mock] {message}", elapsed


class OpenAICompatibleLLMClient(LLMClient):
    def __init__(self, settings: Settings, client: httpx.AsyncClient):
        self.settings = settings
        self.client = client

    async def generate(self, message: str) -> tuple[str, float]:
        started = time.perf_counter()
        response = await self.client.post(
            "/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.llm_api_key}"},
            json={
                "model": self.settings.llm_model,
                "messages": [{"role": "user", "content": message}],
            },
        )
        response.raise_for_status()
        data = response.json()
        elapsed = (time.perf_counter() - started) * 1000
        return data["choices"][0]["message"]["content"], elapsed
