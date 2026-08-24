from __future__ import annotations

from typing import Any, Optional


class AgentHubError(Exception):
    """Base class for agent hub errors."""


class CoreAPIError(AgentHubError):
    """Raised when the Core middle platform returns a non-2xx response."""

    def __init__(
        self,
        *,
        status_code: int,
        code: Optional[Any] = None,
        message: str = "",
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def __str__(self) -> str:
        return f"CoreAPIError({self.status_code}, code={self.code}): {self.message}"


class UnknownAgentError(AgentHubError):
    """Raised when an unknown agent name is requested."""

    def __init__(self, name: str) -> None:
        super().__init__(f"unknown agent '{name}'")
        self.name = name
