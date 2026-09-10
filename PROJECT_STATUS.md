# Project Status

## 현재 상태
초기 포트폴리오 scaffold. 기본 mock workload로 API/queue/streaming 실험 구조를 실행할 수 있다.

## 가장 먼저 할 실제 작업
1. 프로젝트 clone 후 smoke run
2. Locust로 baseline raw CSV 수집
3. 실제 머신 환경 기록
4. sync/async 3회 반복 실험
5. SAMPLE 그래프를 actual 그래프로 교체
6. PostgreSQL conversation API 구현
7. Redis multi-instance 실험

## 금지
- `docs/09_sample_report.md`의 synthetic 숫자를 실제 결과처럼 이력서에 사용하지 않는다.
- Kafka/Kubernetes를 구현하지 않고 기술 스택에 '사용'으로 표기하지 않는다.
