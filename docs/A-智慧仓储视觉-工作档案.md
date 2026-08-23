# A：智慧仓储视觉工作档案

## 2026-08-23 本地初步可交付

### 已完成

- 从 `origin/main` 开始联动组员更新后的 Core 严格事件协议；没有 force push，没有改写组员远端历史。
- 检查 Windows、WSL2、Ubuntu、Docker 与 GPU。设备为 NVIDIA GeForce RTX 5080 Laptop GPU（16 GB）。`nvidia-smi` 的 CUDA 13.1 是驱动可支持上限，不代表 WSL 已安装 13.1 Toolkit。
- 验证 OpenCV Conda 环境中的 PyTorch `2.13.0+cu130`、torchvision `0.28.0+cu130`、Ultralytics `8.4.123` 可在 RTX 5080 执行 CUDA 推理。
- 真实 YOLO 水果计数：公共水果碗图片检测到香蕉 1 框、橙子 7 框。香蕉“一串算一框”说明通用 COCO 权重的计数语义仍需现场自定义检测数据校准。
- 从 Mendeley 官方下载 FRUIT-16K（16,000 张，16 个水果×鲜/腐类别，CC BY 4.0），压缩包 SHA-256 为 `9FF1C7EFEB7C130F6D476ADBEE5C007A12DF4D69960EB2356F0B34FEDB75C59C`。
- 按随机种子 42 划分训练 11,200、验证 2,400、测试 2,400 张；在 RTX 5080 上训练 YOLO11n 分类缺陷模型 10 轮。
- 独立测试集 top-1/top-5 均为 100%。本地 `best.pt` SHA-256 为 `8CD6F8478B26A5060DBDBCA2CD6F518146DAFBB51545AD0C6D15CFEB3D4285CA`。该高分只证明同分布公开数据表现，不能外推现场摄像头。
- 端到端真实推理：水果框经缺陷分类后，1 个橙子高置信度判为 `defective`，5 个低置信度目标进入 `review`，生成 `quality.abnormal`。没有把低置信度结果伪装为正常。
- 真实 YOLO 人员检测：真实图片检测到 4 人；门区有人、门开且无授权时生成 `vision.storage.security`。
- Core 已严格校验两种安全事件，创建告警并产生 `alarm.updated`；同步 AsyncAPI/WebSocket 协议。
- A 针对性测试通过；补充 YOLO 水果 ID 与 Core 种子目录一致性检查后，与组员最新火灾检测提交合并的全仓库运行结果为 57 项通过。

### 缺陷检测的准确范围

本版完成的是水果实例级缺陷分类：先检测每个水果，再把裁剪交给 fresh/spoiled 分类模型，输出 `good/defective/review`。它不能定位病斑、霉斑或破损区域，因为 FRUIT-16K 没有缺陷框或掩码。缺陷区域定位留作后续完善，不能把当前结果冒充病斑检测。

### 使用了什么 Mock

- `run_demo.py` 与 `data/mock_scene.json` 仍保留，用于无 GPU 的事件、库存减少规则和 Core 协议回归。
- Mock 中的检测框、类别、置信度和质量状态都是固定输入，不是模型结果。
- 本地 YOLO 计数、YOLO 缺陷分类和 YOLO 人员检测均另有真实图片/CUDA 运行证据，不依赖 Mock。
- 门开与授权状态当前由演示命令行参数模拟；尚未接门磁/门锁与 Core 授权事件。

### 尚未完成

- CountGD++ 尚未完成部署。已通过 WSL2 GPU 与 CUDA 12.8 Docker GPU passthrough；指定 PyTorch 2.7.1/cu128 devel 镜像尚未 pull 完成，因此 GroundingDINO、Detectron2、checkpoint 与真实推理均未开始。
- RTSP 摄像头、门磁/门锁授权、Zeuslap 实机尚未联调，缺少设备地址、D 模块事件与现场标定数据。
- 现场水果数据尚未采集，公开数据测试 100% 不能代表真实仓储精度。
- 病斑区域检测/分割尚未训练，原因是当前数据集只有整果类别标签。

### 本地检查入口

- 说明：`edge/smart_storage_vision/README.md`
- YOLO 计数/缺陷：`edge/smart_storage_vision/run_yolo_inventory_demo.py`
- YOLO 缺陷训练：`edge/smart_storage_vision/train_quality_yolo.py`
- YOLO 防盗：`edge/smart_storage_vision/run_security_demo.py`
- 本地权重：`edge/smart_storage_vision/output/training/fruit_quality_yolo/weights/best.pt`（被 Git 忽略）
- 工作后续：`docs/A-智慧仓储视觉-下一步计划.md`

## 2026-08-24 CountGD++ 部署暂停与交接

### 已完成

- Stage 1：WSL2 Ubuntu 26.04、内核 `6.18.33.2-microsoft-standard-WSL2` 可看到 NVIDIA GeForce RTX 5080 Laptop GPU，驱动 592.27，compute capability 12.0。
- Stage 2：Docker 29.7.2 使用 `nvidia/cuda:12.8.1-base-ubuntu22.04` 成功看到 RTX 5080；镜像 digest 为 `sha256:001469ea0f3dec85a1ca929aeea3b58ae369d4c11228b10aec1f642bb6ca7a6f`。
- 定位第一次 PyTorch 镜像 pull 的失败层与完整错误：最后一层期望 digest 为 `1953a5f9...`，实际收到 `d0fbaabf...`，Docker 以 `failed precondition` 拒绝提交，没有把错误内容当作可用镜像。
- 确认根因链包含四个旧/第三方 Docker registry mirrors；移除 mirrors 后 daemon 显示 `[]`。原配置备份为 `C:\Users\Dyf\.docker\daemon.json.autodine-backup-20260824`。
- 未运行任何 prune，未删除 layer、cache 或镜像。第二次官方源 pull 按用户指令主动停止，交由用户在 WSL2 终端完成。
- 2026-08-24 再次只读检查时，Docker 仍报告目标 PyTorch 镜像不存在；因此本轮交付继续使用真实 YOLO，未调用 CountGD++，也没有回退到 Mock。

### GitHub 联动记录

- 获取到组员新增的 `6e8a2d0`、`87de26e`、`48e25c6` 三个提交，内容为 B/Core 的火灾双确认能力。
- 使用普通 merge 保留上述提交及其哈希；唯一冲突位于 Core 事件路由的相邻插入点，解决方式仅为同时保留组员的 `vision.front.fire` 与 A 的 `vision.storage.security` 两条路由。
- 未修改 `edge/front_vision` 的组员实现，合并后全仓库 57 项测试通过。

### 未完成及原因

- Stage 3 未完成：目标镜像尚未 pull 成功，所以不能验证容器内 PyTorch 2.7.1、CUDA 12.8、sm_120 与 CUDA tensor 运算。
- GroundingDINO、Detectron2 和 CountGD++ 核心 import 未开始：分阶段原则要求 Stage 3 先通过。
- checkpoint 加载与最小图片推理未开始：基础运行环境尚未通过，且权重尚未下载。
- CountGD++ 尚未接入 `SmartStoragePipeline`：只有真实推理返回框后才实现适配，避免先写无法验证的高层代码。

### 用户手动操作

在 WSL2 Ubuntu 中执行并等待成功：

```bash
docker pull pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

成功后保留最后的 image digest 输出，再通知 Codex 从 Stage 3 继续。详细验证顺序见 `docs/COUNTGD_DEPLOYMENT.md`。
