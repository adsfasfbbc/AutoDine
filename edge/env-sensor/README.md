```
# 多环境传感器数据采集实验
基于 Python + Modbus‑RTU 实现多传感器数据采集与智能家居控制建议。

## 功能
- 通过串口读取 Modbus‑RTU 传感器数据
- Modbus CRC16 报文校验，支持16位有符号寄存器解析，兼容负温度
- 采集：TVOC、温度、湿度、PM2.5、大气压、火焰信号、CO₂
- 定时周期采样，时间与测量数据保存至 CSV 文件
- 根据传感器数值输出智能家居控制建议：
  - 温度过高 → 建议开启空调制冷
  - 温度过低 → 建议开启空调制热
  - 湿度过高 → 建议开启空调除湿
  - TVOC 空气质量超标 → 建议打开风扇（可调用已有风扇控制代码）
  - 检测到火焰信号 → 警告提示立即撤离现场
  - 全部环境指标正常 → 输出提示：当前环境适宜
- Ctrl+C 安全停止程序

## 运行环境
- Ubuntu / Linux
- Python3
- pyserial 库

## 安装依赖
```bash
pip3 install pyserial
```

## 使用步骤

1. 将传感器接 USB‑RS485 转换器，确认串口设备为 `/dev/ttyUSB0`
2. 设置串口权限

```
sudo chmod 666 /dev/ttyUSB0
```

3. 运行采集程序

```
python3 main.py
```

4. `Ctrl+C` 结束程序，采集数据保存在 `sensor_data.csv`

## 文件说明

- `main.py`：主采集程序
- `sensor_data.csv`：输出的采集数据文件

## 配置参数（在 main.py 配置区修改）

表格

| 参数 | 说明 |
| --- | --- |
| TEMP_HIGH | 温度高于该值建议制冷 |
| TEMP_LOW | 温度低于该值建议制热 |
| TVOC_LIMIT | TVOC 阈值，超过建议开风扇 |
| HUMI_HIGH | 湿度高于该值建议除湿 |
| FLAME_ALARM | 火焰告警触发阈值 |