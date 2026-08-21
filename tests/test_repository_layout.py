import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]

ROOT_FILES = [
    ".gitignore",
    "README.md",
    "pyproject.toml",
    ".env.example",
    "Makefile",
]

REQUIRED_DIRECTORIES = [
    "apps/autodine_core",
    "apps/agent_hub",
    "apps/dine_web",
    "edge/smart_storage_vision",
    "edge/front_vision",
    "edge/hardware_hub",
    "contracts/adp/v1",
    "contracts/openapi",
    "contracts/asyncapi",
    "contracts/websocket",
    "data/seed",
    "data/mock",
    "deploy",
    "scripts",
    "tests/e2e",
    "docs",
]

README_DIRECTORIES = REQUIRED_DIRECTORIES + [
    "contracts",
    "contracts/adp",
]

EVENT_NAMESPACES = [
    "vision.storage.",
    "vision.front.",
    "inventory.",
    "quality.",
    "menu.",
    "order.",
    "production.",
    "device.",
    "robot.",
    "alarm.",
    "queue.",
]

ENVELOPE_REQUIRED_FIELDS = [
    "protocol",
    "version",
    "event_id",
    "trace_id",
    "timestamp",
    "store_id",
    "source",
    "event_type",
    "severity",
    "payload",
]


def repo_path(relative_path: str) -> Path:
    return REPO_ROOT / relative_path


def test_repository_includes_required_root_files():
    missing = [path for path in ROOT_FILES if not repo_path(path).is_file()]

    assert missing == [], f"missing root files: {missing}"


def test_repository_includes_required_directories():
    missing = [path for path in REQUIRED_DIRECTORIES if not repo_path(path).is_dir()]

    assert missing == [], f"missing directories: {missing}"


def test_placeholder_directories_have_readmes():
    missing = [
        f"{path}/README.md"
        for path in README_DIRECTORIES
        if not repo_path(path,).joinpath("README.md").is_file()
    ]

    assert missing == [], f"missing placeholder READMEs: {missing}"


def test_adp_envelope_schema_defines_the_v1_contract():
    schema_path = repo_path("contracts/adp/v1/envelope.schema.json")

    assert schema_path.is_file(), "missing envelope schema"

    with schema_path.open("r", encoding="utf-8") as schema_file:
        schema = json.load(schema_file)

    assert schema.get("type") == "object"
    assert schema.get("additionalProperties") is False
    assert schema.get("$schema"), "expected a declared JSON Schema dialect"

    required_fields = schema.get("required", [])
    assert required_fields == ENVELOPE_REQUIRED_FIELDS

    properties = schema.get("properties", {})
    assert set(properties) == set(ENVELOPE_REQUIRED_FIELDS)
    assert properties["protocol"].get("const") == "ADP"
    assert properties["version"].get("const") == "1.0"
    assert properties["payload"].get("type") == "object"
    assert properties["event_type"].get("pattern")
    assert properties["source"].get("type") == "object"
    assert properties["source"].get("additionalProperties") is False
    assert properties["source"].get("required") == ["module"]
    assert properties["source"].get("properties", {}).get("module", {}).get("type") == "string"
    assert properties["source"].get("properties", {}).get("device_id", {}).get("type") == "string"

    event_type_description = json.dumps(properties["event_type"], ensure_ascii=False)
    for namespace in EVENT_NAMESPACES:
        assert namespace in event_type_description


def test_adp_envelope_schema_validates_structured_source_with_jsonschema():
    try:
        from jsonschema import Draft202012Validator
    except ModuleNotFoundError:
        pytest.fail("jsonschema must be installed for schema validation tests")

    schema_path = repo_path("contracts/adp/v1/envelope.schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)

    valid_event = {
        "protocol": "ADP",
        "version": "1.0",
        "event_id": "evt_001",
        "trace_id": "trace_001",
        "timestamp": "2026-08-21T00:00:00Z",
        "store_id": "store_001",
        "source": {
            "module": "vision.storage.camera_ingest",
            "device_id": "cam_001",
        },
        "event_type": "vision.storage.item_detected",
        "severity": "info",
        "payload": {
            "sku_id": "sku_001",
        },
    }
    validator.validate(valid_event)

    invalid_event = {
        **valid_event,
        "source": {
            "device_id": "cam_001",
        },
    }

    with pytest.raises(Exception):
        validator.validate(invalid_event)


def test_contracts_are_present_and_readable():
    openapi_path = repo_path("contracts/openapi/autodine-core-v1.yaml")
    asyncapi_path = repo_path("contracts/asyncapi/autodine-events-v1.yaml")
    websocket_path = repo_path("contracts/websocket/topics.yaml")

    for contract_path in [openapi_path, asyncapi_path, websocket_path]:
        assert contract_path.is_file(), f"missing contract: {contract_path}"

    openapi_text = openapi_path.read_text(encoding="utf-8")
    asyncapi_text = asyncapi_path.read_text(encoding="utf-8")
    websocket_text = websocket_path.read_text(encoding="utf-8")

    assert "openapi:" in openapi_text
    assert "AutoDine Core API v1" in openapi_text
    assert "version: 1.0.0" in openapi_text
    assert "/api/v1/events" in openapi_text
    assert "/api/v1/orders" in openapi_text

    assert "asyncapi:" in asyncapi_text
    assert "AutoDine Event Stream v1" in asyncapi_text
    assert "version: 1.0.0" in asyncapi_text
    assert "queue.updated" in asyncapi_text

    assert "endpoint: /ws/stores/{store_id}" in websocket_text

    for namespace in EVENT_NAMESPACES:
        assert namespace in asyncapi_text
        assert namespace in websocket_text
