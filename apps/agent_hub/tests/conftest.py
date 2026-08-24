from __future__ import annotations

import pytest

from agent_hub.config import Settings
from agent_hub.hub import AgentHub

from .helpers import FakeCore


@pytest.fixture
def settings() -> Settings:
    return Settings(
        core_base_url="http://core",
        default_store_id="store-main",
        default_location_id="bar",
        llm_driver="scripted",
    )


@pytest.fixture
def fake_core() -> FakeCore:
    return FakeCore()


@pytest.fixture
def hub(fake_core: FakeCore) -> AgentHub:
    return AgentHub(
        Settings(
            core_base_url="http://core",
            default_store_id="store-main",
            default_location_id="bar",
            llm_driver="scripted",
        ),
        client=fake_core.client(),
    )
