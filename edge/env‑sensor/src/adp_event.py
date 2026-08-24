import json
import time
import uuid
from datetime import datetime
import paho.mqtt.client as mqtt
from .exceptions import MQTTNotConnectedError


class AdpMqttClient:
    def __init__(self, broker, port, topic, client_id, store_id, device_id, debug_print_only=False):
        self.broker = broker
        self.port = port
        self.topic = topic
        self.client_id = client_id
        self.store_id = store_id
        self.device_id = device_id
        self.module_name = "front_vision"
        self.debug_print_only = debug_print_only  #调试开关：True只打印，不连MQTT
        self.connected = False
        self.client = mqtt.Client(client_id=client_id)

        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                self.connected = True

        self.client.on_connect = on_connect

    def connect(self):
        if self.debug_print_only:
            print("[调试模式] 跳过真实MQTT连接，仅打印报文")
            self.connected = True
            return
        self.client.connect(self.broker, self.port, keepalive=60)
        self.client.loop_start()
        time.sleep(0.5)

    def build_event(self, event_type, payload, severity="info", trace_id=""):
        ts = datetime.now().astimezone().isoformat(timespec="seconds")
        evt = {
            "protocol": "ADP",
            "version": "1.0",
            "event_id": f"EVT‑{uuid.uuid4().hex[:12]}",
            "trace_id": trace_id,
            "timestamp": ts,
            "store_id": self.store_id,
            "source": {
                "module": self.module_name,
                "device_id": self.device_id
            },
            "event_type": event_type,
            "severity": severity,
            "payload": payload
        }
        return evt

    def publish(self, event_type, payload, severity="info", trace_id=""):
        if not self.connected:
            raise MQTTNotConnectedError("MQTT未建立连接")
        evt = self.build_event(event_type, payload, severity, trace_id)
        raw_json = json.dumps(evt, ensure_ascii=False, indent=2)
        if self.debug_print_only:
            print("\n======= 输出ADP事件报文 =======")
            print(raw_json)
            return
        self.client.publish(self.topic, raw_json)
        return evt
