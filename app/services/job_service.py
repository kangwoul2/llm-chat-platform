import asyncio
import uuid
from time import perf_counter

from app.schemas import JobStatus
from app.services.concurrency import LLMConcurrencyLimiter
from app.services.llm_client import LLMClient
from app.storage.job_store import InMemoryJobStore, JobRecord


class JobService:
    def __init__(
        self,
        queue_maxsize: int,
        workers: int,
        store: InMemoryJobStore,
        llm: LLMClient,
        limiter: LLMConcurrencyLimiter,
    ):
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=queue_maxsize)
        self.workers = workers
        self.store = store
        self.llm = llm
        self.limiter = limiter
        self.tasks: list[asyncio.Task] = []

    async def start(self):
        self.tasks = [asyncio.create_task(self._worker(i)) for i in range(self.workers)]

    async def stop(self):
        for task in self.tasks:
            task.cancel()
        await asyncio.gather(*self.tasks, return_exceptions=True)

    async def submit(self, message: str) -> JobRecord:
        job = JobRecord(job_id=str(uuid.uuid4()), message=message)
        await self.store.create(job)
        try:
            self.queue.put_nowait(job.job_id)
        except asyncio.QueueFull:
            await self.store.delete(job.job_id)
            raise
        return job

    async def _worker(self, worker_id: int):
        while True:
            job_id = await self.queue.get()
            job = None
            try:
                job = await self.store.get(job_id)
                if job is None:
                    continue
                job.started_at_perf = perf_counter()
                job.status = JobStatus.PROCESSING
                async with self.limiter:
                    answer, _ = await self.llm.generate(job.message)
                job.answer = answer
                job.status = JobStatus.COMPLETED
            except Exception as exc:  # benchmark project: preserve failure for inspection
                if job is not None:
                    job.error = repr(exc)
                    job.status = JobStatus.FAILED
            finally:
                if job is not None:
                    job.finished_at_perf = perf_counter()
                self.queue.task_done()
