# 05. Connection Pool

## Connection
Client와 server 사이에서 TCP 상태를 유지하는 통신 관계다. HTTPS라면 TCP 연결 외 TLS handshake 비용도 고려해야 한다.

## Connection reuse
매 요청마다 연결을 새로 만드는 대신 기존 keep-alive connection을 재사용한다.

## Pool
여러 reusable connection을 관리하는 집합.

이 프로젝트는 application lifespan 동안 하나의 `httpx.AsyncClient`를 유지한다.

```text
Request A ─┐
Request B ─┼→ AsyncClient Connection Pool → LLM API
Request C ─┘
```

## 너무 큰 Pool의 문제
Pool이 downstream capacity보다 크면 429, timeout, socket 증가를 유발한다. Pool size와 application semaphore는 별개이며 함께 조정해야 한다.

## 실험
- client per request
- shared client + keep-alive pool

측정:
- connection count
- TLS/TCP handshake 횟수(가능한 경우 packet/tool 관찰)
- p95 latency
- RPS
