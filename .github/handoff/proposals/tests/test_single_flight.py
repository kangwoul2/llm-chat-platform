"""경쟁 상태를 먼저 재현하고, single-flight 로 고친 뒤 같은 조건에서 비교한다.

현재 /api/v1/chat/async 의 흐름(app/api/chat.py)을 그대로 옮겼다:
    get → (LLMConcurrencyLimiter 안에서) LLM 호출 → put
쓰는 클래스는 모두 저장소의 실제 클래스다. 세마포어 코드는 수정하지 않고 그대로 가져다 쓴다.
"""
import asyncio

import pytest

from app.services.concurrency import LLMConcurrencyLimiter
from app.services.idempotency import CachedResult, InMemoryIdempotencyStore
from single_flight import SingleFlight


class CountingLLM:
    def __init__(self, delay=0.05):
        self.delay, self.calls, self.peak, self._now = delay, 0, 0, 0

    async def generate(self, message):
        self.calls += 1
        self._now += 1
        self.peak = max(self.peak, self._now)
        try:
            await asyncio.sleep(self.delay)
        finally:
            self._now -= 1
        return f"answer:{message}", self.delay * 1000


async def current_flow(store, limiter, llm, key, message):
    """app/api/chat.py 의 async_chat 과 같은 순서."""
    cached = await store.get(key)
    if cached:
        return cached.answer, "idempotency-hit"
    async with limiter:
        answer, _ = await llm.generate(message)
    await store.put(key, CachedResult(answer=answer, request_id="r"))
    return answer, "async"


async def fixed_flow(store, limiter, llm, flight, key, message):
    async def work():
        cached = await store.get(key)
        if cached:
            return cached.answer, "idempotency-hit"
        async with limiter:                       # 리더만 지난다. 세마포어는 그대로.
            answer, _ = await llm.generate(message)
        await store.put(key, CachedResult(answer=answer, request_id="r"))
        return answer, "async"

    (answer, route), led = await flight.do(key, work)
    return answer, route if led else "single-flight-join"


async def test_current_flow_calls_the_llm_once_per_concurrent_request():
    llm, limiter, store = CountingLLM(), LLMConcurrencyLimiter(10), InMemoryIdempotencyStore()
    results = await asyncio.gather(*[current_flow(store, limiter, llm, "same-key", "hi") for _ in range(20)])
    assert llm.calls == 20, "재현: 같은 키로 동시에 20건 → LLM 호출 20번 (멱등성 키가 있는데도)"
    assert len({a for a, _ in results}) == 1, "저장된 결과는 하나뿐이다 (setdefault)"


async def test_single_flight_reduces_the_same_burst_to_one_llm_call():
    llm, limiter, store, flight = CountingLLM(), LLMConcurrencyLimiter(10), InMemoryIdempotencyStore(), SingleFlight()
    results = await asyncio.gather(*[fixed_flow(store, limiter, llm, flight, "same-key", "hi") for _ in range(20)])
    assert llm.calls == 1
    assert flight.leaders == 1 and flight.joined == 19
    assert {a for a, _ in results} == {"answer:hi"}
    assert sorted(r for _, r in results).count("async") == 1


async def test_different_keys_are_not_merged():
    llm, limiter, store, flight = CountingLLM(), LLMConcurrencyLimiter(10), InMemoryIdempotencyStore(), SingleFlight()
    await asyncio.gather(*[fixed_flow(store, limiter, llm, flight, f"k{i}", "hi") for i in range(5)])
    assert llm.calls == 5


async def test_the_semaphore_limit_is_unchanged_by_single_flight():
    """합치기는 세마포어 바깥이다. 서로 다른 키 30건을 보내도 동시 호출은 한도(3)를 넘지 않는다."""
    llm, limiter, store, flight = CountingLLM(0.03), LLMConcurrencyLimiter(3), InMemoryIdempotencyStore(), SingleFlight()
    await asyncio.gather(*[fixed_flow(store, limiter, llm, flight, f"k{i}", "m") for i in range(30)])
    assert llm.calls == 30 and llm.peak <= 3


async def test_after_completion_a_new_request_with_the_same_key_hits_the_store():
    llm, limiter, store, flight = CountingLLM(), LLMConcurrencyLimiter(2), InMemoryIdempotencyStore(), SingleFlight()
    await fixed_flow(store, limiter, llm, flight, "k", "hi")
    answer, route = await fixed_flow(store, limiter, llm, flight, "k", "hi")
    assert route == "idempotency-hit" and llm.calls == 1


async def test_errors_reach_everyone_waiting_and_the_key_is_released():
    flight, attempts = SingleFlight(), []

    async def boom():
        attempts.append(1)
        await asyncio.sleep(0.02)
        raise RuntimeError("downstream")

    results = await asyncio.gather(*[flight.do("k", boom) for _ in range(5)], return_exceptions=True)
    assert all(isinstance(r, RuntimeError) for r in results) and len(attempts) == 1
    assert "k" not in flight._inflight, "실패 뒤에는 키가 풀려 다음 요청이 다시 시도할 수 있다"

    async def ok():
        return "fine"

    assert (await flight.do("k", ok)) == ("fine", True)


async def test_cancelled_leader_does_not_cancel_the_waiters():
    flight, runs = SingleFlight(), []

    async def slow():
        runs.append(1)
        await asyncio.sleep(0.3)
        return "done"

    leader = asyncio.create_task(flight.do("k", slow))
    await asyncio.sleep(0.02)
    waiter = asyncio.create_task(flight.do("k", slow))
    await asyncio.sleep(0.02)
    leader.cancel()
    with pytest.raises(asyncio.CancelledError):
        await leader
    result, led = await asyncio.wait_for(waiter, timeout=2)
    assert result == "done" and led is True, "기다리던 요청이 새 리더가 되어 끝까지 처리한다"
    assert len(runs) == 2
