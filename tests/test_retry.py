import asyncio

import pytest

from app.services.retry import RetryPolicy, retry_async


@pytest.mark.asyncio
async def test_retry_eventually_succeeds():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise TimeoutError("temporary")
        return "ok"

    async def no_sleep(_: float):
        await asyncio.sleep(0)

    result = await retry_async(
        operation,
        policy=RetryPolicy(max_attempts=3, jitter_ratio=0),
        should_retry=lambda exc: isinstance(exc, TimeoutError),
        sleep=no_sleep,
    )
    assert result == "ok"
    assert attempts == 3


@pytest.mark.asyncio
async def test_non_retryable_error_fails_immediately():
    attempts = 0

    async def operation():
        nonlocal attempts
        attempts += 1
        raise ValueError("bad request")

    with pytest.raises(ValueError):
        await retry_async(
            operation,
            policy=RetryPolicy(max_attempts=3),
            should_retry=lambda _: False,
        )
    assert attempts == 1
