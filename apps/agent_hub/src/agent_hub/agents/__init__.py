from __future__ import annotations

from ..config import Settings
from ..core_client import CoreClient
from ..errors import UnknownAgentError
from ..llm.base import LLMAdapter
from .base import Agent
from .consumer import build_consumer_agent
from .kitchen import build_kitchen_agent
from .manager import build_manager_agent

_BUILDERS = {
    "consumer": build_consumer_agent,
    "kitchen": build_kitchen_agent,
    "manager": build_manager_agent,
}

AGENT_NAMES = tuple(_BUILDERS)


def build_agent(name: str, adapter: LLMAdapter, client: CoreClient, settings: Settings) -> Agent:
    builder = _BUILDERS.get(name)
    if builder is None:
        raise UnknownAgentError(name)
    return builder(adapter, client, settings)
