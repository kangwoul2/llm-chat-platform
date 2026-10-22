"""같은 키의 동시 요청을 하나로 합치기 (제안 — 기존 코드는 수정하지 않음).

문제 (docs/12_known_limitations.md 의 2번)
  /api/v1/chat/async 는 `조회(get) → LLM 호출 → 저장(put)` 순서다. 같은 idempotency_key 가 동시에 두 번 오면
  둘 다 조회에서 "없음"을 보고 둘 다 LLM 을 호출한다. put() 은 setdefault 라 결과는 하나로 남지만,
  외부 LLM 호출과 비용은 이미 두 번 나갔다. (tests/test_single_flight.py 가 이 경쟁 상태를 숫자로 재현한다)

제안
  키별로 "진행 중인 작업"을 하나만 만들고, 같은 키의 나중 요청은 그 결과를 기다려 받는다. (single-flight)

  이 합치기는 세마포어(LLMConcurrencyLimiter) *바깥*에 둔다.
    - 합쳐진 요청은 LLM 슬롯을 쓰지 않으므로 동시 호출 제한 수치의 의미가 바뀌지 않는다.
    - 리더 한 명만 기존과 똑같이 `async with limiter` 를 지나간다. 세마포어 코드는 한 줄도 건드리지 않는다.

주의
  - 프로세스 안에서만 합친다. 서버가 여러 대면 서버 간 중복은 Redis 락이나 DB 유일성 제약조건이 필요하다.
  - 리더가 취소되면 기다리던 요청이 연쇄로 취소되지 않도록, 남은 요청 중 하나가 새 리더가 되어 다시 시도한다.
"""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable, Generic, TypeVar

T = TypeVar("T")


class SingleFlight(Generic[T]):
    def __init__(self) -> None:
        self._inflight: dict[str, asyncio.Future[T]] = {}
        self.leaders = 0       # 실제로 작업을 실행한 횟수 (측정·테스트용)
        self.joined = 0        # 남의 작업 결과를 받아 간 횟수

    async def do(self, key: str, fn: Callable[[], Awaitable[T]]) -> tuple[T, bool]:
        """(결과, 이 호출이 직접 실행했는가)"""
        while True:
            fut = self._inflight.get(key)
            if fut is None:
                fut = asyncio.get_running_loop().create_future()
                self._inflight[key] = fut
                self.leaders += 1
                try:
                    result = await fn()
                except asyncio.CancelledError:
                    fut.cancel()                      # 기다리던 요청은 CancelledError 를 받고 새 리더가 되어 재시도한다
                    raise
                except BaseException as exc:          # noqa: BLE001 — 기다리던 요청에게 같은 오류를 전달한다
                    fut.set_exception(exc)
                    fut.exception()                   # 기다리는 요청이 없어도 'never retrieved' 경고가 나지 않게
                    raise
                else:
                    fut.set_result(result)
                    return result, True
                finally:
                    if self._inflight.get(key) is fut:
                        del self._inflight[key]
            try:
                result = await asyncio.shield(fut)
            except asyncio.CancelledError:
                if fut.cancelled() and not asyncio.current_task().cancelling():
                    continue                          # 리더가 취소됐을 뿐 나는 아니다 → 다시 시도
                raise
            self.joined += 1
            return result, False
