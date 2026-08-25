# A：智慧仓储视觉技术原型

本目录只负责 A 模块：仓储摄像头视觉推理、原料计数与质量观察、防盗判断，以及向 AutoDineCore 发布 ADP 1.0 事件。Core 负责库存/BOM/菜单等业务真值，D 模块负责硬件控制，F 模块负责最终界面。

## 当前完成度

| 功能 | 当前实现 | 真实性说明 |
| --- | --- | --- |
| 水果计数 | 自训练 YOLO26n 六类检测框计数 | Fruits-detection 数据集训练；独立测试 mAP50=0.418、mAP50-95=0.279。支持苹果、香蕉、葡萄、橙子、菠萝、西瓜；不是 Mock |
| 缺陷检测 | YOLO26n-cls 整果质量分类 | FRUIT-16K 与本地 fresh/rotten apple 合并去重后训练，独立测试 Top-1=99.314%、Top-5=99.962%；只在同种水果标签内判断。菠萝/西瓜无品质类时进入 `review`；不是 Mock |
| 人员检测 | Ultralytics YOLO26n person 类 | 已在 NVIDIA Orin 的真实 USB 摄像头/JupyterLab 画面中显示人员框、标签和当前人数；不是 Mock |
| 未授权进门 | 人在门区 + 门已开 + 无授权 | 人体检测是真实模型；演示中的门状态与授权是命令行模拟 |
| Core 告警 | `vision.storage.security` → Core 告警 → `alarm.updated` | 已通过集成测试 |
| CountGD++ | WSL2/Docker 分阶段兼容验证 | Stage 1/2 和目标 PyTorch 2.7.1/cu128 镜像 pull 已完成；Stage 3及后续按用户要求暂停，尚未编译、加载权重或推理；运行后端继续使用真实 YOLO |
| Mock 流程 | 固定检测框验证事件与 Core 协议 | 只用于可重复测试，不是模型交付结果 |
| 摄像头/JupyterLab | 实时推理 Notebook 与可停止后台循环 | 已在 Orin + USB 摄像头上真实运行，画面、人员框、标签、计数和停止均成功 |
| Zeuslap | 普通 HDMI 显示器 | 正式 UI 尚未建设，A 当前只提供 Notebook 画面和后续状态接口 |

### “缺陷检测”的准确范围

本版缺陷模型是水果实例级分类：YOLO 检测模型先框出每个水果，第二个 YOLO 分类模型再在该水果对应的 `fresh_*` 与 `rotten_*` 两类中判断 `good` 或 `defective`。低置信度、异种主分类以及没有对应品质类的菠萝/西瓜进入 `review`。因此它能回答“这个水果是否疑似腐坏”，并按实例计入 `quality.abnormal`。

它目前不能在水果表面再框出病斑、霉斑或破损的具体位置。原因是 FRUIT-16K 只提供整果鲜/腐类别，没有缺陷区域的边界框或分割掩码。后续需要增加带缺陷框/掩码的公开数据与现场标注，训练 YOLO detection/segmentation 缺陷定位模型；README 不会把实例分类结果冒充缺陷区域定位结果。

## JupyterLab 摄像头原型

`notebooks/camera_realtime_yolo26.ipynb` 在同一摄像头画面中执行：

- 独立 YOLO26n 模型分别执行人员检测和六类水果检测；
- 苹果、香蕉、葡萄、橙子框执行同种约束的 YOLO26n-cls 整果品质分类，菠萝/西瓜进入 `review`；
- 检测框、原始品质类别、`good/defective/review`、置信度和当前视野计数；
- Jupyter 页面内 JPEG 画面刷新；
- 红色停止按钮和代码停止入口，停止时释放摄像头。

这是“当前视野有多少目标”，不是跨帧累计通过计数。同一物体不会在界面上累加，但当前版本也没有轨迹 ID；后续累计计数必须增加 Tracking、越线规则和去重。人员检测只显示当前人数，不读取门磁或授权状态，也不判断未授权进入。

硬件上先安装与设备匹配的 PyTorch/CUDA，再安装 `requirements-camera.txt`。该 requirements 故意不包含 `torch`，避免覆盖 Jetson 或其他板卡的厂商版本。YOLO26必须使用兼容版本的 Ultralytics；Orin首次联调时旧版 `8.3.58` 虽能加载权重，但CPU/GPU均无法正确检测，离线升级到本项目固定的 `8.4.123` 并重启Jupyter内核后恢复正常。解压交付包后，从 AutoDine根目录启动 JupyterLab并打开：

```text
edge/smart_storage_vision/notebooks/camera_realtime_yolo26.ipynb
```

USB 摄像头默认使用编号 `0`，打不开时再确认 `/dev/video*` 并尝试 `1`、`2`；RTSP 地址只在本地单元格临时填写，不提交凭据。

### 接口与隐私风险

