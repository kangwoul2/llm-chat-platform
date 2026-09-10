import asyncio
from dataclasses import dataclass


@dataclass
class CachedResult:
    answer: str
    request_id: str


class InMemoryIdempotencyStore:
    """MVP idempotency store. Replace with Redis/PostgreSQL for multi-instance deployments."""

    def __init__(self):
        self._values: dict[str, CachedResult] = {}
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> CachedResult | None:
        async with self._lock:
            return self._values.get(key)

    async def put(self, key: str, value: CachedResult) -> None:
        async with self._lock:
            self._values.setdefault(key, value)
