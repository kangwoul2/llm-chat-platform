# 09. SAMPLE Performance Report

> **주의: 아래 수치는 실제 측정 결과가 아니라 보고서/그래프 형식을 검증하기 위한 synthetic example이다. 이 문서를 실제 포트폴리오 결과로 인용하지 않는다.**

## 1. 가설
외부 I/O를 1.2초로 고정한 mock workload에서 동시 사용자 수가 커질수록 async path가 blocking baseline 대비 높은 throughput과 낮은 p95 latency를 보일 것으로 예상했다.

## 2. SAMPLE 결과

| Users | Scenario | Throughput RPS | p95 ms | Error % |
|---:|---|---:|---:|---:|
| 10 | sync | 7.8 | 1510 | 0.0 |
| 10 | async | 8.0 | 1420 | 0.0 |
| 50 | sync | 21.5 | 4760 | 1.4 |
| 50 | async | 36.9 | 2180 | 0.2 |
| 100 | sync | 24.1 | 8410 | 5.8 |
| 100 | async | 58.4 | 3120 | 0.9 |

## 3. SAMPLE 해석 문장
낮은 동시성에서는 두 구현의 차이가 작았지만, 동시 사용자가 증가하면서 baseline의 tail latency가 빠르게 증가하는 형태가 나타났다. async example은 I/O wait 중 다른 coroutine이 진행될 수 있어 예시 데이터에서 더 높은 throughput을 보인다.

그러나 이 결과만으로 'async가 항상 N배 빠르다'고 결론내릴 수 없다. FastAPI worker 수, thread pool, downstream capacity, connection pool, semaphore 값에 따라 결과가 달라지기 때문이다.

## 4. 실제 실험 후 교체해야 할 내용
- SAMPLE 문구 삭제
- 실제 환경 사양
- 3회 이상 반복값
- raw Locust CSV
- p50/p95/p99
- CPU/memory
- 장애/429 로그
- 해석과 선택 이유

## 그래프

![Sample Throughput](assets/sample_throughput.png)

![Sample p95](assets/sample_p95.png)

![Sample Error Rate](assets/sample_error_rate.png)
