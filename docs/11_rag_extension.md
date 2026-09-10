# 11. Optional RAG Extension

이 프로젝트의 중심은 백엔드 성능/신뢰성이며 RAG는 **복합 downstream workload**로 확장할 수 있다.

## 권장 구조
```text
Question
→ Domain Router
→ Embedding API
→ Vector Search
→ No-context Guard
→ LLM Generation
```

## 백엔드 실험과 연결
- Embedding + LLM 두 개의 외부 I/O가 async path에 미치는 영향
- vector search 시간을 별도 span으로 측정
- RAG 없는 chat vs RAG chat p95 비교
- ingestion을 synchronous API에서 job queue로 분리
- 동일 문서 재업로드에 document hash idempotency 적용

## 품질 평가
성능만 높이고 답변 품질이 떨어지면 성공한 최적화가 아니다. RAG 확장 시 latency/RPS와 별도로 faithfulness, context precision/recall 같은 품질 지표를 함께 기록한다.
