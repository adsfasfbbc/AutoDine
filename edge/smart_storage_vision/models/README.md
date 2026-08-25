# 本地模型目录

模型权重不提交 Git。当前摄像头 Notebook 需要本目录中的三个真实权重：

| 文件 | 用途 | SHA-256 |
| --- | --- | --- |
| `fruit_detector_yolo26n_v1_best.pt` | 苹果、香蕉、葡萄、橙子、菠萝、西瓜检测框与当前视野计数 | `9A8F8E5CC87C58CF3263FC5D04615126B3B8A41F48BD94988272E4DE908C9100` |
| `fruit_quality_yolo26_v2_best.pt` | 检测框裁剪后的整果 fresh/rotten 品质分类 | `56356D4FC5A34741F67074E7173DB88F91C6450E0A7F11D8EEC8DB5C4A5E1091` |
| `person_yolo26n_coco.pt` | COCO `person` 类人员检测 | `9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF` |

品质模型包含 26 个 fresh/rotten 类。摄像头代码只允许使用与检测水果同种的两个品质标签，避免异种标签造成错误品质结论。当前菠萝和西瓜没有对应品质类别，因此输出 `review`，不会伪造 `good` 或 `defective`。

这些 `.pt` 文件包含在本地硬件交付压缩包中，但不会上传 GitHub。不得用空文件、Mock 权重或改名后的其他模型代替。
