# Benchmark Guide

## 1. 서버 실행
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 2. Locust UI
```bash
locust -f benchmarks/locustfile.py --host http://localhost:8000
```

## 3. Headless 예시
Sync/Async task가 현재 동일 비중으로 들어가므로 첫 실험 후 endpoint별 locustfile을 분리하는 것을 권장한다.

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
- 서버 재시작 후 warm-up
- 동일 machine
- 동일 Uvicorn worker 수
- 동일 mock delay 또는 동일 LLM model
- 한 번에 하나의 독립변수만 변경
- 각 조건 최소 3회 반복

## 5. 실제 결과 CSV 형식
`analyze_results.py`가 바로 읽도록 정리:

```csv
scenario,users,throughput_rps,p50_ms,p95_ms,error_rate_pct
sync-baseline,50,...,...,...,...
async,50,...,...,...,...
```

## 6. 결과 보고서에서 반드시 구분
- 관찰된 사실
- 해석
- 한계
- 다음 실험
