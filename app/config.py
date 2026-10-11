from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="BCG_",
        extra="ignore",
    )

    database_url: str = "sqlite:///./bcg.db"
    storage_root: Path = Path("./storage")

    default_template: str = "default"

    # Envelope-level guard: reject whole requests that exceed this.
    max_batch_size: int = 5000
    # Commit interval inside the worker (visible progress + bounded crash loss).
    batch_chunk_size: int = 50

    # In-process worker; disable in tests or when running a separate worker process.
    worker_enabled: bool = True
    worker_poll_interval: float = 1.0
    stale_job_timeout_seconds: int = 600

    # If set, write endpoints require this value in the X-API-Key header.
    api_key: str | None = None
    retry_after_seconds: int = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()