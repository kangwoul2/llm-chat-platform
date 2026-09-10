# 10. Interview Questions

## 왜 async를 선택했나요?
LLM 호출은 CPU-bound보다 원격 응답 대기가 큰 I/O-bound workload다. await 동안 event loop가 다른 요청을 진행하도록 해 동시 요청 처리 효율을 높이는 것이 목적이었다. 단일 모델 inference 시간을 단축하려는 목적은 아니다.

## async로 만들면 무조건 빨라지나요?
아니다. CPU-bound 작업에서는 효과가 작고 blocking library가 event loop 안에 남아 있으면 오히려 병목이 된다. workload 특성을 먼저 측정해야 한다.

## Semaphore와 Queue 차이는?
Semaphore는 동시에 실행 가능한 개수를 제한한다. Queue는 작업의 대기 순서와 상태 자체를 모델링한다. 짧은 요청은 semaphore, 장시간 job은 queue가 더 자연스럽다.

## 왜 WebSocket 대신 SSE인가요?
LLM token/status 전달은 Server → Client 방향이 대부분이라 양방향 WebSocket의 운영 복잡도를 항상 감수할 이유가 없다. 단, 사용자 cancel이나 실시간 양방향 이벤트 요구가 커지면 WebSocket이 유리하다.

## Connection Pool이 왜 필요한가요?
같은 downstream에 반복 요청할 때 TCP/TLS 연결 생성 비용을 매번 지불하지 않고 keep-alive connection을 재사용할 수 있다. 단, pool을 과도하게 키우면 downstream capacity를 초과한다.

## Redis Distributed Lock과 Kafka의 차이는?
Redis lock은 여러 인스턴스의 공유 자원 접근을 조정한다. Kafka는 이벤트를 저장·전달하여 producer와 consumer를 분리한다. Kafka를 쓴다고 race condition이 자동으로 해결되지는 않는다.

## 왜 처음부터 MSA를 쓰지 않았나요?
서비스 분리는 네트워크 실패와 운영 복잡성을 만든다. 먼저 modular monolith에서 병목을 측정하고 독립 확장/장애 격리 필요성이 확인되는 경계만 분리하는 것이 합리적이라고 판단했다.

## 성능 개선을 어떻게 증명했나요?
동일 workload와 환경에서 Before/After를 분리해 RPS, p95/p99, error rate, queue wait, notification delay를 측정하고 raw 결과를 저장한다. 평균만 보지 않고 tail latency와 오류율을 함께 본다.
