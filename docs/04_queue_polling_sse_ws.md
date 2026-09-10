# 04. Queue, Polling, SSE, WebSocket

## Queue를 사용하는 이유
처리 capacity보다 빠르게 요청이 들어오면 즉시 모두 downstream에 보내는 대신 queue에 보관하고 worker가 제한된 속도로 처리한다.

```text
Incoming 100 req/s
Processor capacity 20 req/s
→ 초당 80개 backlog 발생
```

무한 queue는 해결이 아니다. max queue size와 admission control이 필요하다.

## Request ID
긴 작업을 `202 Accepted + job_id`로 분리하면 client connection을 작업 완료까지 붙잡을 필요가 없다.

## Polling
Client가 주기적으로 `GET /jobs/{id}` 호출.

장점: 단순, REST만으로 구현.
단점: 불필요한 request, polling interval만큼 notification delay.

## SSE
Server → Client 단방향 persistent stream.

장점: LLM token/status streaming에 적합, HTTP 기반.
단점: 양방향 상호작용에는 제한.

## WebSocket
Persistent bidirectional channel.

장점: client cancel, interactive event 등 양방향에 강함.
단점: 연결 상태/재연결/scale-out 운영이 더 복잡.

## 비교 지표
- job당 HTTP request 수
- transferred bytes
- active connection 수
- completion → client receive notification latency
- server CPU/memory
