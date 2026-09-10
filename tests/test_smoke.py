import asyncio

import pytest

from app.core.config import Settings
from app.services.llm_client import MockLLMClient


@pytest.mark.asyncio
async def test_mock_llm_is_non_blocking():
    settings = Settings(mock_llm_delay_ms=50)
    client = MockLLMClient(settings)
    results = await asyncio.gather(*(client.generate(str(i)) for i in range(5)))
    assert len(results) == 5
    assert all(answer.startswith("[mock]") for answer, _ in results)
