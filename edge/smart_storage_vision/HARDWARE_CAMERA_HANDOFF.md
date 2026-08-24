# A 模块摄像头原型硬件交接

## 打开入口

解压后从 `AutoDine` 根目录启动 JupyterLab，打开：

```text
edge/smart_storage_vision/notebooks/camera_realtime_yolo26.ipynb
```

先不要直接安装或替换硬件上的 PyTorch。第一轮联调先把以下输出交给 Codex判断：

```bash
uname -m
python --version
python -c "import torch; print(torch.__version__, torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')"
python -c "import cv2; print(cv2.__version__)"
python -c "import ultralytics; print(ultralytics.__version__)"
ls -l /dev/video*
```

如果缺少依赖，再根据设备型号决定如何安装。`requirements-camera.txt` 不包含 torch，目的是避免覆盖 Jetson 或其他硬件提供的 PyTorch/CUDA；但运行 pip 前仍应先确认硬件和现有环境。

## Orin 实测记录

目标硬件实测环境：OpenCV `4.12.0`、PyTorch `2.3.0`、CUDA可用、GPU为NVIDIA Orin。USB摄像头已在JupyterLab中成功显示实时画面、人员框、`person`标签和当前人数，停止功能正常；这部分没有使用Mock。

硬件原有Ultralytics `8.3.58`与YOLO26不兼容：权重哈希和类别表正确，但CPU/GPU均漏检清晰人员，并产生低质量错误类别。升级到 `8.4.123`、重启Jupyter内核并从头运行Notebook后恢复正常。因此运行前必须确认：

```python
import ultralytics
assert ultralytics.__version__ == "8.4.123"
```

断网设备可以把官方 `ultralytics-8.4.123-py3-none-any.whl` 上传到仓库根目录，然后使用当前Jupyter内核离线安装；wheel不提交Git：

```python
import subprocess
import sys

subprocess.check_call([
    sys.executable,
    "-m",
    "pip",
    "install",
    "--user",
    "--no-deps",
    "ultralytics-8.4.123-py3-none-any.whl",
])
```

安装后必须重启内核。该方式只替换Ultralytics，不覆盖Orin上的PyTorch/CUDA。

## 接口安全

- JupyterLab必须保留token/密码认证，不把8888端口直接暴露到公网。
- 本次实测内网地址不写入仓库；RTSP凭据只保留在本地未跟踪配置中。
- Notebook不自动保存视频，但浏览器截图和带输出的Notebook可能包含人员画面；提交前清空全部输出。
- 当前摄像头原型不直接控制门锁，也不把命令行模拟授权状态冒充真实权限。

## 模型文件

交付包显式包含两个运行权重：

| 文件 | 用途 | SHA-256 |
| --- | --- | --- |
| `yolo26n.pt` | 苹果、香蕉、橙子和人员检测 | `9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF` |
| `edge/smart_storage_vision/models/fruit_quality_yolo26_best.pt` | 水果框的整果品质分类 | `16EB3FAA08AB65C269D319B1317CA7F2676DC04AB6A622038A22D21A87208D86` |

这两个权重不在 Git 中。第二个模型只输出整果品质类别，不定位病斑、霉斑或破损区域。

## 运行与停止

Notebook 默认 `CAMERA_SOURCE = 0`。USB 摄像头编号不确定时，根据 `/dev/video*` 调整为 `1`、`2`；RTSP 地址只在本地临时填写，不保存密码。

运行“启动实时推理”单元格后，画面在 Jupyter 中刷新，单元格本身会返回。停止方法：

1. 点击画面下方红色“停止摄像头”按钮；或
2. 运行最后的 `session.stop()` 单元格；或
3. 联调时告诉 Codex，由 Codex在能够访问该 JupyterLab 会话的前提下尝试停止。

停止后会释放摄像头。若后台失败，状态栏显示原始异常；最后一个单元格可再次抛出该异常供诊断。

## 当前边界

- 没有使用 Mock；检测与品质输出来自交付包中的真实 YOLO26 权重。
- 数量是当前帧/当前视野数量，不是累计通过数量。
- 人员检测只报告当前视野人数；没有门磁、门锁和授权输入，不判断未授权进入。
- 已验证Orin CUDA、USB摄像头、Jupyter画面、人员框/标签/人数和停止行为；现场水果计数与品质分类仍需用真实水果逐项记录结果，不能仅凭人员检测成功推断其准确性。
- 正式 UI 不在本阶段实现；后续由 F 模块通过 A/Core 接口展示。
