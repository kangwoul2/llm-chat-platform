# 08. Experiment Plan

## 원칙
성능 숫자는 실제 측정 전에는 포트폴리오 결과로 사용하지 않는다. 저장소의 `sample_*` 데이터는 시각화와 보고서 형식 검증용 synthetic data다.

## 환경 기록 템플릿
- Date:
- OS:
- CPU:
- RAM:
- Python:
- Uvicorn workers:
- LLM provider:
- mock delay / actual model:
- network:
- warm-up requests:
- test duration:

## E1. Sync vs Async
Users: 1, 10, 50, 100, 200

수집:
- RPS
- p50/p95/p99
- error rate

## E2. Semaphore tuning
Concurrency: 1, 5, 10, 20, 50

수집:
- throughput
- p95
- downstream error
- queue/wait time

## E3. Connection Pool
- new client per request
- shared pool 10/20/50

## E4. Job Queue
- workers 1/2/4/8
- queue max 20/100/500

## E5. Delivery
동일한 5초 job에 대해:
- polling 100ms/500ms/1000ms
- SSE
- WebSocket

수집:
- request count
- bytes
- notification delay

## 재현 가능성
각 실험 최소 3회 반복하고 median과 spread를 기록한다. 서로 다른 개선을 동시에 적용하지 않고 한 변수씩 바꾼다.
