# front_vision (M02)

AutoDine 前厅边缘视觉服务：摄像头采集 → YOLO 人数计数（`queue.updated`）+
冲突检测（`vision.front.safety`）+ 火灾多通道投票检测（`vision.front.fire`），
事件以 ADP v1.0 协议发布到 Core 中台。
因隐私考虑已移除表情识别，CX 体验指标改由排队/等待时长等非生物特征数据替代。

## 安装

需要 Python 3.13。在仓库根目录执行：

```bash
python -m venv edge/front_vision/.venv
edge/front_vision/.venv/Scripts/python -m pip install --upgrade pip
# RTX 50 系（Blackwell sm_120）必须 cu128 构建：
edge/front_vision/.venv/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
edge/front_vision/.venv/Scripts/python -m pip install ultralytics onnxruntime \
    opencv-python fastapi uvicorn httpx pytest jsonschema "pyside6>=6.8,<6.9" \
    sounddevice librosa pyserial
# 注意：安装 ultralytics 可能把 torch 覆盖成 PyPI 的 CPU 版，务必再执行一次上一行的
# cu128 安装（pip 会跳过已满足的其余依赖），并用 torch.cuda.is_available() 验证。
# 以可编辑方式安装本包，使 python -m front_vision 可直接使用：
edge/front_vision/.venv/Scripts/python -m pip install -e edge/front_vision --no-deps
```

模型文件放入 `edge/front_vision/models/`（已 gitignore）：
- `yolo11n.pt` — ultralytics 首次运行时自动下载到当前目录，请移动到 `models/`；
- `yolo11n-pose.pt` — 冲突检测的姿态模型，同样由 ultralytics 自动下载后移动到 `models/`；
- `fire.pt` — 火焰检测模型（YOLO26n 微调的权重，单类别 fire）。训练方式见仓库根目录
  `scripts/train_fire.py`（`--data` 指向外部 YOLO 格式数据集的 data.yaml，数据集不入库），
  训练产物 `runs/detect/fire_train/weights/best.pt` 拷贝为 `models/fire.pt`；
  同目录的 `best.onnx` 拷贝为 `models/fire.onnx` 供 onnxruntime 兜底后端使用。
  **模型权重绝不提交进库**。

已知问题：
- 发布是异步的：事件进入内存队列由后台线程重试发送（3 次指数退避），Core 宕机不会阻塞推理。

## 启动

```bash
cd edge/front_vision
.venv/Scripts/python -m front_vision --source camera              # 摄像头
.venv/Scripts/python -m front_vision --source path/to/clip.mp4   # 视频文件（循环播放）
```

已 `pip install -e` 时可直接运行；否则需先 `PYTHONPATH=src`。

CLI 参数：`--source`、`--camera-index`、`--core-url`、`--store-id`、`--device-id`、
`--host`、`--port`（默认 5060，启动时检测占用）、`--backend auto|torch`、`--no-preview`、`--log-level`、
`--no-audio`（关闭声学通道，纯视觉按融合规则不上报）、`--simulate-safety`（注入合成双模态信号做演示）、
`--no-fire`（整体关闭火灾检测）、`--no-fire-sensor`（关闭环境传感器通道，仅剩视觉一路投票）、
`--fire-port`（传感器串口，默认 Windows `COM3` / Linux `/dev/ttyUSB0`）、
`--fire-model`（火焰模型路径，默认 `models/fire.pt`）、`--simulate-fire`（注入合成双通道火焰信号做演示）、
`--fire-vote-threshold`（规则 A 触发所需异常路数，默认 3）。

## 桌面 GUI 预览（--gui）

原生桌面调试窗口（PySide6），与网页预览互不影响——`--gui` 模式下**不启动 FastAPI**，只跑
采集 + 推理 + 事件发布 + 桌面窗口（Qt 事件循环在主线程，推理仍在后台线程）：

```bash
cd edge/front_vision
.venv/Scripts/python -m front_vision --source camera --gui               # 摄像头 + GUI
.venv/Scripts/python -m front_vision --source camera --gui --no-publish  # 纯本地演示，不发 ADP 事件
```

窗口标题 `AutoDine FrontVision - DEBUG`：左侧为标注后实时画面（与 /preview.mjpeg 同一份内存标注帧，
QTimer ~30ms 刷新），右侧面板显示当前人数、检测后端、推理 FPS 与 Core 发布状态（端点 + dropped 计数）。
触发安全告警时顶部显示红色横幅（网页调试页同样）。关闭窗口即退出并释放摄像头。帧只过内存，不落盘。

依赖 PySide6（已加入 pyproject.toml；Windows 上请用 `PySide6>=6.8,<6.9`，6.11.x 的 Qt6Core.dll
在本机加载失败）。无显示环境下测试用 `QT_QPA_PLATFORM=offscreen`（见 tests/test_gui.py）。

