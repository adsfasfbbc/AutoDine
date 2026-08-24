from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict


@dataclass(frozen=True)
class ToolDefinition:
    """Provider-neutral tool definition.

    ``parameters`` is a JSON Schema describing the tool arguments.
    ``handler`` is ``handler(client, settings, **arguments) -> data`` where
    ``data`` is the parsed ``data`` field of the Core response envelope.
    """

    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
