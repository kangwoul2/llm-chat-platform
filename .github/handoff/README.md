# handoff — AI/사람이 이어서 작업하고 보고서를 쓰기 위한 기록

> 이 폴더는 **포트폴리오 문서가 아니다.** 루트 `README.md`·`docs/` 어디에서도 링크하지 않는다.
> 개선 아이디어를 실제로 돌려 본 기록과, 바로 적용할 수 있는 제안 코드를 모아 둔 작업 공간이다.
> GPT/Claude 같은 도구가 이 폴더만 읽고도 “무엇을 했고, 무엇이 확인되었고, 다음에 무엇을 하면 되는지” 알 수 있게 썼다.

- 작성일: 2026-10-21 · 기준 커밋: `c56c358` (main) · 작성: Claude(Sonnet 5.5)가 소유자의 요청으로 작성
- 소유자 지침: **세마포어(`LLMConcurrencyLimiter`) 코드와 `app/` 은 수정하지 않는다.** 이 폴더는 파일을 *추가*할 뿐이다.

## 어디서부터 읽나

| 순서 | 파일 | 한 줄 |
|---|---|---|
| 1 | `01_rag_gap_analysis.md` | 현재 RAG·멱등성 코드의 빈틈 10가지 (코드 근거, VERIFIED / INFERRED) |
| 2 | `02_measured_results.md` | 제안을 실제로 돌려 본 결과 — 가설이 틀린 것 포함. 다른 저장소(교육 과정 RAG 프로젝트)에서 얻은 교훈 |
| 3 | `03_proposals_and_acceptance.md` | 제안 10개의 ACCEPT / MODIFY / HOLD / REJECT 와 적용 순서, 완료 기준 |
| 4 | `04_report_material.md` | 보고서·면접에 쓸 수 있는 문장과 쓰면 안 되는 문장, 한계 |
| – | `proposals/` | 제안 코드(`single_flight.py` · `doc_chunking.py` · `ko_bm25.py` · `citations.py`), 평가 하네스 `rag_eval/`, 테스트 24개 |
| – | `handoff.json` | 위 내용의 기계가 읽는 요약 |

## 한 문단 요약

이 서비스의 강점은 동시성 제어(세마포어, 대기열, 재시도)이고 RAG 는 아직 소형 BM25 구현이다(지식 문서 1개, 평가 없음). 별도의 RAG 프로젝트를 만들며 얻은 방법을 이 저장소의 코드에 맞춰 옮겨 **24 + 6개 질문의 검색 평가 하네스**를 만들고 네 가지 제안을 돌려 보았다. 결과: ① 같은 멱등성 키 동시 20건이 LLM 을 20번 호출하는 경쟁 상태를 재현했고 single-flight 로 1번이 되었다 ② 문서 조각화는 LLM 컨텍스트를 79% 줄였다 ③ 한국어 조사를 떼는 토크나이저는 hit@1 을 75% → 88% 로 올렸다 ④ 처음 제안한 글자 2-gram 은 75% → 62% 로 **나빠져서 버렸다** ⑤ 현재 근거 판정 기준값(0.55)은 답 없는 질문의 67% 만 막는다. 모두 이 저장소 `main` 에는 **아직 적용하지 않았다.**

## 규칙 (이어서 작업하는 쪽이 지킬 것)

1. 세마포어·`app/main.py` 의 limiter 주입을 바꾸지 않는다. 바꿔야 한다면 소유자에게 먼저 묻는다.
2. 측정한 수치만 쓴다. `docs/09_sample_report.md` 의 샘플 수치와 섞지 않는다.
3. 이 폴더의 제안을 main 에 적용하기 전에는 README·포트폴리오에서 “적용된 기능”으로 쓰지 않는다.
4. 판정 표시를 지킨다 — `VERIFIED`(코드를 읽었거나 재현했다) · `INFERRED`(추론) · `UNKNOWN`(확인 못 함).
5. 비밀 키, 교육 과정 자료(명세서 등), 외부 데이터 원본을 이 폴더에 올리지 않는다.
6. 변경은 한 번에 하나, 브랜치 하나에 제안 하나, 적용 전후를 같은 평가 세트로 다시 잰다.

## 실행

```bash
PYTHONPATH=.:.github/handoff/proposals pytest -q .github/handoff/proposals/tests          # 24개
PYTHONPATH=.:.github/handoff/proposals python .github/handoff/proposals/rag_eval/run_eval.py
```
자세한 사용법은 `proposals/README.md`.

## 이 폴더가 CI 에 영향을 주는가

없다. `.github/` 아래는 pytest 기본 설정이 수집하지 않고(`norecursedirs` 의 `.*`), CI 의 `compileall` 대상(`app tests benchmarks`)에도 없다. 로컬에서 `pytest -q` 가 수집하는 테스트 수는 이 폴더를 추가하기 전과 같다(26개).
