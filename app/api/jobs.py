import asyncio

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from sse_starlette.sse import EventSourceResponse

from app.schemas import ChatRequest, JobCreateResponse, JobResponse, JobStatus

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


def _to_response(job):
    return JobResponse(
        job_id=job.job_id,
        status=job.status,
        answer=job.answer,
        error=job.error,
        queue_wait_ms=job.queue_wait_ms,
        processing_ms=job.processing_ms,
        total_ms=job.total_ms,
    )


@router.post("", response_model=JobCreateResponse, status_code=202)
async def create_job(payload: ChatRequest, request: Request):
    try:
        job = await request.app.state.job_service.submit(payload.message)
    except asyncio.QueueFull as exc:
        raise HTTPException(status_code=429, detail="job queue is full") from exc
    return JobCreateResponse(job_id=job.job_id, status=job.status)


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, request: Request):
    job = await request.app.state.job_store.get(job_id)
    if not job:
        raise HTTPException(404, "job not found")
    return _to_response(job)


@router.get("/{job_id}/events")
async def sse_job(job_id: str, request: Request):
    async def event_stream():
        previous = None
        while True:
            if await request.is_disconnected():
                break
            job = await request.app.state.job_store.get(job_id)
            if not job:
                yield {"event": "error", "data": "job not found"}
                break
            if job.status != previous:
                yield {"event": "status", "data": _to_response(job).model_dump_json()}
                previous = job.status
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.1)

    return EventSourceResponse(event_stream())


@router.websocket("/ws/{job_id}")
async def ws_job(websocket: WebSocket, job_id: str):
    await websocket.accept()
    try:
        previous = None
        while True:
            job = await websocket.scope["app"].state.job_store.get(job_id)
            if not job:
                await websocket.send_json({"error": "job not found"})
                break
            if job.status != previous:
                await websocket.send_json(_to_response(job).model_dump())
                previous = job.status
            if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
                break
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        return
