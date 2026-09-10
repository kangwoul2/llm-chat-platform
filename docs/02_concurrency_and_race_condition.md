# 02. Race Condition & Concurrency

## Race Condition

여러 실행 주체가 같은 상태를 동시에 읽고 수정해 **실행 순서에 따라 최종 결과가 달라지는 문제**다.

```text
count = 10

Thread A: READ 10
Thread B: READ 10
Thread A: WRITE 11
Thread B: WRITE 11

Expected = 12
Actual   = 11
```

이를 Lost Update라고 한다.

## 보호 범위에 따른 해결책

```text
CPU instruction
  → Atomic / CAS

Thread / Process memory
  → Mutex / Lock / Atomic variable

Database row
  → Atomic SQL / Transaction / Optimistic or Pessimistic Lock

Multiple application instances
  → DB constraint / Idempotency / Redis Distributed Lock

Event-driven processing
  → Partition key / Idempotent consumer / Unique constraint
```

## Mutex
한 번에 하나의 실행 흐름만 critical section에 들어가게 한다. 공유 상태 정합성에 적합하지만 범위를 너무 크게 잡으면 병렬성이 사라진다.

## Semaphore
동시에 N개까지만 접근하도록 한다. LLM 호출 같은 제한된 downstream resource 보호에 적합하다.

## Lock을 먼저 선택하지 않는 이유
Lock은 correctness를 높일 수 있지만 wait, deadlock, throughput 저하를 만든다. 가능한 경우 다음을 먼저 검토한다.

1. atomic operation
2. unique constraint
3. idempotency
4. optimistic concurrency
5. pessimistic lock
6. distributed lock
