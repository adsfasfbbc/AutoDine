from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Agent Hub configuration, overridable via AGENT_HUB_* environment variables."""

    # Middle platform (AutoDineCore) REST endpoint.
    core_base_url: str = "http://localhost:8000"
    # Single-store operation defaults, matching the seeded catalog.
    default_store_id: str = "store-main"
    default_location_id: str = "bar"

    # LLM driver: "scripted" (deterministic, no key required) or "openai"
    # (any OpenAI-compatible endpoint: Qwen / DeepSeek / GLM / ...).
    llm_driver: str = "scripted"
    llm_base_url: str = ""
    llm_api_key: str = ""
    llm_model: str = "qwen-plus"

    max_tool_iterations: int = 8
    request_timeout_seconds: float = 15.0

    model_config = SettingsConfigDict(env_prefix="AGENT_HUB_", extra="ignore")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def build_settings(**overrides) -> Settings:
    if not overrides:
        return get_settings()
    return Settings(**overrides)
