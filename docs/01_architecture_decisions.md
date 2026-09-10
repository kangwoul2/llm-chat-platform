# 01. Architecture Decision Record

## ADR-001: Monolith First

### 후보
- 처음부터 MSA
- Modular Monolith
- 단일 파일 Monolith

### 선택
**Modular Monolith**로 시작한다.

### 이유
서비스를 분리하면 네트워크 실패, 배포, service discovery, distributed tracing 등 새로운 문제가 추가된다. 이 프로젝트의 첫 목표는 LLM I/O와 동시성 병목을 측정하는 것이므로 먼저 한 프로세스 안에서 API, service, storage, infrastructure 책임만 분리한다.

### MSA 전환 조건
- 특정 workload만 독립적으로 scale-out해야 할 필요가 측정됨
- ingestion/평가 작업이 chat latency에 영향을 줌
- 장애 격리가 실제 요구사항이 됨

---

## ADR-002: Async for LLM I/O

### 후보
1. blocking synchronous call
2. thread pool
3. async/await

### 선택
일반 chat path는 **async/await**.

### 이유
LLM 호출은 CPU 계산보다 원격 서버 응답 대기가 큰 I/O-bound workload다. await 동안 event loop는 다른 request를 진행할 수 있다.

### 주의
async는 한 사용자의 모델 생성 자체를 빠르게 만드는 기술이 아니다. 주요 개선 목표는 동시 요청 상황의 자원 활용과 throughput이다.

---

## ADR-003: Semaphore before Queue

### 후보
- unlimited concurrency
- semaphore
- explicit queue + worker

### 선택
짧은 chat 요청은 **Semaphore**, 긴 작업은 **Queue + Worker**.

### 이유
Semaphore는 최소한의 복잡도로 downstream 동시 호출 수를 제한한다. Queue는 status/priority/retry/queue wait이 필요한 작업에 사용한다.

---

## ADR-004: Polling as Baseline, SSE as Primary Streaming Candidate

Polling은 가장 단순한 비교 기준이다. LLM 결과는 주로 Server → Client 방향이므로 양방향 WebSocket보다 SSE가 더 작은 복잡도로 충분할 수 있다. WebSocket은 취소·양방향 이벤트가 필요한 경우 비교한다.

---

## ADR-005: Kafka is Event Flow, Redis Lock is Coordination

- Redis Distributed Lock: 여러 인스턴스 중 **누가 공유 자원을 수정할 수 있는지** 조정
- Kafka: **이벤트를 저장·전달하고 consumer가 비동기로 처리**

둘을 대체재로 취급하지 않는다.
