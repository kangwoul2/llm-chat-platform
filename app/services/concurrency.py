import asyncio


class LLMConcurrencyLimiter:
    """Limits concurrent calls to a scarce downstream LLM resource."""

    def __init__(self, limit: int):
        self._semaphore = asyncio.Semaphore(limit)

    async def __aenter__(self):
        await self._semaphore.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._semaphore.release()