- JupyterLab必须启用token/密码，只允许可信局域网、VPN或SSH隧道访问；不要把8888端口无认证暴露到公网。
- Notebook只在内存中刷新JPEG，不主动保存摄像头画面；截图、录屏和带输出的Notebook可能包含人员隐私，提交前必须清空输出并检查文件。
- RTSP用户名、密码和内网地址不得写进Notebook、README、事件JSON或Git；使用本地环境变量/未跟踪配置。
- `publish_to_core` 当前通过调用方提供的HTTP地址直接发送事件，没有认证、签名或TLS配置，只适合受信任的本地原型网络。跨主机/生产部署前应由C/D共同提供认证网关或mTLS，限制来源、速率和事件大小。
- A只发布计数、品质和安全观察，不发送原始图像，不拥有库存预留或门锁控制权限。Core负责业务真值与事件校验，HardwareHub负责设备控制。
- Ultralytics权重/代码和FRUIT-16K数据分别受其上游许可约束；公开或商业部署前需完成依赖与数据许可审查。

六类检测模型使用 Fruits-detection 的现成框标注训练，独立测试集含 457 张图片、1636 个框，Precision=0.529、Recall=0.416、mAP50=0.418、mAP50-95=0.279。该结果可作为技术原型，但召回率仍不足，现场漏检必须继续评估。

六个检测类别均已在 `data/seed/catalog.json` 建立 `pcs` 原料条目，A 生成的 `vision.storage.detected`、`inventory.detected` 与 `quality.abnormal` 事件可由当前 Core 识别。新增目录项只建立库存主数据，不表示这些水果已经进入菜单 BOM。

品质模型使用去除完全重复文件后的 12,531/2,764/2,625 训练、验证、测试划分，共 26 个 fresh/rotten 类。独立测试 Top-1=99.314%、Top-5=99.962%；尽管没有完全相同文件跨划分，公开数据仍可能包含近重复帧和背景捷径，不能把高指标外推为摄像头现场准确率。模型权重位于本地忽略目录，不提交 Git。

### CountGD++ 当前边界

- WSL2 Ubuntu 已识别 RTX 5080 Laptop GPU，compute capability 为 12.0。
- `nvidia/cuda:12.8.1-base-ubuntu22.04` 已在 Docker 内识别 GPU，Stage 2 通过。
- `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel` 已 pull 完成，digest 为 `sha256:3d614dfd422b7e43647491cbf07d6acc516c032fc49c594a94afdebd52552fb9`；pull成功只证明镜像完整存在，不等于Stage 3通过。
- 第一次 pull 经旧第三方 registry mirrors 下载时发生 layer digest 不一致；问题 mirrors 已移除并备份原 Docker 配置，第二次官方源 pull 按用户要求停止，交由用户在 WSL2 手动完成。
- 按用户要求，Stage 3容器内 torch/CUDA/sm_120验证及后续工作暂不执行。CountGD++尚未编译GroundingDINO、安装Detectron2、加载checkpoint或真实推理。`CountGDPlusPlusBackend`仍应明确报不可用，不能返回Mock。
- 详细阶段记录与恢复命令见 `docs/COUNTGD_DEPLOYMENT.md`。

## Windows 本地运行

在仓库根目录打开 PowerShell。真实 YOLO 水果计数：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_yolo_inventory_demo.py <水果图片> --detector edge\smart_storage_vision\models\fruit_detector_yolo26n_v1_best.pt
```

如果没有 `--quality-model`，所有检测目标会明确进入 `review`，不会假装已经完成缺陷检测。训练好质量模型后运行：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_yolo_inventory_demo.py <水果图片> --detector edge\smart_storage_vision\models\fruit_detector_yolo26n_v1_best.pt --quality-model edge\smart_storage_vision\models\fruit_quality_yolo26_v2_best.pt
```

真实 YOLO 防盗演示：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_security_demo.py <图片> --model edge\smart_storage_vision\models\person_yolo26n_coco.pt --door-open --roi 0.2,0.1,0.8,1.0
```

`--door-open` 和 `--authorized` 是演示状态，不是传感器读数。接入 D 模块后应由门磁/门锁事件和授权服务提供。

Mock 协议回归与测试：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_demo.py
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' -m pytest -q edge\smart_storage_vision\tests
```

`run_demo.py` 明确使用 `MockBackend`，只验证计数汇总、缺陷汇总、库存减少规则和 ADP/Core 接口。

## 主要代码

- `src/smart_storage_vision/backends.py`：Mock、CountGD++ 边界、真实 YOLO 水果检测/质量分类后端。
- `src/smart_storage_vision/pipeline.py`：计数、显式数量标定、质量汇总、库存减少判断、ADP 事件。
- `src/smart_storage_vision/security.py`：真实 YOLO 人体检测与未授权进入规则。
- `train_fruit_detector_yolo.py`：六类水果检测训练与独立测试入口。
- `train_quality_yolo.py`：去重水果质量数据的 YOLO 分类训练与独立测试入口。
- `data/datasets.yaml`：数据集来源、许可与当前状态。

详细工作记录和下一步安排见 `docs/A-智慧仓储视觉-工作档案.md` 与 `docs/A-智慧仓储视觉-下一步计划.md`。
