import yaml
from src.adp_event import AdpMqttClient
from src.mock_generator import run_mock

if __name__ == "__main__":
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    adp = AdpMqttClient(
        broker=cfg["mqtt"]["broker"],
        port=cfg["mqtt"]["port"],
        topic=cfg["mqtt"]["topic"],
        client_id=cfg["mqtt"]["client_id"],
        store_id=cfg["store_id"],
        device_id=cfg["device_id"]
    )
    adp.connect()
    run_mock(adp, cfg)
