```
# 多传感器数据采集实验
基于 Python 实现 Modbus‑RTU 多环境传感器数据采集程序。

## 功能说明
- 通过串口读取 Modbus‑RTU 传感器数据
- Modbus 报文 CRC16 校验
- 支持16位有符号寄存器解析，兼容负温度读取
- 采集温度、湿度、大气压、TVOC、CO₂、PM2.5、火焰状态
- 定时周期采样，将时间与测量数据保存到 CSV 文件
- Ctrl+C 安全结束程序

## 运行环境
- Ubuntu / Linux
- Python3
- pyserial 库

## 安装依赖
```bash
pip3 install pyserial
```

## 使用方法

1. 将传感器连接 USB‑RS485 转换器，确认串口设备 `/dev/ttyUSB0`
2. 赋予串口权限

```
sudo chmod 666 /dev/ttyUSB0
```

3. 运行采集程序

```
python3 main.py
```

4. 按下 `Ctrl+C` 停止采集，数据自动保存在 `sensor_data.csv`

## 文件清单

- `main.py`：主采集程序
- `sensor_data.csv`：输出采集数据文件

## 实验调试说明

- 若读数异常，优先确认寄存器地址是否匹配传感器手册
- 不同物理量缩放系数不同，根据手册配置 `div` 换算系数
- 可使用寄存器扫描脚本定位正确测量寄存器