# 07. Redis Distributed Lock vs Kafka

## Redis Distributed Lock
여러 서버가 동일한 외부/공유 작업을 동시에 수행하지 못하도록 coordination한다.

예:
```text
Server A ─┐
Server B ─┼→ lock:document:hash
Server C ─┘
```

주의:
- TTL
- owner token
- safe release
- lease expiry 중 작업 지속 문제
- 필요 시 fencing token

분산락이 정합성의 만능 해결책은 아니다. DB unique constraint/idempotency로 해결 가능하면 그 방법이 더 단순할 수 있다.

## Kafka
Kafka는 lock이 아니라 durable event stream이다.

예:
```text
CHAT_COMPLETED
  → analytics consumer
  → evaluation consumer
  → audit consumer
```

Kafka partition key를 conversation_id 등으로 잡아 동일 key 이벤트 순서를 유지할 수 있지만 이것이 distributed lock을 의미하지는 않는다.

## 언제 도입할까
Redis:
- 여러 FastAPI 인스턴스가 공유하는 job status
- rate limit
- short-lived coordination

Kafka:
- 하나의 이벤트를 여러 independent consumer가 소비
- event replay가 필요
- producer와 consumer 처리 속도를 분리
