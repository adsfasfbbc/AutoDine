from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "autodine_core"
    database_url: str = Field(
        default="postgresql+psycopg://autodine:autodine@localhost:5432/autodine_core"
    )
    # Single-store operation: requests that omit store_id fall back to this
    # store, which matches the seeded catalog. The store_id fields stay in the
    # REST/ADP protocols as the multi-store reservation.
    default_store_id: str = "store-main"

    model_config = SettingsConfigDict(
        env_prefix="AUTODINE_CORE_",
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def build_settings(database_url: str | None = None) -> Settings:
    if database_url is None:
        return get_settings()

    return Settings(database_url=database_url)
