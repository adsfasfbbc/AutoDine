"""AutoDine Agent Hub.

Three LLM-driven agents (Consumer / Kitchen / Manager) that interact with the
AutoDineCore middle platform exclusively through its REST API via tool calling.
The agents never access the Core database directly.
"""

__version__ = "0.1.0"
