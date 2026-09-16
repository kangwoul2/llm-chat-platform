import time

from fastapi.testclient import TestClient

from app.core.config import Settings
from app import main


def test_downstream_failure_chat_rag_and_job(monkeypatch):
    monkeypatch.setattr(main, "get_settings", lambda: Settings(
        _env_file=None, llm_provider="mock", mock_llm_delay_ms=0,
        rag_min_score=0.01, job_workers=1,
    ))

    async def failing_generate(message):
        raise RuntimeError("controlled downstream failure")

    with TestClient(main.app) as client:
        monkeypatch.setattr(main.app.state.llm, "generate", failing_generate)
        assert client.post("/api/v1/chat/async", json={"message": "hello"}).status_code == 502
        assert client.post("/api/v1/knowledge/documents", json={
            "document_id": "failure-test", "content": "failuretoken knowledge", "source": "test",
        }).status_code == 201
        assert client.post("/api/v1/knowledge/query", json={"question": "failuretoken"}).status_code == 502
        response = client.post("/api/v1/jobs", json={"message": "hello"})
        assert response.status_code == 202
        for _ in range(100):
            job = client.get(f"/api/v1/jobs/{response.json()['job_id']}").json()
            if job["status"] == "FAILED":
                break
            time.sleep(0.01)
        assert job["status"] == "FAILED"
        assert "controlled downstream failure" in job["error"]
        assert job["total_ms"] is not None
