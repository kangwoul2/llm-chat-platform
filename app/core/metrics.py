from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any


@dataclass
class RequestMetrics:
    request_id: str
    route: str
    queue_wait_ms: float = 0.0
    processing_ms: float = 0.0
    total_ms: float = 0.0
    provider_ms: float = 0.0
    success: bool = True
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class Timer:
    def __enter__(self):
        self.started = perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.elapsed_ms = (perf_counter() - self.started) * 1000