## 冲突检测（vision pose + 声学唤醒融合）

**融合规则**：视觉剧烈互动与声学高唤醒必须在 ±3s 时间窗内同时成立，才发布
`vision.front.safety`；单模态只记 debug 日志，绝不上报。severity 默认 `warning`，
持续 >10s 或冷却期内重复触发升 `critical`；30s 冷却去重。

- 视觉（`safety_vision.py`）：YOLO11n-pose + 简版跟踪，2s 滑窗提取手腕/脚踝速度、
  两人躯干最小距离、躯干下坠速度，加权为 `vision_score`（阈值+滞回走 `FV_SAFETY_VISION_*`）。
- 声学（`safety_audio.py`）：sounddevice 采集 → 2s 环形缓冲 → 每秒提取响度（自适应基线）、
  频谱通量、F0 均值/抖动（librosa.yin）、能量起始峰速率，加权为 `audio_score`。
- 融合（`safety_fusion.py`）：双模态 AND + 冷却 + 升级，经 adp.py 发布，payload：
  `{event_subtype: "violent_interaction", confidence, vision_score, audio_score, duration_ms, zone_id}`。
- 触发时 GUI 与网页调试页显示红色告警横幅（纯状态展示，数秒后自动隐藏）。
- 无麦克风/姿态模型缺失时对应通道自动禁用，不报错中断服务。

**隐私设计**：音频只提物理特征，原始 PCM 只留 2s 内存环形缓冲、提完即弃、不落盘、不做 ASR；
视觉只用骨骼关键点轨迹，不存图像；双模态不同时成立不上报。

## 火灾多通道投票检测（8 路：火焰视觉 + 环境传感器）

**判定规则**：8 路通道（火焰视觉、火焰传感器、温度、湿度、TVOC、CO2、PM2.5、光照）各自给出
异常布尔 + 原始读数，满足任一规则即发布 `vision.front.fire`：

- **规则 A（`vote3`）**：≥ `FV_FIRE_VOTE_THRESHOLD`（默认 3）路同时异常 → 判定火灾；
- **规则 B（`vision_flame`）**：火焰视觉与火焰传感器在 ±3s 时间窗内同时检出 → 判定火灾
  （沿用原有双确认）。

单路/双路异常只记 debug 日志，绝不上报。severity 默认 `warning`，持续 >10s 或冷却期内重复触发
升 `critical`；30s 冷却去重。未读到的通道（串口失败/寄存器超时，读数为 None）按正常计。

- 视觉（`fire_vision.py`）：单类别火焰检测模型 `models/fire.pt`（训练见 `scripts/train_fire.py`），
  torch 优先、onnxruntime 兜底（`models/fire.onnx`）；火焰推理在 `FV_INFER_EVERY_N_FRAMES`
  之上再按 `FV_FIRE_INFER_EVERY_N_FRAMES` 节流（中间帧复用上次结果）。检出框最高置信度即 `vision_conf`。
- 环境传感器（`env_sensor.py`）：pyserial 后台线程按 `FV_FIRE_SENSOR_POLL_S` 间隔轮询**同一台**
  Modbus-RTU 从机（地址 0x02，9600 8N1）的 7 个寄存器，查询与应答均带 CRC16 校验，
  值按有符号 int16 解析（负温度可正确解码）；单寄存器失败该轮记 None，不中断整轮。
  串口打开失败只记 warning 并降级为"全部通道未读"，服务不中断（仅剩视觉一路投票）。

  | 寄存器 | 通道 | 单位 |
  |---|---|---|
  | 0x0001 | TVOC | ppb |
  | 0x0002 | 温度（有符号 int16） | ℃ |
  | 0x0003 | 湿度 | %RH |
  | 0x0005 | PM2.5 | μg/m³ |
  | 0x0007 | 火焰（0/1） | — |
  | 0x0008 | 光照强度 | — |
  | 0x0009 | CO2 | ppm |

- 融合（`fire_fusion.py`）：规则 A/B 判定 + 冷却 + 升级，经 adp.py 发布，payload：
  `{event_subtype, confidence, vision_conf, sensor_state, duration_ms, zone_id,
  vote_count, abnormal_channels, triggered_rule, readings}`，其中 `triggered_rule` 为
  `"vote3"` 或 `"vision_flame"`，`abnormal_channels` 为异常通道名列表，
  `readings` 为 8 路当前值快照（未读为 null）。
- 触发时 GUI 与网页调试页显示红色告警横幅，含触发规则与异常路数（数秒后自动隐藏）。

**异常阈值（默认值仅供起步，必须现场标定）**：

