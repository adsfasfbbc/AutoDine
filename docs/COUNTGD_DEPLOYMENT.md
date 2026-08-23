# CountGD++ GPU Docker 部署档案

> 状态：暂停，尚未部署成功。当前只通过 Stage 1 和 Stage 2；不要把本文件当作成功证明。

## 目标与项目边界

目标环境为 Windows NVIDIA Driver → WSL2 Ubuntu → Docker → CUDA 12.8 → PyTorch 2.7.1 cu128 → CountGD++。CountGD++ 只作为 A 模块的开放词汇检测/计数后端；已有 YOLO 缺陷分类和 YOLO 防盗继续保留。最终输出必须接入 `SmartStoragePipeline → ADP 1.0 → AutoDineCore`，Gradio 页面不是验收标准。

## 已确认环境

| 项目 | 实测值 |
| --- | --- |
| Windows NVIDIA Driver | 592.27 |
| WSL2 Ubuntu | 26.04 LTS |
| WSL2 kernel | `6.18.33.2-microsoft-standard-WSL2` |
| Docker client/server | 29.7.2 / 29.7.2 |
| GPU | NVIDIA GeForce RTX 5080 Laptop GPU |
| Compute capability | 12.0 |
| Stage 2 image | `nvidia/cuda:12.8.1-base-ubuntu22.04` |
| Stage 2 image digest | `sha256:001469ea0f3dec85a1ca929aeea3b58ae369d4c11228b10aec1f642bb6ca7a6f` |
| 目标 Stage 3 image | `pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel` |
| CountGD++ 源码提交 | `8489f836d75eb407ae778c56cff1f72cc6f8baae` |

容器内 Python、torch、torchvision、`torch.version.cuda`、nvcc、GCC/G++ 尚未验证，不能填写推测值。

## Stage 状态

1. WSL2 GPU：通过。看到 RTX 5080 与 capability 12.0。
2. Docker GPU passthrough：通过。CUDA 12.8 base 容器看到同一 GPU。
3. PyTorch 2.7.1/cu128/sm_120：未执行。目标镜像尚未 pull 成功。
4. GroundingDINO ops：未开始。
5. Detectron2 import：未开始。
6. CountGD++ 核心 import：未开始。
7. checkpoint 加载：未开始。
8. 最小图片 inference：未开始。
9. A 项目管线集成：未开始。
10. Gradio/Web UI：未开始，也不是优先项。

## 第一次 pull 失败记录

旧 Docker daemon 配置包含网易、阿里、USTC 与 dockerproxy 第三方 mirrors。前三者持续 DNS 失败，下载经其他代理分段完成后，最后一个 layer 内容 digest 与官方 manifest 不一致，Docker 正确拒绝提交：

```text
failed commit on ref "layer-sha256:1953a5f9db288f25e73653c276da7baef424fe5ff5196516e2386f0770d9f82e": commit failed: unexpected commit digest sha256:d0fbaabf68559fe825c111ccb7cca21a8a6c9c92562b6a7d9eb5341b1b1d77f0, expected sha256:1953a5f9db288f25e73653c276da7baef424fe5ff5196516e2386f0770d9f82e: failed precondition
```

问题层级是 Docker registry/mirror 内容校验，不是 GPU、CUDA、PyTorch 或 CountGD++ 模型兼容错误。

## 已采取的最小修复

- 从 `C:\Users\Dyf\.docker\daemon.json` 删除四个 `registry-mirrors`，保留 builder/buildkit 设置。
- 原配置备份为 `C:\Users\Dyf\.docker\daemon.json.autodine-backup-20260824`。
- 重启后 `docker info` 显示 mirrors 为 `[]`。
- 未运行 `docker system prune`、`docker image prune` 或 builder prune；未删除任何 layer、cache 或镜像。
- 第二次官方源 pull 已按用户要求主动终止，交由用户手动完成。

## 用户手动恢复

在 WSL2 Ubuntu 终端执行：

```bash
docker pull pytorch/pytorch:2.7.1-cuda12.8-cudnn9-devel
```

成功后保留最后的 digest 输出，不要 prune。再让 Codex 从 Stage 3 继续。

## Stage 3 下一条验证

镜像 pull 成功后运行目标容器，至少打印并断言：

```text
torch == 2.7.1
torch.version.cuda == 12.8
torch.cuda.is_available() == True
GPU == NVIDIA GeForce RTX 5080 Laptop GPU
Capability == (12, 0)
torch arch list 包含 sm_120
CUDA 矩阵运算成功
```

Stage 3 通过后才创建 Docker 专用 requirements、编译 GroundingDINO、安装 Detectron2、下载模型权重和实现 CountGD++ A 后端。官方 requirements 中的 `torch<2.6`、torchvision 与 cu121 extra index 不得覆盖基础镜像的 torch/cu128。

## Mock 与回退说明

本次 CountGD++ 部署没有使用 Mock，也没有产生模型推理结果。CountGD++ 不可用期间，A 技术原型使用已真实运行的 YOLO 计数、YOLO 缺陷分类和 YOLO 人员检测；不会自动回落到 Mock。现有 Mock 仅用于协议和业务规则回归。
