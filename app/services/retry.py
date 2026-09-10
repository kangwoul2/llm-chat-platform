from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Awaitable, Callable, TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay_sec: float = 0.2
    max_delay_sec: float = 2.0
    jitter_ratio: float = 0.2

    def delay_for(self, attempt: int) -> float:
        exponential = min(self.max_delay_sec, self.base_delay_sec * (2 ** max(attempt - 1, 0)))
        jitter = exponential * self.jitter_ratio * random.random()
        return exponential + jitter


async def retry_async(
    operation: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    should_retry: Callable[[Exception], bool],
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt >= policy.max_attempts or not should_retry(exc):
                raise
            await sleep(policy.delay_for(attempt))
    assert last_error is not None
    raise last_error
