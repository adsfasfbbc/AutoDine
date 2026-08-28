# 双视频离线推理看板

本目录是A模块的独立视频文件入口，不替换 `../run_dashboard.py` 双摄像头版本。水果视频只运行六类水果检测和整果品质分类；人员进入视频只运行人员检测，避免两路重复计数。

## 输入与输出

- `--inventory-video`：水果视频，输出苹果、香蕉、葡萄、橙子、菠萝、西瓜的检测框与累计唯一轨迹数。
- 苹果、香蕉、葡萄、橙子的每个检测框继续经过现有YOLO26n-cls整果品质分类，输出 `good/defective/review`；菠萝和西瓜保持 `review`。
- `--security-video`：人员进入视频，只输出人员框和累计唯一人员轨迹数。
- 网页默认位于 `http://127.0.0.1:8091/`，两段视频默认各自循环播放。

累计逻辑不会把每帧数量直接相加。视频版使用同类别边界框IoU关联轨迹，同一水果或人员连续出现时只累计一次；检测框会显示本地轨迹ID。默认循环播放时只统计第一遍，重播不会再次累加。

该数字的严格含义是“本次视频首轮累计检测到的唯一轨迹数”，还不是带方向的累计入库量或累计进门人数。长时间遮挡、快速移动或模型漏检可能导致轨迹断裂并产生新ID；真实业务累计仍需越线方向、稳定窗口和现场阈值验收。

## Windows OpenCV环境运行

在AutoDine根目录执行，视频路径含空格或中文时必须加引号：

```powershell
& 'D:\miniconda\Miniconda3\envs\OpenCV\python.exe' `
  edge\smart_storage_vision\video_stream\run_video_dashboard.py `
  --inventory-video 'E:\videos\fruit.mp4' `
  --security-video 'E:\videos\people.mp4'
```

浏览器打开 `http://127.0.0.1:8091/`，按 `Ctrl+C` 停止。使用 `--no-loop` 时每段视频到结尾后显示 `ENDED` 并保留最后一帧。`--playback-rate 2` 表示按两倍源播放节奏调度；模型推理慢于源FPS时，实际显示速度仍受推理吞吐限制。

轨迹关联默认使用 `--tracking-iou 0.3 --tracking-max-missed 15`。现场视频出现轨迹断裂时先记录证据再调节参数，不要通过降低阈值掩盖检测漏检。

可以把待测视频临时放入本目录的 `input/`，该目录内容已被忽略；也可以直接传入仓库外绝对路径。视频不是项目源码，不要提交。

## Mock与项目边界

默认 `--mock-unauthorized-rate 0`，不会生成未授权日志。若为了界面演示显式设置非零概率，日志会标明 `[模拟]`、`mock=true`、`published_to_core=false`，不会生成ADP事件或发送Core。真实未授权判断仍需D模块门磁/门锁、Core授权窗口和A门区Tracking。

视频文件不放进Git。当前页面是A侧离线推理/联调入口，正式UI仍由F模块消费A/Core受控接口。视频画面可能包含人员隐私，不要把视频、带画面截图或导出的浏览器数据提交到仓库。
