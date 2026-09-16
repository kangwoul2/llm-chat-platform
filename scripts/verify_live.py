"""Verify the running server. Makes three LLM requests; do not use as a load test."""
import argparse
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import uuid

import httpx
from websockets.asyncio.client import connect


async def verify(base_url):
    results = []
    run_id = uuid.uuid4().hex

    async def check(name, operation):
        started = time.perf_counter()
        try:
            detail = await operation()
            result = {"name": name, "status": "PASS", "detail": detail}
        except Exception as exc:
            # Avoid logging request headers, credentials, or raw provider errors.
            detail = type(exc).__name__
            if isinstance(exc, httpx.HTTPStatusError):
                detail += f" HTTP {exc.response.status_code}"
            result = {"name": name, "status": "FAIL", "detail": detail}
        result["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 1)
        results.append(result)
        print(json.dumps(result, ensure_ascii=True), flush=True)

    async with httpx.AsyncClient(base_url=base_url, timeout=210, trust_env=False) as client:
        async def post(path, payload):
            response = await client.post(path, json=payload)
            response.raise_for_status()
            return response.json()

        async def health():
            response = await client.get("/health", headers={"X-Request-ID": run_id})
            response.raise_for_status()
            assert response.json()["status"] == "ok"
            assert response.headers["x-request-id"] == run_id
            return "HTTP 200 and request tracing"

        async def chat():
            payload = {"message": "Reply with exactly: connection verified", "idempotency_key": run_id}
            first = await post("/api/v1/chat/async", payload)
            assert first["answer"] and not first["answer"].startswith("[mock]")
            second = await post("/api/v1/chat/async", payload)
            assert second["route"] == "idempotency-hit"
            assert first["answer"] == second["answer"]
            assert first["request_id"] == second["request_id"]
            return {"answer": first["answer"], "processing_ms": first["processing_ms"], "cache": "hit"}

        async def jobs():
            job = await post("/api/v1/jobs", {"message": "Reply with exactly: job verified"})
            job_id = job["job_id"]

            async def polling():
                while True:
                    response = await client.get(f"/api/v1/jobs/{job_id}")
                    response.raise_for_status()
                    value = response.json()
                    if value["status"] in ("COMPLETED", "FAILED"):
                        assert value["status"] == "COMPLETED"
                        return value
                    await asyncio.sleep(0.3)

            async def sse():
                last = None
                async with client.stream("GET", f"/api/v1/jobs/{job_id}/events") as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            last = json.loads(line[6:])
                assert last and last["status"] == "COMPLETED"
                return last

            async def websocket():
                ws_url = base_url.replace("http://", "ws://").replace("https://", "wss://")
                async with connect(f"{ws_url}/api/v1/jobs/ws/{job_id}") as ws:
                    while True:
                        value = json.loads(await ws.recv())
                        if value["status"] in ("COMPLETED", "FAILED"):
                            assert value["status"] == "COMPLETED"
                            return value

            tasks = [asyncio.create_task(operation()) for operation in (polling, sse, websocket)]
            try:
                values = await asyncio.wait_for(asyncio.gather(*tasks), timeout=210)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            assert all(value["answer"] == values[0]["answer"] for value in values)
            assert all(value["total_ms"] >= 0 for value in values)
            return {"transports": ["polling", "SSE", "WebSocket"], "answer": values[0]["answer"],
                    "queue_wait_ms": values[0]["queue_wait_ms"], "total_ms": values[0]["total_ms"]}

        async def rag():
            marker = "verification" + run_id
            await post("/api/v1/knowledge/documents", {
                "document_id": marker, "content": f"{marker} launchcode ORCHID42. The launchcode is ORCHID42.",
                "source": "live-verification",
            })
            value = await post("/api/v1/knowledge/query", {
                "question": f"{marker} launchcode? Answer only with the launchcode.",
            })
            assert value["grounded"] is True
            assert "live-verification" in value["sources"]
            assert "ORCHID42" in value["answer"]
            return {"answer": value["answer"], "sources": value["sources"], "top_score": value["top_score"]}

        async def guard():
            value = await post("/api/v1/knowledge/query", {"question": "unknown" + uuid.uuid4().hex})
            assert value["grounded"] is False and value["llm_ms"] is None
            return "Unsupported question blocked without LLM call"

        async def metrics():
            response = await client.get("/metrics")
            response.raise_for_status()
            assert "chat_platform_http_requests_total" in response.text
            assert "chat_platform_llm_in_flight 0.0" in response.text
            return "Prometheus metrics available; no calls in flight"

        for name, operation in (("health", health), ("chat_and_idempotency", chat),
                                ("job_polling_sse_websocket", jobs), ("rag_sources", rag),
                                ("rag_guard", guard), ("metrics", metrics)):
            await check(name, operation)
    return {"timestamp_utc": datetime.now(timezone.utc).isoformat(), "base_url": base_url, "results": results}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).resolve().parents[1] / "benchmarks/results/raw/live-verification.json")
    args = parser.parse_args()
    report = asyncio.run(verify(args.base_url.rstrip("/")))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    raise SystemExit(0 if all(result["status"] == "PASS" for result in report["results"]) else 1)
