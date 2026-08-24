from __future__ import annotations

from agent_hub.errors import UnknownAgentError


def _tool_names(hub, name: str) -> set:
    return {t.name for t in hub.agent(name).tools}


def test_consumer_tools(hub):
    assert _tool_names(hub, "consumer") == {
        "list_menu",
        "get_menu_item",
        "create_order",
        "get_order",
        "cancel_order",
    }


def test_kitchen_tools(hub):
    assert _tool_names(hub, "kitchen") == {
        "get_order",
        "start_production_task",
        "ready_production_task",
        "complete_production_task",
    }


def test_manager_tools(hub):
    assert _tool_names(hub, "manager") == {
        "list_inventory",
        "list_alarms",
        "acknowledge_alarm",
        "resolve_alarm",
        "list_queue_snapshots",
        "get_analytics_summary",
        "issue_device_command",
        "list_device_commands",
    }


def test_agents_are_isolated(hub):
    consumer = _tool_names(hub, "consumer")
    kitchen = _tool_names(hub, "kitchen")
    manager = _tool_names(hub, "manager")
    assert "start_production_task" not in consumer
    assert "create_order" not in kitchen
    assert "list_menu" not in manager
    assert "get_analytics_summary" not in consumer


def test_unknown_agent(hub):
    import pytest

    with pytest.raises(UnknownAgentError):
        hub.agent("nope")


def test_describe_lists_all_agents(hub):
    assert {a["name"] for a in hub.describe()} == {"consumer", "kitchen", "manager"}
