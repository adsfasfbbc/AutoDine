import yaml
import time
from src.adp_event import AdpMqttClient
from src.mock_generator import run_mock

def main():
    with open("config.yaml", "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    adp = AdpMqttClient(
        broker=cfg["mqtt"]["broker"],
        port=cfg["mqtt"]["port"],
        topic=cfg["mqtt"]["topic"],
        client_id=cfg["mqtt"]["client_id"],
        store_id=cfg["store_id"],
        device_id=cfg["device_id"],
        debug_print_only=True   # Windows调试：只打印JSON，不连接MQTT服务
    )

    adp.connect()
    print("=== front_vision 模块启动 ===")

    if cfg["mock_mode"]:
        print("当前为Mock模拟模式，输出仿真传感器数据")
        run_mock(adp, cfg)
    else:
        print("真实硬件模式（Windows下无485硬件，暂不可用）")
        # 这里后续放真实Modbus读取传感器逻辑
        while True:
            time.sleep(1)

if __name__ == "__main__":
    main()
