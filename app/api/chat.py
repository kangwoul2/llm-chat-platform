import time
import uuid

from fastapi import APIRouter, HTTPException, Request

from app.schemas import ChatRequest, ChatResponse
from app.services.idempotency import CachedResult

router = APIRouter(prefix="/api/v1/chat", tags=["chat"])


@router.post("/async", response_model=ChatResponse)
async def async_chat(payload: ChatRequest, request: Request):
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    state = request.app.state

    if payload.idempotency_key:
        cached = await state.idempotency_store.get(payload.idempotency_key)
        if cached:
            return ChatResponse(
                request_id=cached.request_id,
                answer=cached.answer,
                route="idempotency-hit",
                processing_ms=(time.perf_counter() - started) * 1000,
            )

    try:
        async with state.llm_limiter:
            answer, _ = await state.llm.generate(payload.message)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"downstream llm error: {exc!r}") from exc

    elapsed = (time.perf_counter() - started) * 1000
    if payload.idempotency_key:
        await state.idempotency_store.put(
            payload.idempotency_key,
            CachedResult(answer=answer, request_id=request_id),
        )
    return ChatResponse(request_id=request_id, answer=answer, route="async", processing_ms=elapsed)


@router.post("/sync-baseline", response_model=ChatResponse)
def sync_baseline(payload: ChatRequest, request: Request):
    """Controlled baseline endpoint.

    With mock provider it intentionally blocks the worker thread using time.sleep.
    The production-style path is /async.
    """
    settings = request.app.state.settings
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    if settings.llm_provider != "mock":
        raise HTTPException(400, "sync baseline is enabled only with mock provider")
    time.sleep(settings.mock_llm_delay_ms / 1000)
    elapsed = (time.perf_counter() - started) * 1000
    return ChatResponse(
        request_id=request_id,
        answer=f"[sync-mock] {payload.message}",
        route="sync-baseline",
        processing_ms=elapsed,
    )
