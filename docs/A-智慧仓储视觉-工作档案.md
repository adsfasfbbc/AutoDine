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
- 本地权重：`edge/smart_storage_vision/output/training/fruit_quality_yolo26/weights/best.pt`（被 Git 忽略）
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

## 2026-08-24 YOLO11 → YOLO26 本地迁移

### 已完成

- 选择 YOLO26n，而不是 DETR/Faster R-CNN：现有 Ultralytics 管线可直接复用，检测、分类和边缘导出路径一致，适合时间紧迫的实时原型；CountGD++ 继续并行作为开放词汇计数后端。
- 计数与人员检测默认权重改为 `yolo26n.pt`；缺陷训练默认权重改为 `yolo26n-cls.pt`，没有把旧 YOLO11 权重改名冒充新模型。
- 在 RTX 5080 上用原 11,200/2,400/2,400 划分重新训练 YOLO26n-cls 10 轮。第 10 轮验证 top-1 为 99.958%、top-5 为 100%；独立 test top-1/top-5 均为 100%。新 `best.pt` SHA-256 为 `16EB3FAA08AB65C269D319B1317CA7F2676DC04AB6A622038A22D21A87208D86`。
- 公共领域水果盘真实推理得到苹果 6 框、香蕉 1 框、橙子 7 框，并生成 5 个 ADP 事件；YOLO26 人员检测在真实图片中检测到 5 人并生成未授权进入事件。
- YOLO26 验证完成后删除旧 `yolo11n.pt`、`yolo11n-cls.pt` 和旧 YOLO11 训练/测试输出，释放约 20.6 MB；FRUIT-16K 与全部 YOLO26 权重保留。旧文件未进入回收站，需要时只能重新下载或训练。

### 仍需如实说明

- 人工抽查发现 1 张 `F_Banana` 验证图片被高置信度判为 `S_Banana`；公共领域水果盘也产生 1 个 `defective` 与 3 个 `review`。因此公开数据汇总高分不能证明现场缺陷识别可靠，摄像头测试必须重点统计误报。
- COCO 检测器对 FRUIT-16K 的近距离单果分类图片没有框，这不是 Mock，也不是缺陷分类器失败；计数验收应使用货架/水果盘场景并最终训练现场 YOLO26 检测权重。
- 门状态和授权状态仍为命令行模拟；只有人员检测是真实 YOLO26 推理。

## 2026-08-24 JupyterLab 摄像头原型（本地实现）

### 已完成

- 新增 `edge/smart_storage_vision/notebooks/camera_realtime_yolo26.ipynb`，在 Jupyter 页面内持续刷新带框画面。
- 同一 YOLO26n 检测器处理苹果、香蕉、橙子和人员；水果裁剪继续使用已训练的 YOLO26n-cls 执行整果品质分类。
- 画面和状态栏展示原始品质类别、`good/defective/review`、置信度、当前视野水果数量与人数。
- 推理运行在后台线程，Notebook 单元格可返回以响应红色停止按钮；停止后释放摄像头。后台异常会保留并显示，不会伪装成正常停止。
- 新增硬件依赖文件，明确不通过普通 requirements 覆盖硬件厂商提供的 PyTorch/CUDA。
- 当前人员功能只是“视野内人数”，没有使用 Mock 门状态或授权状态，也没有在缺少输入时虚构未授权进入结果。

### 尚未完成及原因

- 尚未在目标硬件读取真实摄像头；用户还未连接设备，硬件型号、架构、摄像头接口和 Jupyter 可访问性尚待现场确认。
- 尚未测量目标设备 FPS、延迟、温度和显存；这些只能在实际硬件模型栈和摄像头输入下测量。
- 当前计数是单帧当前视野计数，不是 Tracking/越线累计计数。
- 当前缺陷能力仍是整果分类，不是病斑、霉斑或破损框/分割。
- 正式 UI 尚未建设；本阶段只交付 Jupyter 可视化，后续由 F 模块消费 A/Core 接口实现。

## 2026-08-24 Orin摄像头实机验收与发布前整合

### 已完成

