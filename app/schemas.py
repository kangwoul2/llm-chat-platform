from enum import StrEnum
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    conversation_id: str | None = None
    idempotency_key: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    route: str
    processing_ms: float


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class JobCreateResponse(BaseModel):
    job_id: str
    status: JobStatus


class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    answer: str | None = None
    error: str | None = None
    queue_wait_ms: float | None = None
    processing_ms: float | None = None
    total_ms: float | None = None
