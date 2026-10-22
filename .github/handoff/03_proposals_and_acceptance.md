# 03. 제안 판정과 적용 순서

각 제안은 **측정 결과(`02`)에 따라** ACCEPT / MODIFY / HOLD / REJECT 로 나누었다.
적용은 한 번에 하나씩, 브랜치 하나에 한 제안만 담아 변경 전후를 같은 평가 세트로 다시 잰다. (`docs/08_experiment_plan.md` 의 “한 번에 하나의 변수만 변경” 원칙)

> **세마포어(`LLMConcurrencyLimiter`)와 `app/main.py` 의 limiter 주입은 어떤 제안에서도 수정하지 않는다.**

## 판정 표

| # | 제안 | 판정 | 이유 (근거) | 파일 |
|---|---|---|---|---|
| P1 | 같은 `idempotency_key` 의 동시 요청을 하나로 합치기 (single-flight) | **ACCEPT** | 현재 흐름이 같은 키 20건에 LLM 을 20번 호출함을 재현했고, 합치면 1번이 된다. 알려진 한계 #2 를 직접 해결한다. 세마포어 바깥에 두어 한도의 의미가 바뀌지 않음을 테스트가 확인 | `proposals/single_flight.py`, `tests/test_single_flight.py` |
| P2 | 검색 평가 하네스와 근거 판정 기준값 재설정 | **ACCEPT** | 평가 없이는 아래 모든 제안을 판단할 수 없다. 현재 기준값 0.55 는 답 없는 질문의 67% 만 막는다 | `proposals/rag_eval/` |
| P3 | 한국어 조사 떼기 토크나이저 | **MODIFY** | 24문항 평가에서 hit@1 75% → 88%, MRR 0.830 → 0.906. 다만 질문과 조사 목록을 한 사람이 정했으므로 **실제 사용자 질문으로 다시 확인한 뒤** 적용 | `proposals/ko_bm25.py` |
| P4 | 문서 조각화 + 고정 청크 ID + 재색인 멱등 | **ACCEPT** | LLM 컨텍스트가 3,266자 → 680자(−79%)로 줄고 hit@3 이 88% → 92%. hit@1 은 떨어질 수 있어(75% → 67%) **P3 와 함께** 적용했을 때 83% | `proposals/doc_chunking.py` |
| P5 | 실제 인용한 근거만 `sources` 로 반환 + 근거 번호 프롬프트 | **ACCEPT** | R5 결함(검색된 전부를 출처로 표시)을 직접 해결. 스텁 LLM 으로 테스트 가능 | `proposals/citations.py` |
| P6 | 글자 2-gram 토크나이저 | **REJECT** | 측정 결과 hit@1 75% → 62%. 코드는 부정 결과로 남김 | `ko_bm25.tokenize_ngram`, `rag_eval/tokenizer_results.md` |
| P7 | 임베딩 기반 벡터 검색(Chroma 등) 또는 BM25 혼합 | **HOLD** | 틀린 질문 대부분은 표현 차이가 아니라 *비슷한 내용의 다른 문서*(`10_interview_questions.md`) 때문이다. P3·P4 적용 뒤에도 표현이 바뀐 질문을 놓치는 것이 확인될 때 도입 | – |
| P8 | MMR | **HOLD** | 문서 수가 적은 지금은 차이를 측정할 수 없다 | – |
| P9 | LangGraph | **REJECT** | 이 서비스의 RAG 는 “검색 한 번 → 생성 한 번”이라 그래프가 해결할 문제가 없다. 기술 이름만 늘어난다 | – |
| P10 | 지식 저장소 영속화 (PostgreSQL) | **HOLD** | 알려진 한계 #1·#5 와 같은 묶음. 영속화는 `docs/12` 의 PostgreSQL 연결 작업과 함께 | – |

## 적용 순서 (권장)

각 단계의 “완료 기준”을 모두 만족해야 다음으로 넘어간다.

1. **P2 하네스를 저장소 정식 위치로 옮긴다.** (`benchmarks/` 또는 `tests/`)
   - 완료: `python rag_eval/run_eval.py` 가 현재 main 의 수치(구성 A)를 재현한다. 결과를 `docs/` 에 “측정 결과”로 기록하고 **샘플 수치와 섞지 않는다**.
2. **P1 single-flight 를 `app/api/chat.py` 에 연결한다.**
   - 변경 범위: `chat.py` 한 파일 + `app/services/single_flight.py` 추가. `LLMConcurrencyLimiter`·`main.py` 는 그대로.
   - 완료: `tests/test_single_flight.py` 통과, 기존 테스트 전부 통과, `docs/12` #2 를 “프로세스 안에서는 해결, 서버 간은 여전히 한계”로 고쳐 쓴다.
3. **P5 인용만 sources 로.** `GroundedChatService` 를 상속한 `CitingChatService` 를 `/api/v1/knowledge/query` 에 연결한다.
   - 완료: 스텁 LLM 테스트 통과, 응답에 `sources`(인용된 것)와 `retrieved_sources`(검색된 것)가 따로 나온다.
4. **P4 조각화 → P3 토크나이저 순서로 하나씩.** 각각 적용 후 P2 를 다시 돌려 표를 갱신한다.
   - 완료: 구성 B/D 수치가 `rag_eval/results.md` 와 같은 방향(컨텍스트 감소, hit@3 유지 이상).
5. **기준값(`rag_min_score`)을 P3·P4 적용 뒤의 구성으로 다시 정한다.** 먼저 바꾸면 근거 없는 숫자만 바뀐다.
   - 완료: 새 기준값과 그 값에서의 통과/차단률을 문서에 적는다.

## 연결 스케치 (코드는 아직 적용하지 않음)

`app/api/chat.py` 의 흐름에 P1 을 넣는다면:

```python
# app/main.py lifespan 에 한 줄 추가 — limiter 줄은 건드리지 않는다
app.state.chat_flight = SingleFlight()

# app/api/chat.py async_chat 안에서
async def work():
    cached = await state.idempotency_store.get(payload.idempotency_key)
    if cached:
        return cached.answer, cached.request_id, "idempotency-hit"
    async with state.llm_limiter:                       # 기존과 동일
        answer, _ = await state.llm.generate(payload.message)
    await state.idempotency_store.put(payload.idempotency_key, CachedResult(answer=answer, request_id=request_id))
    return answer, request_id, "async"

if payload.idempotency_key:
    (answer, rid, route), led = await state.chat_flight.do(payload.idempotency_key, work)
    route = route if led else "single-flight-join"
```

P3·P4 를 `app/main.py` 에 연결한다면 `KnowledgeStore.from_directory(...)` 자리에 `ChunkedKnowledge(retriever_factory=KoBM25Retriever)` 를 만들고 `upsert_many` 로 채운다. `GroundedChatService(store=...)` 는 `store.search(question, limit=4)` 규격만 요구하므로 그대로 받는다. (`test_chunked_store_is_a_drop_in_for_grounded_chat_service` 가 확인)

## 하지 말 것

- 샘플 수치(`docs/09_sample_report.md`)를 실제 성과처럼 쓰지 않는다.
- 이 폴더의 결과를 “이 저장소에 이미 적용된 기능”으로 README·포트폴리오에 쓰지 않는다. 적용·재측정한 뒤에만 쓴다.
- 평가 질문 24개로 만든 숫자를 일반화하지 않는다. 방향만 본다.
- 비밀 키, 교육 과정 자료(명세서 등), 외부 데이터 원본을 이 폴더에 올리지 않는다.
