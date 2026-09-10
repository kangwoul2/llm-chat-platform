# 13. Actual Performance Report Template

> 이 문서는 실제 benchmark 완료 후 채우는 최종 보고서 템플릿이다.

## 1. 실험 목적
- 문제:
- 가설:
- 변경사항:
- 독립변수:
- 통제변수:

## 2. 환경
| 항목 | 값 |
|---|---|
| Date | |
| CPU | |
| RAM | |
| OS | |
| Python | |
| Uvicorn workers | |
| LLM provider | |
| Model / mock delay | |
| Test duration | |

## 3. 결과
| Users | Scenario | RPS | p50 | p95 | p99 | Error % |
|---:|---|---:|---:|---:|---:|---:|
| | Before | | | | | |
| | After | | | | | |

## 4. 개선율
예:
```text
Throughput improvement (%)
= (After RPS - Before RPS) / Before RPS × 100

p95 reduction (%)
= (Before p95 - After p95) / Before p95 × 100
```

## 5. 관찰
측정된 사실만 작성한다.

## 6. 해석
왜 이런 결과가 나왔는지 시스템 구조와 연결한다.

## 7. Trade-off
성능을 얻기 위해 증가한 복잡도/자원/실패 가능성을 적는다.

## 8. 한계
- local benchmark인가?
- downstream이 mock인가 실제 LLM인가?
- network variability는?
- 반복 횟수는 충분한가?

## 9. 다음 실험
이번 결과로 새롭게 생긴 질문을 정의한다.
