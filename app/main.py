from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.chat import router as chat_router
from app.api.jobs import router as jobs_router
from app.api.knowledge import router as knowledge_router
from app.core.config import get_settings
from app.core.observability import RequestContextMiddleware, metrics_response
from app.rag.service import GroundedChatService
from app.rag.store import KnowledgeStore
from app.services.concurrency import LLMConcurrencyLimiter
from app.services.idempotency import InMemoryIdempotencyStore
from app.services.job_service import JobService
from app.services.llm_client import MockLLMClient, OpenAICompatibleLLMClient
from app.storage.job_store import InMemoryJobStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    limits = httpx.Limits(
        max_connections=settings.http_max_connections,
        max_keepalive_connections=settings.http_max_keepalive_connections,
    )
    timeout = httpx.Timeout(
        connect=settings.http_connect_timeout_sec,
        read=settings.http_read_timeout_sec,
        write=settings.http_read_timeout_sec,
        pool=settings.http_connect_timeout_sec,
    )
    http_client = httpx.AsyncClient(base_url=settings.llm_base_url, limits=limits, timeout=timeout)

    llm = (
        MockLLMClient(settings)
        if settings.llm_provider == "mock"
        else OpenAICompatibleLLMClient(settings, http_client)
    )
    limiter = LLMConcurrencyLimiter(settings.max_llm_concurrency)
    job_store = InMemoryJobStore()
    idempotency_store = InMemoryIdempotencyStore()
    job_service = JobService(
        queue_maxsize=settings.job_queue_maxsize,
        workers=settings.job_workers,
        store=job_store,
        llm=llm,
        limiter=limiter,
    )
    knowledge_store = KnowledgeStore.from_directory(settings.rag_knowledge_dir)
    grounded_chat = GroundedChatService(
        knowledge_store, llm, min_score=settings.rag_min_score, limiter=limiter,
    )

    app.state.settings = settings
    app.state.http_client = http_client
    app.state.llm = llm
    app.state.llm_limiter = limiter
    app.state.job_store = job_store
    app.state.idempotency_store = idempotency_store
    app.state.job_service = job_service
    app.state.knowledge_store = knowledge_store
    app.state.grounded_chat = grounded_chat

    await job_service.start()
    yield
    await job_service.stop()
    await http_client.aclose()


app = FastAPI(title="Chat Platform", version="0.2.0", lifespan=lifespan)
app.add_middleware(RequestContextMiddleware)
app.include_router(chat_router)
app.include_router(jobs_router)
app.include_router(knowledge_router)
app.mount("/dashboard", StaticFiles(directory="web", html=True), name="dashboard")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return metrics_response()
