# proposals — 바로 돌려 볼 수 있는 제안 코드와 측정 하네스

기존 `app/` 코드는 수정하지 않았고, 실제 클래스(`BM25Retriever`, `KnowledgeStore`, `GroundedChatService`, `InMemoryIdempotencyStore`, `LLMConcurrencyLimiter`)를 import 해서 조합한다.
`.github/` 아래라서 기본 `pytest -q` 와 CI(`compileall app tests benchmarks`)는 이 폴더를 수집하지 않는다.

## 실행 (저장소 루트에서)

```bash
# 테스트 (24개)
PYTHONPATH=.:.github/handoff/proposals pytest -q .github/handoff/proposals/tests

# 검색 평가 → rag_eval/results.md
PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/run_eval.py

# 토크나이저 변형 비교 → rag_eval/tokenizer_results.md
PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/tokenizer_experiment.py
```

필요한 것: 이 저장소의 `requirements.txt` 중 `pytest`, `pytest-asyncio`, `prometheus-client`, `httpx`, `pydantic`, `pydantic-settings`, `fastapi`. 네트워크·LLM 호출은 없다.

## 파일

| 파일 | 하는 일 | 판정(`../03`) |
|---|---|---|
| `single_flight.py` | 같은 키의 동시 요청을 하나로 합침. 리더 취소·오류 전파 처리 | P1 ACCEPT |
| `rag_eval/harness.py` · `run_eval.py` · `questions.jsonl` | 검색 평가(hit@k, MRR, 컨텍스트 크기)와 근거 판정 기준값 스윕. 질문 24 + 6, 코퍼스는 `docs/*.md` | P2 ACCEPT |
| `ko_bm25.py` | 조사를 떼고 원형과 함께 색인하는 BM25 (`BM25Retriever` 와 같은 규격). 글자 2-gram 은 부정 결과로 보관 | P3 MODIFY · P6 REJECT |
| `doc_chunking.py` | 마크다운 조각화, 고정 청크 ID `{문서}#{순번}`, 재색인 시 옛 조각 삭제. `GroundedChatService` 에 그대로 끼움 | P4 ACCEPT |
| `citations.py` | 근거 번호 프롬프트, `[근거 N]` 해석, 실제 인용한 출처만 반환(`CitingChatService`) | P5 ACCEPT |
| `rag_eval/tokenizer_experiment.py` | 토크나이저 5종 비교 | – |
| `rag_eval/results.md` · `tokenizer_results.md` | 위 두 스크립트의 실행 결과(커밋 시점 저장본) | – |
| `tests/` | 위 모듈의 테스트 24개. 특히 `test_single_flight.py` 는 현재 흐름의 경쟁 상태를 먼저 재현한다 | – |

## 읽는 순서

1. `../01_rag_gap_analysis.md` — 무엇이 문제인가 (VERIFIED / INFERRED 구분)
2. `../02_measured_results.md` — 측정해 보니 어땠나 (가설이 틀린 것 포함)
3. `../03_proposals_and_acceptance.md` — 무엇을 어떤 순서로 적용할까
4. `../04_report_material.md` — 보고서를 쓸 때 쓸 수 있는 문장과 쓰면 안 되는 문장
