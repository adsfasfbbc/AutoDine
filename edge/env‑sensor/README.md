# env_sensor
消费区 Modbus‑RTU 环境传感器采集模块

## 功能说明
- 通过 Modbus‑RTU 串口读取环境传感器（温湿度、烟雾等）数据
- 按照项目ADP协议标准封装事件报文，支持MQTT发布
- 内置Mock仿真模式，本地无需真实硬件、无需MQTT服务即可调试
- 支持调试打印开关 `debug_print_only`，控制台直接输出完整JSON报文
- 提供单元测试校验ADP事件输出格式正确性

## 目录结构
env_sensor/
├── main.py                 # 程序入口
├── config.yaml             # 模块配置文件
├── requirements.txt        # python 依赖
├── src/
│   ├── **init**.py
│   ├── adp_event.py        # ADP 事件封装
│   ├── exceptions.py       # 自定义异常
│   ├── mock_generator.py   # mock 仿真数据生成
│   └── modbus_env_sensor.py # modbus 硬件读取逻辑
├── logs/                   # 日志输出目录
├── test/
│   ├── **init**.py
│   ├── test_adp_schema.py  # ADP 事件格式单元测试
│   └── test_mock.py
└── docs/
└── front_vision_event.md # ADP 事件字段文档

## 配置说明

修改 `config.yaml`

- `mock_mode`: true = 仿真模式；false = 真实硬件 Modbus 采集
- `debug_print_only`: true 仅控制台打印 JSON，不连接 MQTT；false 启用真实 MQTT 发布
- MQTT broker、串口设备号、store_id、device_id 根据部署环境修改

> 
> 提交的 config.yaml 为模板配置，生产环境请勿直接填写密钥与真实 IP。

## 运行方式

### 1. 单元测试（校验 ADP 事件格式，无需硬件 / MQTT）

```
python -m test.test_adp_schema
```

预期输出：`✅ ADP schema校验通过`

### 2. Mock 仿真调试模式（Windows 本地开发）

修改 config.yaml:

```
mock_mode: true
```

开启 `debug_print_only: true`

```
python main.py
```

控制台周期性打印 ADP 完整 JSON 事件报文。

### 3. 真实硬件运行（边缘 Linux 设备）

1. 设置 `mock_mode: false`
2. 设置 `debug_print_only: false`
3. 确认串口设备、MQTT broker 配置正确

```
python main.py
```

## 注意事项

1. Windows 下无 Modbus 串口硬件，仅可使用 mock 模式调试
2. logs/ 存放运行日志，日志文件不会提交至 git
3. 部署前确认串口权限（Linux 需添加 dialout 用户组权限）
4. MQTT 服务正常运行才可进行真实报文发布