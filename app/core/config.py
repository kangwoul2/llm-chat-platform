from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Chat Platform"
    app_env: str = "local"
    host: str = "0.0.0.0"
    port: int = 8000

    llm_provider: str = "mock"
    mock_llm_delay_ms: int = 1200
    llm_base_url: str = "https://api.openai.com"
    llm_api_key: str = ""
    llm_model: str = "gpt-5-mini"
    llm_retry_attempts: int = 3

    max_llm_concurrency: int = 10
    http_max_connections: int = 50
    http_max_keepalive_connections: int = 20
    http_connect_timeout_sec: float = 5.0
    http_read_timeout_sec: float = 30.0

    rag_knowledge_dir: str = "data/knowledge"
    rag_min_score: float = 0.55

    job_workers: int = 4
    job_queue_maxsize: int = 100
    job_result_ttl_sec: int = 3600

    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/chat_platform"
    redis_url: str = "redis://localhost:6379/0"
    enable_postgres: bool = False
    enable_redis: bool = False
    enable_kafka: bool = False
    kafka_bootstrap_servers: str = "localhost:9092"
    kafka_topic_chat_events: str = "chat-events"


@lru_cache
def get_settings() -> Settings:
    return Settings()
