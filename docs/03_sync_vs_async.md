# 03. Sync vs Async Experiment

## 가설
동일한 1.2초 I/O workload에서 동시 사용자가 증가하면 async 구현이 blocking baseline보다 더 높은 throughput과 낮은 tail latency를 보일 것이다.

## 비교 대상

### Sync baseline
```text
request
→ blocking wait
→ response
```

### Async
```text
request A → await downstream
request B → 진행 가능
request C → 진행 가능
```

## 측정 지표
- Throughput (RPS): 초당 완료 요청 수
- p50 latency: 중앙 사용자 응답 시간
- p95 latency: 95% 요청이 완료되는 상한
- p99 latency: tail latency
- Error rate
- CPU / Memory

## 해석 시 주의
실제 FastAPI `def` endpoint는 thread pool에서 실행될 수 있다. 따라서 이 실험은 'Python 전체의 sync vs async 절대 우열'을 증명하는 실험이 아니라 **우리 workload와 worker/config 조건에서의 차이**를 측정하는 실험이다.

실제 포트폴리오 수치는 동일 머신, 동일 provider, 동일 workload, 동일 warm-up 조건에서 재측정해야 한다.