| 通道 | 异常条件 | 配置项 | 默认 |
|---|---|---|---|
| 温度 | > 阈值 | `FV_FIRE_TEMP_THRESHOLD_C` | 45 ℃ |
| 湿度 | < 阈值 | `FV_FIRE_HUMIDITY_THRESHOLD_RH` | 20 %RH |
| TVOC | > 阈值 | `FV_FIRE_TVOC_THRESHOLD_PPB` | 600 ppb |
| CO2 | > 阈值 | `FV_FIRE_CO2_THRESHOLD_PPM` | 1500 ppm |
| PM2.5 | > 阈值 | `FV_FIRE_PM25_THRESHOLD` | 150 μg/m³ |
| 光照 | > 阈值 | `FV_FIRE_LIGHT_THRESHOLD` | 1000 |
| 火焰视觉 | 置信度超阈值 | `FV_FIRE_CONFIDENCE` | 0.25 |
| 火焰传感器 | == 1 | — | — |

**Core 侧联动**：Core 收到 `vision.front.fire` 后除开报警外，会查询该门店已注册设备
（`POST /api/v1/devices` 注册，`{store_id, device_id, device_type}`），对 `device_type`
属于关机清单（默认 `fan`、`air_conditioner`，可用 `AUTODINE_CORE_FIRE_SHUTDOWN_DEVICE_TYPES`
以 JSON 列表覆盖）的设备逐台创建 `power_off` 关机命令（`device.command` 事件经 WebSocket 扇出）。
门店无匹配设备时只记日志，不报错。

**传感器接线**：环境传感器（Modbus RTU，从站地址 0x02）经 USB 转 485/串口模块接入边缘主机，
Windows 上设备管理器里对应 `COMx`（用 `--fire-port` 或 `FV_FIRE_SENSOR_PORT` 指定），
Linux 上通常为 `/dev/ttyUSB0`；9600 8N1。

## 配置项（环境变量，前缀 `FV_`）

| 变量 | 默认 | 说明 |
|---|---|---|
| `FV_CAMERA_INDEX` | 0 | DirectShow 摄像头索引 |
| `FV_SOURCE` | camera | `camera` 或视频文件路径 |
| `FV_FRAME_WIDTH` / `FV_FRAME_HEIGHT` | 640 / 480 | 采集分辨率 |
| `FV_CORE_URL` | http://localhost:8000 | Core 中台地址 |
| `FV_STORE_ID` | store-main | 门店 ID |
| `FV_DEVICE_ID` | front-cam-01 | 设备 ID |
| `FV_QUEUE_ZONE_ID` | front-queue | 排队区域 ID |
| `FV_DETECTOR_BACKEND` | auto | `auto`（torch 优先，onnx 兜底）或 `torch` |
| `FV_PERSON_CONFIDENCE` | 0.4 | YOLO person 置信度阈值 |
| `FV_INFER_EVERY_N_FRAMES` | 5 | 每 N 帧做一次推理 |
| `FV_PREVIEW_ENABLED` | true | 调试预览（/ 页面与 /preview.mjpeg） |
| `FV_SMOOTH_WINDOW_S` | 3 | 人数滑动窗口（中位数平滑） |
| `FV_QUEUE_HEARTBEAT_S` | 10 | queue.updated 心跳周期 |
| `FV_SAFETY_ENABLED` | true | 冲突检测总开关 |
| `FV_SAFETY_ZONE_ID` | front-hall | safety 事件区域 ID |
| `FV_SAFETY_VISION_WINDOW_S` | 2 | 视觉特征滑窗 |
| `FV_SAFETY_VISION_THRESHOLD` | 0.6 | vision_score 阈值 |
| `FV_SAFETY_VISION_HYSTERESIS_S` | 2 | 视觉防抖滞回 |
| `FV_AUDIO_ENABLED` | true | 声学通道开关（--no-audio 对应 false） |
| `FV_AUDIO_DEVICE` | （默认设备） | 麦克风设备索引或名称 |
| `FV_AUDIO_SAMPLE_RATE` | 16000 | 采样率 |
| `FV_SAFETY_AUDIO_THRESHOLD` | 0.6 | audio_score 阈值 |
| `FV_SAFETY_AUDIO_BASELINE_ALPHA` | 0.02 | 响度自适应基线系数 |
| `FV_SAFETY_FUSION_WINDOW_S` | 3 | 双模态 ±3s 融合窗 |
| `FV_SAFETY_COOLDOWN_S` | 30 | 冷却去重 |
| `FV_SAFETY_CRITICAL_AFTER_S` | 10 | 持续升级 critical 阈值 |
| `FV_FIRE_ENABLED` | true | 火焰检测总开关（--no-fire 对应 false） |
| `FV_FIRE_ZONE_ID` | front-hall | fire 事件区域 ID |
| `FV_FIRE_MODEL_PATH` | models/fire.pt | 火焰检测模型路径 |
| `FV_FIRE_CONFIDENCE` | 0.25 | 火焰框置信度阈值 |
| `FV_FIRE_INFER_EVERY_N_FRAMES` | 5 | 火焰推理节流（在每 N 帧推理之上再节流） |
| `FV_FIRE_SENSOR_ENABLED` | true | 火焰传感器通道开关（--no-fire-sensor 对应 false） |
| `FV_FIRE_SENSOR_PORT` | （平台默认） | 传感器串口：Windows `COM3` / Linux `/dev/ttyUSB0` |
| `FV_FIRE_SENSOR_BAUDRATE` | 9600 | 串口波特率 |
| `FV_FIRE_SENSOR_POLL_S` | 0.1 | Modbus 轮询间隔 |
| `FV_FIRE_SENSOR_TIMEOUT_S` | 0.5 | 串口读超时 |
| `FV_FIRE_FUSION_WINDOW_S` | 3 | 规则 B 双通道 ±3s 融合窗 |
| `FV_FIRE_COOLDOWN_S` | 30 | 冷却去重 |
| `FV_FIRE_CRITICAL_AFTER_S` | 10 | 持续升级 critical 阈值 |
| `FV_FIRE_VOTE_THRESHOLD` | 3 | 规则 A 触发所需异常路数（--fire-vote-threshold） |
| `FV_FIRE_TEMP_THRESHOLD_C` | 45 | 温度异常阈值（>，℃，需现场标定） |
| `FV_FIRE_HUMIDITY_THRESHOLD_RH` | 20 | 湿度异常阈值（<，%RH，需现场标定） |
| `FV_FIRE_TVOC_THRESHOLD_PPB` | 600 | TVOC 异常阈值（>，ppb，需现场标定） |
| `FV_FIRE_CO2_THRESHOLD_PPM` | 1500 | CO2 异常阈值（>，ppm，需现场标定） |
| `FV_FIRE_PM25_THRESHOLD` | 150 | PM2.5 异常阈值（>，μg/m³，需现场标定） |
| `FV_FIRE_LIGHT_THRESHOLD` | 1000 | 光照异常阈值（>，需现场标定） |
| `FV_PORT` | 5060 | HTTP 服务端口 |

