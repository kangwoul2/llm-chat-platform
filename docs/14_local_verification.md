# 로컬 실행과 기능별 검증

프로젝트 루트(`llm-chat-platform`)에서 실행합니다. Python 3.11 이상이 필요합니다.

## 1. 환경 설정

Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
# .env가 없을 때만 복사합니다. 기존 키를 덮어쓰지 마세요.
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

OpenAI 사용 시 `.env`에 다음 값을 설정합니다.

```dotenv
HOST=127.0.0.1
PORT=8000
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.openai.com
LLM_API_KEY=여기에_본인의_API_키
LLM_MODEL=gpt-5-mini
LLM_RETRY_ATTEMPTS=3
HTTP_READ_TIMEOUT_SEC=60
```

기존 구현은 `/v1/chat/completions`를 호출합니다. `LLM_BASE_URL`에는 `/v1`을 붙이지 않습니다.
`gpt-5-mini`의 Chat Completions 지원은 [OpenAI 공식 문서](https://developers.openai.com/api/docs/models/gpt-5-mini)에서 확인할 수 있습니다.
`.env`는 Git 제외 대상입니다. 키를 출력하거나 테스트 결과 파일에 저장하지 않습니다.

## 2. 서버 실행

```powershell
.\.venv\Scripts\python.exe scripts/run_dev.py
```

이 실행기는 `.env`의 HOST와 PORT를 사용하며, 프로젝트 루트를 기준으로 지식 문서와 대시보드를 읽습니다.
`.env`를 바꾼 뒤에는 서버를 Ctrl+C로 종료하고 다시 실행해야 합니다.

키 없이 확인하려면 `.env`의 `LLM_PROVIDER=mock`을 사용하거나, 해당 터미널에서만 다음처럼 덮어씁니다.

```powershell
$env:LLM_PROVIDER = 'mock'
.\.venv\Scripts\python.exe scripts/run_dev.py
# 서버를 Ctrl+C로 종료한 후, .env 설정을 다시 사용하려면:
Remove-Item Env:LLM_PROVIDER
```

- 대시보드: http://127.0.0.1:8000/dashboard/
- API 실행 화면: http://127.0.0.1:8000/docs
- 상태 확인: http://127.0.0.1:8000/health
- 지표: http://127.0.0.1:8000/metrics

## 3. API 비용 없는 자동 검증

```powershell
.\.venv\Scripts\python.exe -m pytest -v
```

실제 키가 `.env`에 있어도 이 테스트는 외부 LLM을 호출하지 않습니다.
`test_runtime.py`가 별도 포트에 실제 Uvicorn 서버를 띄우고 mock LLM을 사용합니다.
테스트용 설정은 지연 250ms, 동시 LLM 호출 2개, 작업 처리자 1개, 대기열 2개입니다.
테스트 서버는 종료 시 정리됩니다. 사용자가 실행한 8000번 서버와 분리됩니다.

| 검증 대상 | 확인 방법 |
| --- | --- |
| 서버·대시보드·Swagger·요청 추적 | HTTP 200과 X-Request-ID 확인 |
| 비동기 채팅 | 응답 내용 확인, 동시 호출 중 지표 요청 처리 |
| 동기 비교 경로 | mock 응답 확인; 실제 OpenAI 모드에서는 사용 불가 |
| 순차 멱등성 | 같은 키의 두 번째 요청이 기존 결과 반환 |
| 입력 검증 | 빈 입력·길이 초과 422, 없는 작업 404 |
| 작업 폴링 | COMPLETED까지 확인, 대기·처리·전체 시간 확인 |
| SSE | 실제 HTTP 스트림에서 완료 이벤트 수신 |
| WebSocket | 실제 소켓에서 완료 메시지 수신 |
| 대기열 과부하 | 15건 요청에서 202와 429 발생, 이후 재접수 성공 |
| RAG 문서 등록·교체 | 동일 ID 갱신 시 문서 수 유지 |
| RAG 검색·출처·차단 | 근거 있는 응답의 출처 확인, 무관한 질문의 LLM 호출 차단 |
| 공용 동시 호출 제한 | 채팅·RAG 혼합 요청 중 LLM 동시 호출 수가 2 이하 |
| 재시도 | 429/500/503 최대 3회, 400/401/403 1회; 타임아웃·연결 오류 후 복구 |
| 실패 전파 | 채팅·RAG는 502, 비동기 작업은 FAILED |
| 지표 | Prometheus 요청·지연·동시 호출·RAG 지표 노출 |

## 4. 실제 OpenAI로 확인

서버가 실행 중인 상태에서 다른 터미널에서 실행합니다.

```powershell
.\.venv\Scripts\python.exe scripts/verify_live.py
```

기본 LLM 호출은 총 3건입니다: 일반 채팅, 비동기 작업, 근거 기반 질의.
일시적 오류가 발생하면 설정된 정책에 따라 재시도할 수 있습니다.
같은 작업을 폴링·SSE·WebSocket으로 동시에 관찰해 결과 일치를 확인합니다.
순차 멱등성, 근거 부족 차단, 지표도 함께 확인합니다.
검증용 문서 1개와 작업 결과는 실행 중인 서버 메모리에 남고 재시작하면 사라집니다.

실측 원본은 `benchmarks/results/raw/live-verification.json`에 저장합니다.
이 파일은 Git 제외 대상이며 다시 실행하면 덮어씁니다. 보관하려면 `--output`으로 다른 경로를 지정합니다.
한 항목이라도 실패하면 종료 코드는 1입니다. 이는 소규모 기능 검증이며 성능 벤치마크가 아닙니다.

## 5. 직접 하나씩 실행

1. 대시보드에서 `Async 즉시 호출`로 일반 채팅을 확인합니다.
2. Polling, SSE, WebSocket을 각각 선택하고 `Job 실행`으로 상태와 시간을 확인합니다.
3. `/docs`에서 `POST /api/v1/chat/async`에 같은 `idempotency_key`를 두 번 보내 두 번째 `route`가 `idempotency-hit`인지 확인합니다.
4. `POST /api/v1/knowledge/documents`에 아래 문서를 등록합니다.

   ```json
   {"document_id":"local-guide","content":"검증암호 ORCHID42. 검증암호 값은 ORCHID42입니다.","source":"local-guide"}
   ```

5. `POST /api/v1/knowledge/query`에 `{"question":"검증암호 ORCHID42"}`를 보내 `grounded`, `sources`, 답변을 확인합니다.
6. 등록 문서와 무관한 질문을 보내 `grounded=false`, `llm_ms=null`을 확인합니다.
7. 과부하·재시도 재현은 외부 API 대신 자동 mock 테스트로 확인합니다.

## 6. 검증 범위와 남은 한계

- SSE·WebSocket은 작업 상태와 완성된 답변을 전달합니다. LLM 토큰 스트리밍은 구현되어 있지 않습니다.
- `ENABLE_POSTGRES`, `ENABLE_REDIS`, `ENABLE_KAFKA`는 현재 API 초기화에 연결되지 않습니다. true로 바꾸어도 영구 저장·분산 락·이벤트 발행이 자동으로 활성화되지 않습니다.
- `JOB_RESULT_TTL_SEC`는 현재 저장소에서 적용되지 않습니다. 결과는 재시작 전까지 메모리에 남습니다.
- 동시 멱등성 요청의 원자성, 여러 서버 간 공유 상태, 대화 이력 저장은 보장하지 않습니다.
- HTTP 클라이언트 재사용은 코드에 구현되어 있습니다. TCP/TLS 연결 재사용 횟수와 연결 풀 튜닝 효과는 별도 계측이 필요합니다.
- p95/p99, 처리량 개선 및 실제 제공자 429/타임아웃은 이 소규모 검증으로 입증하지 않습니다.

인증 오류(401)가 발생하면 키를 확인하고 서버를 재시작합니다. `/health`가 200이어도 외부 LLM 인증 성공을 뜻하지 않습니다.