- 在NVIDIA Orin提供的JupyterLab中打开真实USB摄像头，实时画面、人员检测框、`person`标签、当前人数和停止释放均成功；该过程没有使用Mock。
- 首次失败时，摄像头帧、模型SHA-256、COCO类别表和CUDA均正常，但硬件Ultralytics `8.3.58`在CPU/GPU上都漏检清晰人员并产生错误类别。相同截图在本地 `8.4.123`中检测到两个person框，置信度约0.926和0.618，定位为YOLO26运行库版本不兼容，而不是训练、视频输入或CUDA单点问题。
- 通过官方离线wheel只把Ultralytics升级到 `8.4.123`，保留Orin原有PyTorch `2.3.0`和OpenCV `4.12.0`；重启Jupyter内核后实时人员检测恢复正常。
- 摄像头Notebook继续提供当前视野水果计数与整果品质分类。按用户决定，本阶段接受分类原型，不继续开发病斑框/分割。
- FRUIT-16K哈希审计确认16,000张中只有14,727个不同文件，600组完全重复图片跨数据划分；原始接近100%的指标受泄漏影响。排除与训练集完全相同的图片后，验证集2,128张有1次品质误判，测试集2,134张0次，但仍不能排除近重复帧和现场域偏移。
- 用户已手动pull `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`；本地只读检查确认digest为 `sha256:3d614dfd422b7e43647491cbf07d6acc516c032fc49c594a94afdebd52552fb9`，大小9,356,854,547字节。没有prune；Stage 3和CountGD++后续按用户要求暂停。
- 获取远端最新main并使用fast-forward原样接入组员的环境传感器提交；没有修改 `edge/env-sensor`、B、C、D、E或F模块实现。
- 发布前全仓库按项目配置运行59项测试全部通过；Notebook代码单元可编译、无输出，数据清单YAML可解析。
- 发布前真实模型复核：水果盘得到苹果6、香蕉1、橙子7，苹果中1个 `defective`、3个 `review`，生成5个A事件；人员图检测5人。在命令行模拟门开且无授权的前提下生成 `vision.storage.security`，模拟输入已在结果中标明。
- 重新生成本地硬件交付包 `AutoDine-camera-yolo26-prototype-20260824-v2.zip`，包含摄像头源码/Notebook、两个模型权重和Ultralytics 8.4.123离线wheel，排除Git历史、数据集、缓存、画面、skill和 `MISSION.md`；该zip不上传GitHub。

### 发布前风险审查

- A摄像头Notebook没有硬编码实测内网IP、RTSP密码、API Key或Core凭据，且提交版本没有输出单元格，不包含人员截图。
- 模型、数据集、离线wheel、交付zip、摄像头画面、skill和 `MISSION.md`不进入Git提交。
- `publish_to_core`当前没有认证/TLS配置，只能视为受信任本地原型接口；跨主机部署前必须由C/D补充认证网关或mTLS、来源/速率限制与重放防护。
- JupyterLab必须启用token/密码并限制在可信局域网/VPN/SSH隧道，不公开暴露8888端口。
- 仓库中组员历史提交已存在若干 `__pycache__/*.pyc`，本次不擅自删除或改写组员文件；建议由对应模块负责人另行清理。

### 仍未完成及原因

- 尚未用真实苹果、香蕉、橙子完成Orin摄像头的逐类现场准确率记录；本次实机已确认人员视觉链路，不能据此假设水果效果。
- 摄像头实时循环尚未直接发布稳定后的ADP事件；当前真实图片管线与Core集成测试已存在，但实时多帧需要节流/去抖，避免每帧重复写库存或告警。
- 未授权进入的人员检测、规则和Core告警已具备，但真实门磁/门锁状态及授权窗口尚未接入，因此防盗硬件端到端仍未完成。
- CountGD++只完成基础镜像pull，尚未完成Stage 3、GroundingDINO、Detectron2、checkpoint、真实推理或A适配；这是按用户指令暂停，不是部署成功。
- 正式UI、Tracking/越线累计计数和病斑区域定位未实现；分别留给F联动及后续增强。

## 2026-08-24 六类水果检测与品质分类 V2

### 本次做了什么

