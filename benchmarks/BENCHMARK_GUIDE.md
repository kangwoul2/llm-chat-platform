# 성능 측정 안내

## 1. 서버 실행

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. Locust 실행

```bash
locust -f benchmarks/locustfile.py --host http://localhost:8000
```

## 3. 화면 없이 실행하는 예시

현재 동기/비동기 요청이 같은 비중으로 들어가므로 첫 실험 이후에는 경로별 Locust 파일을 분리하는 것을 권장합니다.

```bash
locust -f benchmarks/locustfile.py \
  --host http://localhost:8000 \
  --headless \
  -u 50 \
  -r 10 \
  -t 60s \
  --csv benchmarks/results/run_u50
```

## 4. 실험 규칙

- 서버 재시작 후 준비 요청 실행
- 같은 장비 사용
- 같은 Uvicorn 작업자 수
- 같은 모의 응답 지연시간 또는 같은 LLM 모델
- 한 번에 하나의 변수만 변경
- 각 조건 최소 3회 반복

## 5. 실제 결과 CSV 형식

`analyze_results.py`가 읽을 수 있도록 다음 형식을 사용합니다.

```csv
scenario,users,throughput_rps,p50_ms,p95_ms,error_rate_pct
sync-baseline,50,...,...,...,...
async,50,...,...,...,...
```

## 6. 결과 보고서에서 반드시 구분할 것

- 측정된 사실
- 결과 해석
- 실험 한계
- 다음 실험

성능 결과는 **기준 상태 → 한 가지 변경 → 같은 부하 → 측정 → 해석** 순서로 정리합니다.