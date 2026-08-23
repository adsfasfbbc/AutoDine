# A：智慧仓储视觉下一步计划

## 当前执行顺序

1. 先交付真实 YOLO 版本：水果检测计数、质量分类、防盗、Core 事件和 Windows 运行说明。
2. YOLO 版本通过测试后，再尝试 CountGD++ 的 WSL2/Docker/CUDA 兼容性验证。
3. CountGD++ 若失败，保存原始错误、分析原因并写入 README；运行时继续使用真实 YOLO，Mock 只做测试。

## YOLO 版本下一阶段

1. 用现场固定机位采集水果/食物图片，按拍摄批次划分训练、验证、测试集，避免相邻帧泄漏。
2. 为每个原料定义“一个检测目标对应多少克/毫升/个”的标定；不能从框大小猜重量。
3. 扩展自定义 YOLO 检测数据，使柠檬、番茄、草莓等非 COCO 类别也可定位并逐个计数。
4. 把 FRUIT-16K 预训练的质量分类器用现场样本微调；低置信度结果进入 `review`，不自动报废。
5. 建议验收门槛：计数 MAE ≤ 1 个/画面，质量分类宏平均 F1 ≥ 0.85，并单独报告每类结果。

## 硬件与防盗联调

1. 从 D 模块取得 RTSP、门磁/门锁、设备 ID 和授权事件格式；凭据只用环境变量或本地配置，不提交 Git。
2. 配置归一化门区 ROI，并用 YOLO track 的轨迹 ID 判断跨门线，避免同一人在多帧重复报警。
3. 用 D/Core 的真实门状态与授权窗口替代演示参数 `--door-open`、`--authorized`。
4. Zeuslap 若是普通显示器，使用 HDMI 展示 F 模块页面；A 只提供状态/API，不虚构板卡控制协议。

## CountGD++ 验证

1. 用户先在 WSL2 Ubuntu 手动完成 `docker pull pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel`，保留成功 digest；当前不要 prune。
2. 从 Stage 3 继续，验证 torch 2.7.1、torchvision、CUDA 12.8、capability 12.0、`sm_120` arch list 与 CUDA tensor 运算。
3. 确认镜像内 `nvcc` 为 CUDA 12.8，并固定 GCC/G++；随后才创建 Docker 专用 requirements，禁止 torch/torchvision 被官方旧 requirements 降级。
4. 固定 CountGD++ 官方源码提交，先编译并运行 GroundingDINO CUDA ops 测试，再安装并 import Detectron2。
5. 下载 BERT 与约 1.25 GB CountGD++ checkpoint，记录来源、版本与哈希，完成真实水果图片最小推理。
6. 推理成功后实现 A 后端适配：CountGD++ 返回水果实例框与计数；已有 YOLO 缺陷分类器处理每个框，YOLO 人员模型继续负责防盗；输出进入 `SmartStoragePipeline → ADP → Core`。
7. 对 OmniCount 水果子集和现场图片记录 MAE、延迟、显存、失败样例；若失败，按 CUDA 架构、PyTorch ABI、Detectron2/自定义算子、权重加载分类并保留完整日志。

CountGD++ 不可用时，运行后端保持真实 YOLO，不回落到 Mock。Mock 只用于协议和业务规则回归。

## Git 与组员协作

每次工作先 `git fetch origin`，确认最新远端；只追加自己的 A 提交。普通 push 被拒绝时停止并报告，绝不 force push，绝不改写、删除、压缩、覆盖或重排组员在远端的提交。
