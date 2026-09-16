"""Run from any working directory: python scripts/run_dev.py."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

if __name__ == "__main__":
    import uvicorn
    from app.core.config import get_settings

    settings = get_settings()
    if settings.llm_provider not in {"mock", "openai_compatible"}:
        raise SystemExit("LLM_PROVIDER must be mock or openai_compatible")
    if settings.llm_provider == "openai_compatible" and not settings.llm_api_key.strip():
        raise SystemExit("Set LLM_API_KEY in .env before starting the OpenAI provider")
    print(f"Provider: {settings.llm_provider}; model: {settings.llm_model}", flush=True)
    uvicorn.run("app.main:app", host=settings.host, port=settings.port)
