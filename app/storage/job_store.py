import asyncio
from dataclasses import dataclass, field
from time import perf_counter

from app.schemas import JobStatus


@dataclass
class JobRecord:
    job_id: str
    message: str
    status: JobStatus = JobStatus.QUEUED
    answer: str | None = None
    error: str | None = None
    created_at_perf: float = field(default_factory=perf_counter)
    started_at_perf: float | None = None
    finished_at_perf: float | None = None

    @property
    def queue_wait_ms(self) -> float | None:
        if self.started_at_perf is None:
            return None
        return (self.started_at_perf - self.created_at_perf) * 1000

    @property
    def processing_ms(self) -> float | None:
        if self.started_at_perf is None or self.finished_at_perf is None:
            return None
        return (self.finished_at_perf - self.started_at_perf) * 1000

    @property
    def total_ms(self) -> float | None:
        if self.finished_at_perf is None:
            return None
        return (self.finished_at_perf - self.created_at_perf) * 1000


class InMemoryJobStore:
    def __init__(self):
        self._jobs: dict[str, JobRecord] = {}
        self._lock = asyncio.Lock()

    async def create(self, job: JobRecord) -> None:
        async with self._lock:
            self._jobs[job.job_id] = job

    async def get(self, job_id: str) -> JobRecord | None:
        async with self._lock:
            return self._jobs.get(job_id)

    async def delete(self, job_id: str) -> None:
        async with self._lock:
            self._jobs.pop(job_id, None)
