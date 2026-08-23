# A：智慧仓储视觉技术原型

本目录只负责 A 模块：仓储摄像头视觉推理、原料计数与质量观察、防盗判断，以及向 AutoDineCore 发布 ADP 1.0 事件。Core 负责库存/BOM/菜单等业务真值，D 模块负责硬件控制，F 模块负责最终界面。

## 当前完成度

| 功能 | 当前实现 | 真实性说明 |
| --- | --- | --- |
| 水果计数 | Ultralytics YOLO11n 检测框计数 | 已用 RTX 5080/CUDA 和真实水果图片运行：香蕉 1 框、橙子 7 框；不是 Mock |
| 缺陷检测 | YOLO11n-cls 水果实例质量分类 | FRUIT-16K 已完成 10 轮本地训练与独立测试；真实图片已输出 `good/defective/review`，不是 Mock |
| 人员检测 | Ultralytics YOLO11n person 类 | 已用 RTX 5080/CUDA 和真实图片运行，检测 4 人；不是 Mock |
| 未授权进门 | 人在门区 + 门已开 + 无授权 | 人体检测是真实模型；演示中的门状态与授权是命令行模拟 |
| Core 告警 | `vision.storage.security` → Core 告警 → `alarm.updated` | 已通过集成测试 |
| CountGD++ | WSL2/Docker 分阶段兼容验证 | Stage 1/2 已通过；Stage 3 的指定 PyTorch 2.7.1/cu128 镜像待用户手动 pull，尚未编译、加载权重或推理；运行后端继续使用真实 YOLO |
| Mock 流程 | 固定检测框验证事件与 Core 协议 | 只用于可重复测试，不是模型交付结果 |
| 摄像头/Zeuslap | 图片输入、本地 JSON 状态 | 尚未接 RTSP/门磁；Zeuslap 目前只作为普通 HDMI 显示器 |

### “缺陷检测”的准确范围

本版缺陷模型是水果实例级分类：YOLO 检测模型先框出每个水果，第二个 YOLO 分类模型再根据 FRUIT-16K 的 `F_*`（fresh）与 `S_*`（spoiled）标签把该水果判为 `good` 或 `defective`。因此它能回答“这个水果是否腐坏”，并按实例计入 `quality.abnormal`。

它目前不能在水果表面再框出病斑、霉斑或破损的具体位置。原因是 FRUIT-16K 只提供整果鲜/腐类别，没有缺陷区域的边界框或分割掩码。后续需要增加带缺陷框/掩码的公开数据与现场标注，训练 YOLO detection/segmentation 缺陷定位模型；README 不会把实例分类结果冒充缺陷区域定位结果。

本地训练数据为 11,200/2,400/2,400 的训练、验证、测试划分，随机种子为 42。独立测试集 top-1/top-5 均为 100%，但这只证明同分布公开数据表现，不能外推为现场摄像头 100% 准确。模型权重位于本地忽略目录，不提交 Git。

### CountGD++ 当前边界

- WSL2 Ubuntu 已识别 RTX 5080 Laptop GPU，compute capability 为 12.0。
- `nvidia/cuda:12.8.1-base-ubuntu22.04` 已在 Docker 内识别 GPU，Stage 2 通过。
- `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel` 尚未 pull 完成，因此 Stage 3 的 torch/cu128/sm_120/CUDA tensor 验证尚未执行。
- 第一次 pull 经旧第三方 registry mirrors 下载时发生 layer digest 不一致；问题 mirrors 已移除并备份原 Docker 配置，第二次官方源 pull 按用户要求停止，交由用户在 WSL2 手动完成。
- CountGD++ 尚未编译 GroundingDINO、安装 Detectron2、加载 checkpoint 或真实推理。`CountGDPlusPlusBackend` 仍应明确报不可用，不能返回 Mock。
- 详细阶段记录与恢复命令见 `docs/COUNTGD_DEPLOYMENT.md`。

## Windows 本地运行

在仓库根目录打开 PowerShell。真实 YOLO 水果计数：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_yolo_inventory_demo.py <水果图片> --detector yolo11n.pt
```

如果没有 `--quality-model`，所有检测目标会明确进入 `review`，不会假装已经完成缺陷检测。训练好质量模型后运行：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_yolo_inventory_demo.py <水果图片> --detector yolo11n.pt --quality-model <best.pt>
```

真实 YOLO 防盗演示：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' edge\smart_storage_vision\run_security_demo.py <图片> --model yolo11n.pt --door-open --roi 0.2,0.1,0.8,1.0
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
- `train_quality_yolo.py`：公开水果质量数据的 YOLO 分类训练入口。
- `data/datasets.yaml`：数据集来源、许可与当前状态。

详细工作记录和下一步安排见 `docs/A-智慧仓储视觉-工作档案.md` 与 `docs/A-智慧仓储视觉-下一步计划.md`。
