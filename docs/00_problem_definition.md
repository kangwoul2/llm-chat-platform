# 00. Problem Definition

## 프로젝트 한 줄 정의

**LLM API를 사용하는 백엔드에서 I/O 대기, 동시 요청 폭주, 장시간 작업, 상태 전달 방식이 시스템 성능에 미치는 영향을 직접 구현하고 정량 비교하는 프로젝트**다.

## 왜 이 프로젝트를 만드는가

일반적인 LLM 데모는 `request → LLM → response`까지만 구현한다. 그러나 실제 서비스에서는 다음 문제가 발생한다.

1. 외부 LLM 응답을 기다리는 동안 서버 자원이 비효율적으로 사용될 수 있다.
2. async로 전환해도 downstream LLM에 무제한 요청을 보내면 429, timeout, connection saturation이 발생할 수 있다.
3. 긴 작업은 HTTP 요청을 계속 유지하는 것보다 Job으로 분리하는 편이 나을 수 있다.
4. Job 결과를 Polling, SSE, WebSocket 중 어떤 방식으로 전달할지에 따라 네트워크 비용과 사용자 체감 지연이 달라진다.
5. 다중 인스턴스로 확장하면 메모리 Queue, in-memory idempotency, mutex가 더 이상 전역 상태를 보호하지 못한다.
6. Redis Distributed Lock, Kafka 같은 기술은 역할이 다르며 실제 문제가 있을 때 선택해야 한다.

## 핵심 연구 질문

- Sync와 End-to-End Async는 동시 사용자 증가 시 Throughput/p95에 어떤 차이를 만드는가?
- 적정 Semaphore 크기는 어떻게 결정해야 하는가?
- HTTP Connection Pool 재사용은 연결 생성 비용을 얼마나 줄이는가?
- Queue를 넣었을 때 처리 안정성과 Queue Wait의 trade-off는 무엇인가?
- Polling/SSE/WebSocket은 결과 전달 비용에서 어떻게 다른가?
- 멱등성은 retry 중복 처리를 어디까지 막아야 하는가?
- 단일 인스턴스 mutex, DB lock, Redis distributed lock은 각각 어떤 범위를 보호하는가?
- Kafka는 lock이 아니라면 어떤 문제를 해결하는가?
