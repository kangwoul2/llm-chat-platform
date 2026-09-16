import httpx
import pytest

from app.core.config import Settings
from app.services.llm_client import OpenAICompatibleLLMClient
from app.services.retry import RetryPolicy


@pytest.mark.asyncio
@pytest.mark.parametrize("status,expected_attempts", [(400, 1), (401, 1), (403, 1), (429, 3), (500, 3), (503, 3)])
async def test_provider_http_retry_classification(status, expected_attempts):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        return httpx.Response(status, json={"error": "controlled failure"})

    async with httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        llm = OpenAICompatibleLLMClient(Settings(_env_file=None), client)
        llm.retry_policy = RetryPolicy(max_attempts=3, base_delay_sec=0)
        with pytest.raises(httpx.HTTPStatusError):
            await llm.generate("test")
    assert attempts == expected_attempts


@pytest.mark.asyncio
@pytest.mark.parametrize("error_type", [httpx.ReadTimeout, httpx.ConnectError])
async def test_provider_recovers_from_transport_error(error_type):
    attempts = 0

    def handler(request):
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise error_type("controlled failure", request=request)
        return httpx.Response(200, json={"choices": [{"message": {"content": "recovered"}}]})

    async with httpx.AsyncClient(base_url="https://example.test", transport=httpx.MockTransport(handler)) as client:
        llm = OpenAICompatibleLLMClient(Settings(_env_file=None), client)
        llm.retry_policy = RetryPolicy(max_attempts=3, base_delay_sec=0)
        answer, _ = await llm.generate("test")
    assert answer == "recovered"
    assert attempts == 3