- 使用 Fruits-detection 已有边界框训练 YOLO26n 六类水果检测器，类别为 apple、banana、grape、orange、pineapple、watermelon。独立测试集 457 张、1636 个框，Precision=0.529、Recall=0.416、mAP50=0.418、mAP50-95=0.279。
- 检测最佳权重为 `fruit_detector_yolo26n_v1_best.pt`，SHA-256 为 `9A8F8E5CC87C58CF3263FC5D04615126B3B8A41F48BD94988272E4DE908C9100`。旧通用人员权重和旧品质训练目录均保留，没有覆盖。
- 将 FRUIT-16K 与 `Original Image` 的 fresh/rotten apple 合并，按来源组拆分并删除完全重复文件，得到 12,531/2,764/2,625 的训练、验证、独立测试集，共 26 个 fresh/rotten 类。
- YOLO26n-cls 训练到 30 轮。第一次托管会话在保存第 24 轮后结束，没有留下异常栈；确认 `last.pt` 完整后用原生 `resume=True` 从第 25 轮续训，没有从头重跑。独立测试 Top-1=99.314%、Top-5=99.962%。
- 品质最佳权重为 `fruit_quality_yolo26_v2_best.pt`，SHA-256 为 `56356D4FC5A34741F67074E7173DB88F91C6450E0A7F11D8EEC8DB5C4A5E1091`。
- 静态联合回归使用真实权重：清晰人员样图检测到 1 人、置信度 0.953；缺陷橙子样图检测到 `orange 0.97`，同种品质输出 `defective 1.00 (rotten_orange)`。标注框已视觉抽查正确，没有使用 Mock。
- 将人员检测与水果检测拆为两个独立 YOLO 模型，避免自训练六类水果模型丢失 `person` 类。摄像头状态栏扩展为六类水果当前视野计数。
- 修正品质异种误判：先由检测器确定水果种类，再只比较同种 `fresh_*`/`rotten_*` 概率。菠萝和西瓜没有品质训练类时明确输出 `review`。
- A 模块单元与集成测试 12 项全部通过。Notebook 已切换为三个本地权重，仍保留可停止后台循环和 Jupyter 画面。

### 本次没有做什么及原因

- 没有在 Orin 上复测新六类水果模型，因为用户已断开硬件；本次只完成 Windows/RTX 5080 静态联合回归。下一次需把更新交付包上传硬件后逐类实测。
- 没有把整果分类改为病斑框或分割，因为当前批准的技术原型仍以整果分类验收，现有品质数据也没有缺陷区域标注。
- 菠萝和西瓜没有品质分类结果，因为 26 类品质数据不含这两类；当前如实进入 `review`，没有借用其他水果类别，也没有 Mock。
- 检测 Recall 只有 0.416，不能声称六类水果现场识别已经准确完成；需要摄像头实测、误检漏检归档和补充现场数据。
- 品质测试接近 100% 不代表现场准确率。完全重复文件已删除，但公开数据仍可能存在近重复帧、统一背景和采集域捷径。
- CountGD++ 仍按用户要求停在镜像已 pull、Stage 3 未验证的状态，没有继续安装、编译或推理。
- 没有提交或上传 GitHub，没有修改远端、没有 force push，也没有触碰组员模块。

### 下一步怎么做

1. 重新连接 Orin/JupyterLab，上传更新后的精简交付包，从 Notebook 依次验证人员和六类水果框、当前视野计数、品质状态、FPS、停止释放。
2. 对现场漏检和误检保存少量、去隐私、按拍摄会话分组的标注样本，优先提高六类检测 Recall。
3. 为菠萝、西瓜补充 fresh/rotten 品质数据；需要病斑定位时另建带框/掩码的数据集和检测/分割模型。
4. 摄像头结果稳定后增加多帧去抖与节流，再通过现有 `SmartStoragePipeline → ADP → Core` 发布，避免逐帧重复事件。

## 2026-08-25 六类模型发布整合

### 本次整理

- 先抓取并纯快进到远端最新 `main`，原样保留组员对 `edge/env-sensor` 的两次更新；A 的本地改动与这些路径没有重叠，没有改写组员历史。
- 将葡萄、菠萝、西瓜补入Core种子目录，与已有苹果、香蕉、橙子共同形成六个 `pcs` 原料ID；只补齐A事件所需主数据，没有修改菜单BOM或Core处理逻辑。
- 将A到Core的目录契约测试扩大到全部六类，防止模型类别与Core原料ID再次悄然失配。
- 删除已被 `prepare_v2_datasets.py` 完整替代的旧 `prepare_quality_dataset.py`。新版入口包含检测标注审计、图片有效性检查、完全重复文件去重、来源分组切分与许可状态记录，避免组员误用旧随机切分流程。
- Git交付仍不包含模型权重、原始数据集、训练输出、摄像头画面、缓存、个人skill、`MISSION.md`或本地交付压缩包。

### 仍然存在的边界

- 六类检测 Recall=0.416，仍是技术原型；目录联动通过不等于现场精度通过。
- 菠萝和西瓜缺少品质训练类别，只能进入 `review`；没有用其他水果结果或Mock代替。
- `MockBackend` 与 `mock_scene.json` 只用于协议、库存变化和告警规则的可重复回归；真实YOLO推理不会自动回落到Mock。
- 门开与授权仍是演示输入，CountGD++仍停在镜像已pull、Stage 3未执行；二者都没有伪装为硬件或模型已完成。
