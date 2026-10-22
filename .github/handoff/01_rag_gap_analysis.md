# 01. 현재 RAG 코드의 빈틈 분석

기준 커밋 `c56c358` (main). 아래 판정은 코드를 직접 읽거나, 이 폴더의 테스트·하네스로 재현한 것만 `VERIFIED` 로 적었다.
읽은 파일: `app/rag/{retrieval,store,service}.py`, `app/api/{chat,knowledge}.py`, `app/services/{concurrency,idempotency,llm_client}.py`, `tests/test_retrieval.py`, `data/knowledge/service_guide.md`, `docs/{11,12}_*.md`.

범례 — `VERIFIED` 코드를 읽었거나 재현했다 · `INFERRED` 코드에서 추론했지만 측정하지 않았다 · `UNKNOWN` 확인하지 못했다

## 이 프로젝트의 강점 (건드리지 않는다)

| 항목 | 근거 |
|---|---|
| 외부 LLM 동시 호출 수를 `LLMConcurrencyLimiter`(세마포어) 하나로 제한하고, 일반 채팅·작업 대기열·RAG 가 같은 한도를 공유 | `app/services/concurrency.py`, `app/main.py` 의 `limiter` 주입, `docs/` 의 “RAG 동시 호출 제한 버그” 수정 기록 — VERIFIED |
| 기준선(동기)과 비교하는 실험 설계, 샘플 수치를 실제 성과로 쓰지 않는다는 원칙 | `PROJECT_STATUS.md`, `docs/08`, `docs/12` — VERIFIED |

**이 폴더의 모든 제안은 세마포어 코드를 수정하지 않는다.** 제안 코드는 기존 `LLMConcurrencyLimiter` 를 그대로 import 해서 쓰고, 테스트로 한도가 유지됨을 확인한다.

## RAG 쪽 빈틈

| # | 현재 동작 | 문제 | 근거 | 판정 | 이 폴더의 대응 |
|---|---|---|---|---|---|
| R1 | 지식 문서는 `data/knowledge/service_guide.md` 하나(약 760바이트, 8줄) | 검색 품질을 비교할 수 없다. 어떤 질문도 같은 문서로 간다 | `data/knowledge/` | VERIFIED | 평가 코퍼스로 `docs/*.md`(16개 파일)를 대신 사용 |
| R2 | `KnowledgeStore.from_directory` 가 파일 하나 = 문서 하나 | 관련 문단이 한 줄이어도 파일 전체가 LLM 컨텍스트로 간다 | `app/rag/store.py` | VERIFIED — 상위 3개 평균 3,266자 vs 조각 680자 (`02`) | `proposals/doc_chunking.py` |
| R3 | `tokenize()` 가 `[0-9A-Za-z가-힣_]+` 로만 자른다 | “세마포어가” 와 “세마포어로” 가 만나지 못한다 (한국어 조사) | `app/rag/retrieval.py` | VERIFIED — 재현 테스트 있음 | `proposals/ko_bm25.py` (조사 떼기) |
| R4 | 근거 판정이 `top_score >= rag_min_score(0.55)` | 절대 BM25 점수라 코퍼스·토크나이저가 바뀌면 의미가 변한다. 측정해 보니 답 없는 질문 6개 중 2개를 통과시킨다 | `app/rag/service.py` | VERIFIED — 차단율 67% (`02`) | `proposals/rag_eval/` 기준값 스윕 |
| R5 | 답변의 `sources` 가 *검색된 문서 전부* | LLM 이 쓰지 않은 문서도 출처처럼 보인다 | `app/rag/service.py` 의 `sources=list(dict.fromkeys(hit.document.source for hit in hits))` | VERIFIED | `proposals/citations.py` |
| R6 | 프롬프트가 “컨텍스트만 근거로 답하세요”뿐이고 근거 번호가 없다 | 어떤 문장이 어떤 근거인지 알 수 없다. 컨텍스트 안의 지시문을 막는 문구도 없다 | `app/rag/service.py` 의 `prompt` | VERIFIED(번호 없음) · INFERRED(주입 위험) | `proposals/citations.py` 의 `build_prompt` |
| R7 | 지식 저장소가 메모리뿐 (`app.state.knowledge_store`) | 서버를 재시작하면 API 로 넣은 문서가 사라진다 | `app/main.py`, `docs/12_known_limitations.md` | VERIFIED | (범위 밖) PostgreSQL 영속화는 `03` 에서 HOLD |
| R8 | `KnowledgeStore.add` 가 문서를 넣을 때마다 BM25 를 처음부터 다시 만든다 | 문서가 많아지면 등록이 느려진다 | `app/rag/store.py` | INFERRED (측정 안 함) | – |
| R9 | RAG 테스트가 3개이고 모두 문서 1~2개짜리 | 검색 품질을 말할 숫자가 없다 | `tests/test_retrieval.py` | VERIFIED | `proposals/rag_eval/` (24 + 6 질문) |

## 동시성 쪽 빈틈 (알려진 한계 #2)

| # | 현재 동작 | 문제 | 근거 | 판정 | 이 폴더의 대응 |
|---|---|---|---|---|---|
| C1 | `/api/v1/chat/async` 가 `get → LLM → put` | 같은 `idempotency_key` 가 동시에 오면 둘 다 조회에서 “없음”을 보고 둘 다 LLM 을 호출한다. 결과는 `setdefault` 로 하나만 남지만 호출·비용은 두 번 나간다 | `app/api/chat.py`, `app/services/idempotency.py`, `docs/12` #2 | VERIFIED — 같은 키 20건 동시 → LLM 20번 호출 (`tests/test_single_flight.py`) | `proposals/single_flight.py` |

## 해결하지 않는 것 (범위 밖)

- 여러 서버 간 멱등성·락(Redis/DB 제약조건) — 프로세스 안 합치기와 별개의 문제다.
- 임베딩 기반 벡터 검색 — 평가에서 의미 검색이 필요하다는 증거가 아직 없다 (`03` 의 HOLD 근거).
