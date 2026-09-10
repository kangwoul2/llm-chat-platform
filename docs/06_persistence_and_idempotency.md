# 06. Persistence, Transaction, Idempotency

## 대화 영구 저장
브라우저 DOM만 사용하면 새로고침 시 대화가 사라진다. 실제 서비스에서는 PostgreSQL을 source of truth로 사용한다.

```text
Conversation
- id
- title
- created_at

Message
- id
- conversation_id
- role
- content
- status
- created_at
```

Redis는 job status, session, rate-limit처럼 빠르고 일시적인 shared state에 사용한다.

## 외부 API를 DB Transaction 안에 오래 넣지 않는다

나쁜 예:
```text
BEGIN
message insert
10초 LLM call
assistant insert
COMMIT
```

DB connection/lock을 장시간 점유할 수 있다.

더 나은 흐름:
```text
짧은 transaction: user message + pending record
→ LLM call
→ 짧은 transaction: answer + completed
```

## Idempotency
같은 요청이 retry되어도 최종 상태가 한 번 처리한 것과 같게 만든다.

MVP는 in-memory store를 제공하지만 multi-instance에서는 Redis/PostgreSQL unique constraint로 이전해야 한다.
