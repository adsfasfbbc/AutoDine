import random
import time


def run_mock(adp_client, cfg):
    interval = cfg["report"]["env_report_interval_s"]
    while True:
        adp_client.publish(
            event_type="device.environment",
            payload={
                "tvoc_ppb": random.randint(10, 800),
                "temperature": round(random.uniform(22.0, 28.0), 1),
                "humidity": round(random.uniform(40, 65), 1),
                "pm25": random.randint(5, 40),
                "atm_pressure": round(random.uniform(980.0, 1030.0), 1),
                "fire": random.randint(0, 1),
                "co2_ppm": random.randint(420, 1200),
                "sensor_model": "Multi‑Modbus‑Env"
            },
            severity="info"
        )
        time.sleep(interval)
