# A：双视频库存异常演示版

本目录是独立入口，不替换 `video_stream/`、摄像头看板或 Jupyter Notebook。它复用既有 YOLO26 推理代码和三份模型权重，但拥有自己的运行时、库存夹具、异常规则、网页、无界面入口和测试。CountGD++保留在项目中，本版本不调用它。

## 数据边界

真实模型输出仅包括：

- YOLO26六类水果检测与唯一轨迹累计：`apple/banana/grape/orange/pineapple/watermelon`。
- 六类水果框内的整果 `good/defective/review` 分类。
- YOLO26人员检测、当前视野人数和唯一人员轨迹累计。

演示数据包括：

- Word v1.0规定的67种原料库存初值。
- I014香蕉在10秒内从2000g连续减少到900g的库存异常场景。
- 从当前检测人员中选择一人的权限结果。

界面用“演示数据/联调演示”标识，不出现英文 `MOCK`。API和无界面输出保留 `simulated=true`、`published_to_core=false`，不能把这些结果称为真实库存或真实授权判断。

## Word v1.0库存口径

- 使用 `I001`至`I067`，基础单位仅为 `g/ml/pcs`。
- I004冰块和I005纯净水为 `UNLIMITED`，不参与异常减少判断。
- 库存可用量遵循 `physical_quantity - defective_quantity - reserved_quantity`，最低为0。
- 其他原料只显示库存演示，不进入视觉计数或品质分类。
- YOLO六类只有香蕉能明确映射到Word原料I014；其他五类没有对应ID，因此本版本不伪造映射，也不写Core。

当前主项目 `data/seed/catalog.json` 与Word v1.0的67原料/40商品规模不一致。本版本不覆盖公共Seed，使用 `fixtures/inventory_demo_v1.json` 隔离联调；正式合并必须由Core负责人确定唯一Seed版本。

## 异常减少规则

同一 `TRACKED` 原料在10秒滑动窗口中必须同时满足：

1. 至少连续4次负向变化；
2. 单次下降达到“大量下降阈值”的20%，用于确认突发性；
3. 平均下降速率达到阈值要求；
4. 最终累计下降达到 `max(初始窗口库存的20%, 单位绝对阈值)`。

绝对阈值为 `g=500`、`ml=1000`、`pcs=5`。一次事件只告警一次；库存回升后才允许形成新的事件。当前没有订单/BOM正常消耗流，因此只能判断“未解释的库存异常候选”，不能直接定性为盗窃。

## 网页运行

在AutoDine根目录使用Windows `OpenCV`环境：

```powershell
conda activate OpenCV
python edge\smart_storage_vision\video_inventory_anomaly_demo\run_dashboard.py `
  --inventory-video 'D:\AutoDineVideos\水果.mp4' `
  --security-video 'D:\AutoDineVideos\人2.mp4'
```

打开 `http://127.0.0.1:8092/`，停止按 `Ctrl+C`。默认单次播放，两段视频可长度不同：较短视频结束后保留末帧，另一段继续处理。添加 `--loop` 可循环回放，但视觉累计只记录第一轮。

默认水果阈值为0.50，人员阈值为0.25，二者互不影响：

```powershell
--fruit-confidence 0.6 --person-confidence 0.25
```

默认要求CUDA；只有明确接受CPU推理时才加 `--allow-cpu`。加入 `--disable-demo-events` 会关闭库存变化和权限演示，67种库存保持固定。

## 无界面运行

```powershell
conda activate OpenCV
python edge\smart_storage_vision\video_inventory_anomaly_demo\run_headless.py `
  --inventory-video 'D:\AutoDineVideos\水果.mp4' `
  --security-video 'D:\AutoDineVideos\人2.mp4'
```

标准输出为逐行JSON，包含启动信息、库存异常候选、权限演示事件和最终模型累计。该入口不启动网页，也不发布Core。

## 本地只读接口

- `GET /api/state`：模型计数、库存、两路状态和告警聚合。
- `GET /api/inventory`：67种演示库存快照。
- `GET /api/alerts`：库存异常和权限事件。
- `GET /api/videos/{stream_id}/frame.jpg`：最近一张标注帧。

服务默认只绑定 `127.0.0.1`，没有认证、TLS或写接口。不要直接暴露到公网；正式F页面应读取Core/WebSocket业务状态，而不是把本调试端口作为生产接口。

## 已验证与已知问题

- OpenCV环境隔离测试9项通过。
- RTX GPU设备为 `0`，两段真实MP4都能完成读取、YOLO推理和不同长度EOF处理。
- 库存异常输出：I014香蕉10秒内连续4次下降，共减少1100g，速率110g/s。
- 权限演示事件能在人员检测存在时产生，所有演示事件均未发布Core。
- 浏览器可见布局、67原料滚动区、双视频末帧、两类预警和API刷新通过，控制台无错误。
- 水果检测链路已可用于当前技术原型，现场仍需按具体摄像头、光照和目标距离校准阈值并记录漏检、误检。
- 品质仍是整果分类，不是缺陷框或分割；本次视频验收显示缺陷分类准确度不高，不能作为正式质检结论，后续需要补充现场真实缺陷样本并做独立评估。
- 当前累计依赖同类别检测框的轻量IoU轨迹关联；遮挡、快速移动、检测漏帧或水果离开后重新进入画面时，同一个水果可能获得新的轨迹ID并被重复计数。

## 后续接Core

当前 `DemoInventoryProvider` 应由Core库存快照提供器替换，读取 `store_id/location_id/ingredient_id/physical_quantity/defective_quantity/reserved_quantity/available_quantity`。Core还必须提供订单、生产任务和人工盘点造成的正常库存变化，异常引擎先抵扣这些可解释消耗。A只上报观察或异常候选；由Core负责库存真值、幂等、告警创建、确认和解除。公共AsyncAPI事件名需C/A共同确认后再修改，当前版本不擅自新增公共契约。
