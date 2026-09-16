"""Real HTTP/SSE/WebSocket checks against an isolated local mock server."""
import asyncio
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

import httpx
import pytest
from websockets.asyncio.client import connect


@pytest.fixture(scope="module")
def server_url(tmp_path_factory):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = os.environ.copy()
    env.update(LLM_PROVIDER="mock", MOCK_LLM_DELAY_MS="250",
               MAX_LLM_CONCURRENCY="2", JOB_WORKERS="1", JOB_QUEUE_MAXSIZE="2")
    url = f"http://127.0.0.1:{port}"
    log_path = tmp_path_factory.mktemp("server") / "uvicorn.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
             "--port", str(port), "--no-access-log"],
            cwd=Path(__file__).resolve().parents[1], env=env, stdout=log, stderr=log,
        )
        try:
            with httpx.Client(base_url=url, trust_env=False) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if process.poll() is not None:
                        pytest.fail(log_path.read_text(encoding="utf-8"))
                    try:
                        if client.get("/health").status_code == 200:
                            break
                    except httpx.TransportError:
                        pass
                    time.sleep(0.1)
                else:
                    pytest.fail("Local server startup timed out")
            yield url
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


@pytest.fixture
async def client(server_url):
    async with httpx.AsyncClient(base_url=server_url, timeout=10, trust_env=False) as client:
        yield client


async def submit(client):
    response = await client.post("/api/v1/jobs", json={"message": "runtime check"})
    assert response.status_code == 202, response.text
    return response.json()["job_id"]


async def completed(client, job_id):
    for _ in range(100):
        response = await client.get(f"/api/v1/jobs/{job_id}")
        assert response.status_code == 200
        job = response.json()
        if job["status"] in ("COMPLETED", "FAILED"):
            assert job["status"] == "COMPLETED", job
            assert job["answer"].startswith("[mock]")
            assert job["total_ms"] >= job["processing_ms"] >= 0
            assert job["queue_wait_ms"] >= 0
            return job
        await asyncio.sleep(0.05)
    pytest.fail("Job did not finish")


@pytest.mark.asyncio
async def test_health_dashboard_docs_and_trace(client):
    for path in ("/health", "/dashboard/", "/docs", "/openapi.json"):
        response = await client.get(path, headers={"X-Request-ID": "runtime-check"})
        assert response.status_code == 200
        assert response.headers["x-request-id"] == "runtime-check"


@pytest.mark.asyncio
async def test_chat_and_sequential_idempotency(client):
    payload = {"message": "hello", "idempotency_key": "runtime-idempotency"}
    first = await client.post("/api/v1/chat/async", json=payload)
    second = await client.post("/api/v1/chat/async", json=payload)
    assert first.status_code == second.status_code == 200
    assert first.json()["answer"] == "[mock] hello"
    assert second.json()["route"] == "idempotency-hit"
    assert first.json()["request_id"] == second.json()["request_id"]


@pytest.mark.asyncio
async def test_sync_baseline(client):
    response = await client.post("/api/v1/chat/sync-baseline", json={"message": "hello"})
    assert response.status_code == 200
    assert response.json()["answer"] == "[sync-mock] hello"


@pytest.mark.asyncio
async def test_input_validation_and_missing_job(client):
    for path, payload in (("/api/v1/chat/async", {"message": ""}),
                          ("/api/v1/jobs", {"message": "x" * 8001}),
                          ("/api/v1/knowledge/query", {"question": ""})):
        assert (await client.post(path, json=payload)).status_code == 422
    assert (await client.get("/api/v1/jobs/missing")).status_code == 404


@pytest.mark.asyncio
async def test_job_polling(client):
    await completed(client, await submit(client))


@pytest.mark.asyncio
async def test_job_sse(client):
    job_id = await submit(client)
    events = []
    async with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        async for line in response.aiter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert events[-1]["status"] == "COMPLETED"
    assert events[-1]["answer"].startswith("[mock]")


@pytest.mark.asyncio
async def test_job_websocket(client, server_url):
    job_id = await submit(client)
    async with connect(server_url.replace("http://", "ws://") + f"/api/v1/jobs/ws/{job_id}") as ws:
        while True:
            event = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
            if event["status"] in ("COMPLETED", "FAILED"):
                assert event["status"] == "COMPLETED"
                assert event["answer"].startswith("[mock]")
                break


@pytest.mark.asyncio
async def test_queue_backpressure_and_recovery(client):
    responses = await asyncio.gather(*(
        client.post("/api/v1/jobs", json={"message": f"burst {i}"}) for i in range(15)
    ))
    assert {r.status_code for r in responses} == {202, 429}
    for response in responses:
        if response.status_code == 202:
            await completed(client, response.json()["job_id"])
    await completed(client, await submit(client))


async def add_knowledge(client):
    response = await client.post("/api/v1/knowledge/documents", json={
        "document_id": "runtime-guide", "content": "runtimecheck bounded queue backpressure worker",
        "source": "runtime-guide.md",
    })
    assert response.status_code == 201
    return response.json()["knowledge_size"]


@pytest.mark.asyncio
async def test_rag_upsert_sources_and_guard(client):
    assert await add_knowledge(client) == await add_knowledge(client)
    response = await client.post("/api/v1/knowledge/query", json={"question": "runtimecheck bounded queue"})
    assert response.status_code == 200
    body = response.json()
    assert body["grounded"] is True
    assert "runtime-guide.md" in body["sources"]
    assert body["llm_ms"] is not None
    response = await client.post("/api/v1/knowledge/query", json={"question": "zxqvunknown"})
    assert response.status_code == 200
    assert response.json()["grounded"] is False
    assert response.json()["llm_ms"] is None


@pytest.mark.asyncio
async def test_shared_concurrency_limit_and_responsiveness(client):
    await add_knowledge(client)
    requests = [asyncio.create_task(client.post("/api/v1/chat/async", json={"message": "concurrency"}))
                for _ in range(4)]
    requests += [asyncio.create_task(client.post("/api/v1/knowledge/query", json={"question": "runtimecheck bounded queue"}))
                 for _ in range(4)]
    peak = 0
    try:
        while not all(task.done() for task in requests):
            response = await client.get("/metrics")
            assert response.status_code == 200
            line = next(line for line in response.text.splitlines()
                        if line.startswith("chat_platform_llm_in_flight "))
            peak = max(peak, float(line.split()[1]))
            await asyncio.sleep(0.02)
        responses = await asyncio.gather(*requests)
        assert all(response.status_code == 200 for response in responses)
    finally:
        await asyncio.gather(*requests, return_exceptions=True)
    assert 0 < peak <= 2, f"Configured limit=2, observed downstream calls={peak}"


@pytest.mark.asyncio
async def test_prometheus_metrics(client):
    text = (await client.get("/metrics")).text
    for metric in ("chat_platform_http_requests_total", "chat_platform_http_request_duration_seconds",
                   "chat_platform_llm_in_flight", "chat_platform_rag_answers_total"):
        assert metric in text
