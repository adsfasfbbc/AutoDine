# 本地模型目录

模型权重不提交 Git。摄像头 Notebook 需要在本目录放置：

```text
fruit_quality_yolo26_best.pt
```

该文件是整果 fresh/spoiled 品质分类权重，SHA-256：

```text
16EB3FAA08AB65C269D319B1317CA7F2676DC04AB6A622038A22D21A87208D86
```

通用检测权重 `yolo26n.pt` 放在 AutoDine仓库根目录，SHA-256：

```text
9B09CC8BF347F0FC8A5F7657480587F25DB09B34BF33B0652110FB03A8AD4FEF
```

两个 `.pt` 文件均包含在本地硬件交付压缩包中，但不会上传 GitHub。不得用空文件、Mock权重或改名后的其他模型代替。
