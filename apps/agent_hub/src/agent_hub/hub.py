from __future__ import annotations

from typing import Any, Dict, List, Optional

from .agents import build_agent
from .agents.base import Agent
from .config import Settings, get_settings
from .core_client import CoreClient
from .errors import UnknownAgentError
from .llm.base import LLMAdapter
from .llm.openai_adapter import OpenAICompatAdapter
from .llm.scripted_adapter import ScriptedAdapter


def _build_adapter(settings: Settings) -> LLMAdapter:
    if settings.llm_driver == "openai":
        if not settings.llm_base_url or not settings.llm_api_key or not settings.llm_model:
            raise ValueError(
                "llm_driver=openai 需要配置 AGENT_HUB_LLM_BASE_URL / AGENT_HUB_LLM_API_KEY / AGENT_HUB_LLM_MODEL"
            )
        return OpenAICompatAdapter(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    return ScriptedAdapter(
        default_store_id=settings.default_store_id,
        default_location_id=settings.default_location_id,
    )


class AgentHub:
    """Wires the Core client, the LLM adapter, and the three agents together."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        *,
        client: Optional[CoreClient] = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.client = client or CoreClient(
            self.settings.core_base_url,
            timeout=self.settings.request_timeout_seconds,
        )
        self.adapter = _build_adapter(self.settings)
        self._agents: Dict[str, Agent] = {
            name: build_agent(name, self.adapter, self.client, self.settings)
            for name in ("consumer", "kitchen", "manager")
        }

    def agent_names(self) -> List[str]:
        return list(self._agents)

    def agent(self, name: str) -> Agent:
        agent = self._agents.get(name)
        if agent is None:
            raise UnknownAgentError(name)
        return agent

    def run(self, name: str, message: str, history: Optional[List[Dict[str, str]]] = None) -> str:
        return self.agent(name).run(message, history)

    def describe(self) -> List[Dict[str, Any]]:
        return [
            {"name": agent.name, "tools": [tool.name for tool in agent.tools]}
            for agent in self._agents.values()
        ]

    def close(self) -> None:
        self.client.close()
