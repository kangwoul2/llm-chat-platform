# 12. Known Limitations

이 저장소는 포트폴리오 실험을 시작하기 위한 MVP다. 다음 사항은 의도적으로 다음 iteration으로 남겨두었다.

1. **In-memory Job Store**: process restart 시 유실된다. multi-instance에서는 Redis/PostgreSQL로 이동한다.
2. **In-memory Idempotency**: 단일 프로세스 범위이며 `get → process → put` 사이의 동일-key 동시 요청 coalescing은 아직 구현하지 않았다. 이 자체를 race-condition 개선 실험으로 사용한다.
3. **SSE/WebSocket status loop**: 현재 100ms internal polling으로 store를 관찰한다. Redis Pub/Sub 또는 per-job event로 개선 가능하다.
4. **Sync baseline**: FastAPI의 sync endpoint는 thread pool에서 실행된다. 실험 결과는 worker/thread configuration을 함께 기록해야 한다.
5. **PostgreSQL**: schema scaffold만 있으며 repository/API 연동은 다음 단계다.
6. **Redis/Kafka**: adapter만 있으며 기본 path에서 사용하지 않는다. 실제 문제를 재현한 뒤 활성화한다.
7. **Synthetic report**: `sample_*` 결과는 실제 측정값이 아니다.
