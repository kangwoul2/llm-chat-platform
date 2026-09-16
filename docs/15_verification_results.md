# 실행 검증 기록 — 2026-09-16

## 환경

- Windows, Python 3.11.9, 프로젝트 전용 `.venv`
- `requirements.txt` 설치 완료, `pip check` 통과
- `.env`: OpenAI 호환 제공자, `gpt-5-mini`, 로컬 127.0.0.1:8000
- `.env`의 Git 제외 여부 확인 완료

## 자동 검증

`python -m pytest -q`: **26 passed**, 의존성의 deprecation warning 2건.
`python -m compileall -q app tests scripts benchmarks`: 통과.

- 기존 검색·근거 차단·재시도·mock 호출 테스트: 6개
- 실제 로컬 서버의 HTTP·SSE·WebSocket·과부하·동시 호출·지표 테스트: 11개
- 제어된 HTTP 응답/전송 오류를 이용한 제공자 재시도 테스트: 8개
- 일반 채팅·RAG·작업 처리의 외부 LLM 실패 전파 테스트: 1개

자동 테스트는 외부 OpenAI를 호출하지 않는다. 전송 오류 테스트는 실제 제공자 장애가 아니라 제어된 오류를 주입한다.

## 재현하고 수정한 문제

RAG가 일반 채팅·작업 처리와 공유하는 세마포어를 우회했다.
동시 호출 제한 2, mock 지연 250ms에서 채팅 4건과 RAG 4건을 함께 보내면 동시 LLM 호출이 **6개**까지 관측되었다.
RAG 서비스에 공용 세마포어를 전달해 실제 LLM 생성 구간에 적용했다.
같은 검증에서 동시 호출 수가 **2 이하**임을 확인했다.

RAG의 외부 LLM 예외도 HTTP 502로 변환하도록 수정했고, 실패 전파 테스트로 확인했다.

## 실제 OpenAI 검증

**인증 오류로 미완료, 사용자 요청으로 보류.** 키 수정 후 서버 재시작과 재시도까지 진행했으나,
OpenAI의 `/v1/models` 진단 요청에서도 **HTTP 401 / invalid_api_key**가 확인되었다.
키의 실제 값은 로그나 보고서에 기록하지 않았다.
`.env`와 유효 설정의 키 일치, 프로세스 환경변수 덮어쓰기 없음, 앞뒤 공백 없음은 확인했다.

| 항목 | 결과 |
| --- | --- |
| 서버 상태와 요청 추적 | 통과 |
| OpenAI 일반 채팅·멱등성 | 인증 오류로 미검증 |
| OpenAI 작업의 폴링·SSE·WebSocket 답변 전달 | 인증 오류로 미검증 |
| OpenAI RAG 답변과 출처 | 인증 오류로 미검증 |
| 근거 없는 질문의 생성 차단 | 통과 |
| Prometheus 지표와 진행 중 호출 정리 | 통과 |

원본: `benchmarks/results/raw/live-verification.json` (로컬 전용, Git 제외).
유효한 키를 저장하고 서버를 재시작한 뒤 `python scripts/verify_live.py`로 다시 확인한다.

보류 후 `.env`의 OpenAI 설정은 보존하고, 개발 서버 프로세스만 `LLM_PROVIDER=mock`으로 전환했다.
이 서버의 대시보드에서는 외부 API 호출 없이 기능을 확인할 수 있다.

## 이번 결과로 입증하지 않은 사항

PostgreSQL·Redis·Kafka의 실제 API 연동, 결과 TTL 만료, 동시 멱등성 원자성,
토큰 단위 스트리밍, TCP/TLS 연결 재사용 계측, 실제 제공자 장애 재현 및 p95/p99 성능 개선.
상세 실행법과 구현 범위는 [로컬 실행과 검증 안내](14_local_verification.md)를 참고한다.