排队 ROI 在 `config.py` 的 `queue_roi`（归一化 x/y/w/h），v1 默认全画面。

## HTTP 接口

- `GET /health` — 服务与采集状态；
- `GET /metrics` — 当前人数、推理后端、推理 FPS、当前 safety 告警等；
- `GET /` — 调试页面（左侧 MJPEG 实时画面 + 右侧指标，每 2s 轮询 /metrics）；
- `GET /preview.mjpeg` — 标注后的 MJPEG 流（绿框=YOLO person+置信度，左上角人数与 FPS）。

## 调试预览（隐私注意）

预览**默认开启**，便于本机演示；帧仅在内存中保留最新一份，JPEG 也只存在于内存，不落盘。
生产环境或非本机演示机请用 `--no-preview`（或 `FV_PREVIEW_ENABLED=false`）关闭，关闭后推理循环零预览开销。

## 发布事件（ADP v1.0，POST {core}/api/v1/events）

| event_type | severity | payload | 触发 |
|---|---|---|---|
| `queue.updated` | info | `{zone_id, waiting_count}`（estimated_wait_seconds 暂缺省） | 人数变化或每 10s 心跳 |
| `vision.front.safety` | warning/critical | `{event_subtype, confidence, vision_score, audio_score, duration_ms, zone_id}` | 双模态 ±3s 同时成立；>10s 或冷却期内重触发升 critical |
| `vision.front.fire` | warning/critical | `{event_subtype, confidence, vision_conf, sensor_state, duration_ms, zone_id, vote_count, abnormal_channels, triggered_rule, readings}` | 规则 A：≥3 路异常；规则 B：火焰视觉+传感器 ±3s 双确认；>10s 或冷却期内重触发升 critical |

人数经 3 秒滑动窗口中位数平滑。

## 隐私说明

所有视频帧与音频仅在内存中处理，**绝不落盘**；音频原始 PCM 只保留 2 秒环形缓冲且提完特征即弃，
不做任何语音识别；视觉只使用骨骼关键点轨迹。发布到 Core 的只有计数与安全告警等聚合统计，
不包含任何图像或音频。

## 测试与冒烟

```bash
cd edge/front_vision
PYTHONPATH=src .venv/Scripts/python -m pytest tests -v        # 单元测试（无需摄像头/GPU）
.venv/Scripts/python scripts/smoke_front_vision.py            # 端到端冒烟（合成视频 + 假 Core）
```
