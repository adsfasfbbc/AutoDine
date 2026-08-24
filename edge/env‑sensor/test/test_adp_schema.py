import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from src.adp_event import AdpMqttClient


def test_schema():
    # 直接实例化，传入需要的参数，不再写DummyClient
    client = AdpMqttClient(
        broker="127.0.0.1",
        port=1883,
        topic="adp/v1/event/S001",
        client_id="test_client",
        store_id="S001",
        device_id="SENSOR_ENV01"
    )
    evt = client.build_event("device.environment", {
        "tvoc_ppb": 100,
        "temperature": 25.0,
        "humidity": 50.0,
        "pm25": 20,
        "atm_pressure": 1013.0,
        "fire": 0,
        "co2_ppm": 600,
        "sensor_model": "Multi‑Modbus‑Env"
    })
    required = ["protocol", "version", "event_id", "timestamp", "store_id", "source", "event_type", "severity", "payload"]
    for k in required:
        assert k in evt, f"缺少字段:{k}"
    assert evt["protocol"] == "ADP"
    assert evt["version"] == "1.0"
    print("✅ ADP schema校验通过")


if __name__ == "__main__":
    test_schema()
