<div align="center">

# Reliable LLM Chatbot Backend

### Grounded RAG · Async I/O · Backpressure · Streaming · Observability

FastAPI 기반 LLM 챗봇을 단순 기능 구현에서 끝내지 않고, **느린 외부 LLM과 동시 요청을 안정적으로 다루는 백엔드 시스템**으로 확장한 프로젝트입니다.

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Async%20API-009688?style=flat-square&logo=fastapi&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Persistence-4169E1?style=flat-square&logo=postgresql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-Coordination-DC382D?style=flat-square&logo=redis&logoColor=white)
![Kafka](https://img.shields.io/badge/Kafka-Optional%20Events-231F20?style=flat-square&logo=apachekafka&logoColor=white)

</div>

---

## Executive Summary

LLM 기반 API의 가장 큰 특징 중 하나는 서버가 직접 계산하는 시간보다 **외부 provider 응답을 기다리는 I/O 시간이 길다**는 점입니다. 단순한 구현은 다음처럼 시작할 수 있습니다.

```text
Client → API → LLM → Response
```

하지만 동시 요청이 증가하면 문제는 달라집니다.

```text
동시 요청 증가
   ↓
외부 LLM 대기 증가
   ↓
in-flight request 증가
   ↓
provider rate limit / timeout / tail latency 증가
   ↓
무제한 concurrency를 허용할 수 없음
   ↓
Semaphore / Queue / Retry / Backpressure 필요
   ↓
긴 작업은 request lifetime에서 분리할 필요
   ↓
Polling / SSE / WebSocket 전달 방식 선택 필요
   ↓
RAG에서는 성능 문제와 별개로 근거 없는 응답 문제도 발생
```

따라서 이 프로젝트는 두 축을 분리해 다룹니다.

```text
Backend Reliability
- Async I/O
- Connection Pool
- Semaphore
- Bounded Queue
- Retry / Timeout
- Idempotency
- Polling / SSE / WebSocket
- Metrics

Grounded Answer Quality
- Knowledge ingestion
- Retrieval
- Score threshold
- No-context guard
- Source reporting
```

핵심 원칙은 **"기술을 많이 쓰는 것"이 아니라, 문제가 발생하는 경계를 먼저 정의하고 가장 작은 해결책부터 적용하는 것**입니다.

---

## 1. Problem Definition

### 1.1 LLM은 CPU-bound workload가 아니다

현재 workload의 주요 병목은 외부 LLM provider 응답 대기입니다.

서버 관점에서 다음 시간이 길게 발생합니다.

```text
request parsing
     ↓
network send
     ↓
-------------------------
external LLM waiting time
-------------------------
     ↓
response parsing
```

따라서 CPU 연산을 병렬화하는 방식보다 **I/O 대기 동안 event loop가 다른 요청을 처리할 수 있는 Async 구조**가 자연스러운 출발점입니다.

다만 `async` 자체가 provider의 한 요청 latency를 줄여주는 것은 아닙니다.

이 프로젝트에서 Async의 목적은:

- 동일 시간 동안 더 많은 I/O-bound request를 관리하고
- worker/thread 점유를 줄이며
- downstream concurrency를 명시적으로 제어하기 위함입니다.

---

### 1.2 Async만 적용하면 오히려 provider를 과부하시킬 수 있다

Async API는 많은 요청을 동시에 시작하기 쉽습니다.

```text
100 Requests
    ↓
Async endpoint
    ↓
100 downstream calls
    ↓
LLM Provider
    ↓
429 / timeout / saturation
```

그래서 `asyncio.Semaphore`를 downstream 호출 경계에 둡니다.

```text
incoming concurrency != downstream concurrency
```

즉 서버가 100개의 요청을 받을 수 있더라도 LLM으로 동시에 보내는 호출 수는 별도 제한합니다.

---

### 1.3 모든 대기 요청을 Semaphore에만 맡길 것인가?

짧은 작업은 Semaphore만으로 충분할 수 있지만, 처리 시간이 길어지거나 대기 요청 자체를 관리해야 한다면 문제가 생깁니다.

필요한 정보가 달라집니다.

- 지금 몇 건이 기다리는가?
- 대기 시간이 얼마나 되는가?
- 요청을 취소할 수 있는가?
- 서버 재시작 후 상태를 어떻게 복구할 것인가?
- Queue가 가득 찼을 때 요청을 계속 받을 것인가?

이 시점에서 **bounded Queue + Worker + Request ID** 구조로 확장합니다.

---

### 1.4 RAG에서는 빠른 응답보다 틀린 응답이 더 큰 문제일 수 있다

검색 결과가 없는데도 LLM에게 질문을 보내면 모델은 자연스러운 문장을 생성할 수 있습니다.

```text
질문
 ↓
검색 결과 없음
 ↓
LLM 호출
 ↓
그럴듯하지만 근거 없는 답변
```

V2에서는 검색 결과의 최고 score가 기준보다 낮으면 LLM을 호출하지 않습니다.

```text
Question
   ↓
BM25 Retrieval
   ↓
top score >= threshold ?
    /              \
  yes               no
   ↓                 ↓
LLM with context   No-context response
```

현재 기본 threshold는 `0.55`이며, 근거가 없을 때는 명시적으로 답변을 중단합니다.

---

## 2. System Architecture

![System Architecture](docs/assets/system_architecture.svg)

```text
Client
  │
  ▼
FastAPI
  │
  ├─ Request ID / Metrics
  │
  ├─ Direct Async Chat
  │      │
  │      ▼
  │   Semaphore
  │      │
  │      ▼
  │ Shared httpx.AsyncClient
  │      │
  │      ▼
  │     LLM
  │
  ├─ Grounded Knowledge Chat
  │      │
  │      ▼
  │ BM25 Retrieval
  │      │
  │ Score Guard
  │      │
  │      ▼
  │ Context-only LLM Prompt
  │
  └─ Long-running Job
         │
         ▼
      Bounded Queue
         │
         ▼
       Worker
         │
         ├─ Polling
         ├─ SSE
         └─ WebSocket
```

### Responsibility Boundary

| Component | Responsibility |
|---|---|
| FastAPI | HTTP contract, request lifecycle |
| RequestContextMiddleware | correlation ID, request metric |
| Shared AsyncClient | HTTP connection reuse |
| Semaphore | active downstream concurrency 제한 |
| Bounded Queue | waiting work와 overload를 명시적으로 관리 |
| Worker | queue에서 실제 처리 실행 |
| KnowledgeStore | document 저장 및 retrieval index |
| GroundedChatService | retrieval → threshold → context-only generation |
| PostgreSQL scaffold | conversation/message source of truth 확장 지점 |
| Redis adapter | multi-instance coordination 확장 지점 |
| Kafka adapter | analytics/evaluation event stream 확장 지점 |

---

## 3. Implemented Features

### 3.1 Controlled Sync Baseline

```http
POST /api/v1/chat/sync-baseline
```

Mock provider에서만 활성화되는 실험용 endpoint입니다.

FastAPI의 synchronous `def` endpoint가 worker thread에서 blocking sleep을 수행하도록 구성해 baseline을 만듭니다.

중요한 점은 이 endpoint를 "sync는 무조건 나쁘다"는 증거로 사용하지 않는 것입니다. FastAPI는 sync route를 thread pool에서 실행하기 때문에 실험 시 worker/thread 설정도 함께 기록해야 합니다.

---

### 3.2 End-to-End Async Chat

```http
POST /api/v1/chat/async
```

```json
{
  "message": "hello",
  "idempotency_key": "request-001"
}
```

흐름:

```text
HTTP Request
   ↓
Idempotency lookup
   ↓
Semaphore acquire
   ↓
Async LLM call
   ↓
Result cache
   ↓
HTTP Response
```

---

### 3.3 Shared HTTP Connection Pool

프로세스 lifecycle 동안 하나의 `httpx.AsyncClient`를 재사용합니다.

대안은 요청마다 client를 새로 만드는 방식입니다.

```text
Per-request client
→ TCP/TLS connection 생성 반복 가능
→ connection setup overhead

Shared client
→ keep-alive connection reuse
→ bounded connection pool
```

Connection pool의 크기도 무조건 크게 설정하지 않습니다. 너무 큰 pool은 downstream service에 과도한 connection을 만들 수 있으므로 concurrency limit과 함께 결정해야 합니다.

---

### 3.4 Retry with Exponential Backoff

모든 오류를 재시도하지 않습니다.

현재 retry 대상:

```text
Timeout
Network Error
HTTP 429
HTTP 5xx
```

재시도하지 않는 오류 예:

```text
400 Bad Request
401 Unauthorized
validation error
```

정책:

```text
attempt 1
  ↓ fail
base delay + jitter
  ↓
attempt 2
  ↓ fail
exponential delay + jitter
  ↓
attempt 3
```

무제한 retry는 장애 시 더 많은 부하를 만드는 retry storm으로 이어질 수 있기 때문에 최대 시도 횟수를 제한합니다.

---

### 3.5 Bounded Queue and Backpressure

긴 작업은 Request ID를 발급하고 queue에 저장합니다.

```http
POST /api/v1/jobs
```

```json
{
  "job_id": "...",
  "status": "QUEUED"
}
```

Queue가 가득 찼을 때 계속 메모리를 늘리는 대신 요청을 거절합니다.

```text
Queue capacity reached
        ↓
Admission Control
        ↓
HTTP 429
```

Queue는 latency를 줄이는 기술이 아닙니다. 오히려 대기 시간이 생깁니다.

도입 목적은:

- overload를 메모리 안에서 무한정 쌓지 않고
- 처리 중인 작업과 대기 작업을 분리하고
- queue wait를 관찰 가능하게 만들기 위함입니다.

---

## 4. Polling vs SSE vs WebSocket

Job 완료 상태를 전달하는 세 방식을 모두 구현해 비교할 수 있게 했습니다.

### Polling

```text
Client ─ GET ─▶ Server
Client ─ GET ─▶ Server
Client ─ GET ─▶ Server
```

장점:
- 단순함
- 연결이 끊겨도 다음 요청으로 복구 쉬움

비용:
- 완료되지 않은 상태에서도 반복 HTTP request
- polling interval만큼 결과 인지 지연 가능

### SSE

```text
Client ───── connection ─────▶ Server
Client ◀── server events ───── Server
```

장점:
- 서버 → 클라이언트 단방향 업데이트에 자연스러움
- LLM token/status streaming에 적합

### WebSocket

```text
Client ◀════════════════════▶ Server
```

장점:
- 양방향 실시간 통신

비용:
- connection lifecycle과 scale-out 시 connection state 관리가 더 복잡함

따라서 이 프로젝트에서는 **양방향 메시징 요구가 없는 단순 LLM streaming/status는 SSE가 더 작은 해결책일 수 있다**는 가설을 실험 대상으로 둡니다.

---

## 5. Grounded Knowledge API

### Document Upsert

```http
POST /api/v1/knowledge/documents
```

```json
{
  "document_id": "policy-001",
  "content": "...",
  "source": "internal-policy"
}
```

### Grounded Query

```http
POST /api/v1/knowledge/query
```

```json
{
  "question": "문서에 있는 정책을 설명해줘"
}
```

응답에는 다음 정보를 포함합니다.

```text
request_id
grounded
sources
top_score
llm_ms
total_ms
```

이 구조의 목적은 LLM 응답만 반환하는 것이 아니라 **검색 근거와 처리 시간을 함께 관찰**하는 것입니다.

---

## 6. Observability

Prometheus format의 `/metrics` endpoint를 제공합니다.

현재 주요 metric:

| Metric | Meaning |
|---|---|
| `chat_platform_http_requests_total` | method/route/status별 요청 수 |
| `chat_platform_http_request_duration_seconds` | endpoint latency histogram |
| `chat_platform_llm_in_flight` | 현재 진행 중인 LLM 호출 수 |
| `chat_platform_rag_answers_total` | grounded / no-context 결과 수 |

모든 HTTP response에는 `X-Request-ID`를 반환하여 client log와 server log를 연결할 수 있습니다.

---

## 7. Performance Measurement Strategy

성능 개선은 다음 순서로만 기록합니다.

```text
1. Baseline 환경 고정
2. Hypothesis 작성
3. 단 하나의 변수 변경
4. 동일 workload 재실행
5. raw result 저장
6. p50 / p95 / p99 / RPS / Error 비교
7. trade-off 해석
```

### Primary Metrics

| Metric | Why |
|---|---|
| Throughput (RPS) | 단위 시간 처리량 |
| p50 latency | 일반적인 요청 경험 |
| p95 / p99 | tail latency와 saturation 관찰 |
| Error Rate | throughput 증가가 실패 증가로 얻어진 것인지 확인 |
| LLM in-flight | downstream pressure 관찰 |
| Queue Wait | overload가 queue latency로 이동했는지 확인 |
| Processing Time | 실제 worker 처리 시간 |
| Notification Delay | 완료 후 client 인지까지 시간 |

### Experiment Matrix

```text
E1. Sync baseline vs Async
E2. Unlimited concurrency vs Semaphore N
E3. New HTTP client/request vs Shared Pool
E4. Direct request vs Bounded Queue under overload
E5. Polling vs SSE vs WebSocket
E6. Retrieval threshold / no-context behavior
```

실측하지 않은 수치는 성과로 적지 않습니다. 기존 `docs/09_sample_report.md`는 분석 파이프라인 검증용 synthetic example이며 실제 결과와 명시적으로 분리합니다.

---

## 8. Consistency and Race Conditions

### In-memory Idempotency MVP

현재 idempotency store는 동일 key에 대한 완료 결과 재사용을 지원합니다.

하지만 다음 race는 여전히 학습용 limitation으로 남아 있습니다.

```text
Request A: GET key → miss
Request B: GET key → miss
Request A: process
Request B: process
Request A: PUT
Request B: PUT
```

즉 `get → process → put` 전체가 atomic하지 않습니다.

Multi-instance 단계에서는 다음 대안을 비교할 수 있습니다.

```text
DB UNIQUE constraint
Redis SET NX
in-flight future sharing
idempotency record table
```

분산락은 가장 먼저 선택하지 않습니다. 더 작은 원자적 연산이나 unique constraint로 해결 가능한지 먼저 확인합니다.

---

## 9. Redis and Kafka: Why They Are Not the Same Tool

### Redis

이 프로젝트에서 Redis가 필요한 시점:

- 여러 application instance가 job state를 공유해야 할 때
- rate limit state를 공유할 때
- distributed coordination이 필요할 때

### Kafka

Kafka가 필요한 시점:

- chat completion event를 여러 consumer가 독립 소비할 때
- evaluation / analytics / audit pipeline을 API request와 분리할 때
- replay 가능한 event history가 필요할 때

```text
Redis → shared state / coordination
Kafka → event stream / replay / consumer decoupling
```

Kafka를 distributed lock 용도로 사용하지 않습니다.

---

## 10. Data Persistence Boundary

PostgreSQL schema scaffold에는 Conversation과 Message 모델이 정의되어 있습니다.

```text
Conversation 1 ───── N Message
```

DB transaction 안에서 LLM network call 전체를 기다리지 않는 것을 원칙으로 합니다.

```text
Bad
BEGIN TX
  ↓
LLM call 3~20 sec
  ↓
DB update
COMMIT

Better
short DB operation
  ↓
external LLM I/O
  ↓
short DB operation
```

외부 I/O 때문에 transaction과 DB connection을 오래 점유하지 않도록 transaction boundary를 좁게 유지하는 방향입니다.

---

## 11. Test Strategy

현재 테스트는 다음을 다룹니다.

```text
test_smoke.py
→ mock LLM async behavior

test_retrieval.py
→ document retrieval / grounding threshold

test_retry.py
→ retry count / non-retryable error behavior
```

CI:

```bash
python -m compileall -q app tests benchmarks
pytest -q
```

GitHub Actions에서 Python 3.11 기준으로 실행합니다.

---

## 12. Project Structure

```text
.
├── app/
│   ├── api/
│   │   ├── chat.py
│   │   ├── jobs.py
│   │   └── knowledge.py
│   ├── core/
│   │   ├── config.py
│   │   ├── metrics.py
│   │   └── observability.py
│   ├── rag/
│   │   ├── retrieval.py
│   │   ├── service.py
│   │   └── store.py
│   ├── services/
│   │   ├── concurrency.py
│   │   ├── idempotency.py
│   │   ├── job_service.py
│   │   ├── llm_client.py
│   │   └── retry.py
│   ├── infrastructure/
│   │   ├── redis_lock.py
│   │   └── kafka_events.py
│   └── storage/
├── benchmarks/
├── docs/
├── tests/
├── web/
├── docker-compose.yml
└── README.md
```

---

## 13. Run Locally

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Swagger:

```text
http://localhost:8000/docs
```

Dashboard:

```text
http://localhost:8000/dashboard/
```

PostgreSQL + Redis:

```bash
docker compose up -d postgres redis
```

Kafka profile:

```bash
docker compose --profile kafka up -d
```

기본 provider는 API key가 필요 없는 mock implementation이므로 인프라와 concurrency 실험을 외부 API 비용과 분리할 수 있습니다.

---

## 14. Known Limitations

현재 구현을 production-ready라고 과장하지 않습니다.

1. JobStore가 process memory 기반이므로 restart 시 상태가 사라집니다.
2. in-memory idempotency는 simultaneous duplicate를 완전히 atomic하게 차단하지 않습니다.
3. BM25 KnowledgeStore는 single-process prototype이며 large-scale vector retrieval이 아닙니다.
4. SSE/WebSocket status endpoint 내부 구현에는 단순 polling이 포함되어 있습니다.
5. PostgreSQL schema는 scaffold이며 모든 API path에 persistence가 연결된 상태는 아닙니다.
6. Redis/Kafka adapter는 역할 경계를 학습하기 위한 확장 지점이며 모든 요청이 이를 사용하지 않습니다.
7. 실제 LLM provider의 rate limit과 token streaming 특성은 provider별 별도 측정이 필요합니다.

이 제한 사항을 숨기기보다 다음 개선 우선순위를 결정하는 근거로 사용합니다.

---

## 15. Architecture Decisions

### Why Async instead of simply increasing threads?

I/O 대기 workload에서는 thread 수를 계속 늘리면 thread stack, scheduling, context switching 비용도 증가합니다. Async는 적은 execution resource로 많은 waiting task를 관리하기 위한 선택입니다.

### Why Semaphore before Queue?

짧은 요청에서 필요한 것이 단순히 downstream 동시 호출 제한이라면 Semaphore가 더 작은 해결책입니다. Queue는 대기 상태, admission control, worker lifecycle이 필요할 때 도입합니다.

### Why SSE before WebSocket for token/status streaming?

서버가 client로 일방향 update만 보내면 SSE가 protocol과 운영 복잡도가 더 작습니다. client→server 실시간 메시지가 필요할 때 WebSocket의 추가 복잡성을 정당화할 수 있습니다.

### Why no Redis lock everywhere?

DB unique constraint나 atomic update로 해결할 수 있는 문제를 network distributed lock으로 바꾸면 failure mode가 늘어납니다. lock scope는 필요한 최소 범위로 유지합니다.

---

## 16. Interview Story

### 30-second version

> LLM 챗봇을 구현하면서 외부 API가 느린 I/O-bound workload라는 점에 주목했습니다. 처음에는 단순 async 호출로 시작했지만 동시 요청을 무제한 열면 provider를 과부하시킬 수 있어 Semaphore로 downstream concurrency를 제한했습니다. 긴 작업은 bounded Queue와 Worker로 분리하고 Request ID를 통해 Polling, SSE, WebSocket으로 상태를 전달했습니다. 이후 RAG에서 검색 근거가 없는데도 답하는 문제를 별도 품질 문제로 보고 BM25 retrieval과 score 기반 no-context guard를 추가했습니다. 현재는 Prometheus 지표와 load-test harness로 throughput, p95/p99, queue wait를 분리 측정하도록 구성했습니다.

### Questions this repository can defend

- Async가 latency를 줄이는 기술인가?
- Semaphore와 Queue는 어떤 차이가 있는가?
- Queue가 왜 성능 최적화가 아니라 overload protection인가?
- Connection Pool을 너무 크게 잡으면 어떤 문제가 생기는가?
- 429 retry 시 exponential backoff와 jitter가 왜 필요한가?
- Polling, SSE, WebSocket 중 무엇을 선택할 것인가?
- RAG score threshold를 왜 두는가?
- Idempotency와 distributed lock은 어떤 문제를 각각 푸는가?
- PostgreSQL, Redis, Kafka의 역할을 왜 분리했는가?
- 평균 latency보다 p95/p99를 보는 이유는 무엇인가?

세부 질문과 답변 구조는 [`docs/10_interview_questions.md`](docs/10_interview_questions.md)에 정리되어 있습니다.

---

## 17. Development Roadmap

다음 단계는 기술을 추가하는 것이 아니라 **현재 limitation을 하나씩 측정 가능한 문제로 바꾸는 것**입니다.

```text
1. Redis-backed JobStore / Idempotency
2. PostgreSQL persistence 실제 API 연결
3. simultaneous duplicate race 재현 및 atomic claim 비교
4. connection reuse 실측
5. Polling / SSE / WebSocket network overhead 실측
6. vector/hybrid retrieval + reranker 비교
7. RAG quality dataset 및 grounding evaluation
8. multi-instance deployment
```

---

## Engineering Principle

> **문제를 재현하고, metric을 먼저 정의하고, 가장 작은 해결책부터 적용한 뒤, 같은 workload에서 다시 측정한다.**

이 프로젝트의 목표는 LLM 기술 자체를 보여주는 것이 아니라 **AI 기능을 신뢰할 수 있는 서비스로 운영하기 위해 백엔드가 어떤 판단을 해야 하는지 설명할 수 있는 것**입니다.
