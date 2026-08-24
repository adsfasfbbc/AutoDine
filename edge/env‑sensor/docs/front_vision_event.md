# M02 FrontVision 输出事件 ADP v1.0 Schema
> 当前模块功能：Modbus‑RTU多参数环境传感器，已移除全部视觉业务
store_id: S001
device_id: SENSOR_ENV01

## 事件列表
### 1. device.environment | info
```json
{
  "tvoc_ppb": int,
  "temperature": float,
  "humidity": float,
  "pm25": int,
  "atm_pressure": float,
  "fire": int,
  "co2_ppm": int,
  "sensor_model": "Multi‑Modbus‑Env"
}
