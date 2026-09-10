from __future__ import annotations

import time
import uuid

from fastapi import Request, Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from starlette.middleware.base import BaseHTTPMiddleware

HTTP_REQUESTS = Counter(
    "chat_platform_http_requests_total",
    "HTTP requests by method, route and status",
    ["method", "route", "status"],
)
HTTP_LATENCY = Histogram(
    "chat_platform_http_request_duration_seconds",
    "End-to-end HTTP request latency",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)
LLM_IN_FLIGHT = Gauge("chat_platform_llm_in_flight", "Current downstream LLM calls")
RAG_GROUNDED = Counter(
    "chat_platform_rag_answers_total",
    "Grounded and no-context RAG outcomes",
    ["grounded"],
)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        elapsed = time.perf_counter() - started
        route = request.scope.get("route")
        route_path = getattr(route, "path", request.url.path)
        HTTP_REQUESTS.labels(request.method, route_path, response.status_code).inc()
        HTTP_LATENCY.labels(request.method, route_path).observe(elapsed)
        response.headers["X-Request-ID"] = request_id
        return response


def metrics_response() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
