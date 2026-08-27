# 二维投影圆心精度实验：配置与运行

[English](README.md)

以下命令均在仓库根目录执行，用于生成论文 Figure 8 的误差分布，以及
`Ellipse Center`、`Mass Center` 和 `Refined Center` 的逐次结果。

## 1. 准备环境

按照仓库根目录 [README Installation](../../../README.md#installation) 完成环境安装。
本实验不需要额外构建 PCL。

## 2. 快速检查

```bash
circular-center-run \
  configs/experiments/synthetic_2d_accuracy/ci.yaml \
  --output-dir outputs/synthetic_2d_accuracy_ci
```

该 profile 只运行 2 次，用于检查数据生成、方法调用、单应性判别、统计和绘图链路，
并与完整配置使用同一执行链路。

## 3. 运行完整实验

```bash
circular-center-run \
  configs/experiments/synthetic_2d_accuracy/paper.yaml \
  --output-dir outputs/synthetic_2d_accuracy
```

`paper` profile 共运行 1000 次。每次投影两个半径相同、共面且不同心的圆；相机内参为
`(fx, fy, cx, cy) = (600, 600, 640, 480)`；轮廓加入 `sigma = 1 px` 的噪声并拟合
椭圆；第二个圆用于单应性判别。

复现 Figure 8 时直接使用现有 `paper` 配置，不要修改
`experiments/synthetic_2d_accuracy/protocol.yaml` 或
`experiments/synthetic_2d_accuracy/profiles/paper.yaml`。

## 4. 配置方法

外层配置只选择参与实验的方法：

```yaml
schema_version: 1
experiment: synthetic_2d_accuracy
datasets: [paper]
methods:
  2d: [Ellipse Center, Mass Center, Refined Center]
  3d: null
  ambiguity: Homography Validation
```

若要比较新的二维方法，先在 `configs/methods/2d/` 注册，再将论文方法名加入
`methods.2d`。返回两个候选点的方法还需要选择兼容的 ambiguity 方法。Figure 8
专用的数据生成和搜索参数继续由本实验目录管理。

## 5. 输出

```text
outputs/synthetic_2d_accuracy/
├── summary.json
└── paper/
    ├── validation_error_distribution.png
    ├── raw_results.csv
    ├── method_summary.csv
    └── paper_comparison.csv
```

`raw_results.csv` 应包含 1 行表头和 3000 条方法记录：

```bash
wc -l outputs/synthetic_2d_accuracy/paper/raw_results.csv
```

`paper_comparison.csv` 会将均值、标准差、中位数、p95 和最大误差与 Figure 8 的归档
逐次数据进行比较。

## 6. 实验结果

一次完整运行得到下图和数值。

![论文 Figure 8 的实验结果](assets/reference-run.png)

| 方法 | 均值（px） | 中位数（px） | p95（px） | 论文均值（px） |
| --- | ---: | ---: | ---: | ---: |
| Refined Center | 0.9415 | 0.4427 | 1.4534 | 1.2672 |
| Ellipse Center | 16.1364 | 15.3862 | 29.9091 | 16.1364 |
| Mass Center | 16.1165 | 15.2437 | 29.3413 | 16.1164 |

两个 baseline 与归档统计达到数值精度一致。`Refined Center` 的中位数完全一致，p95
相差约 `1.8%`；均值低约 `25.7%`，原因是归档 CSV 中少量退化候选搜索形成的长尾与
后期发布的 CCFinder 源码不同。论文的主要结论得到复现：改进圆心的误差远小于两个
baseline，分布也明显更集中。所有差异均记录在 `paper_comparison.csv` 中。

## 常见问题

- 出现 `Refined Center returned multiple candidates ...`：在 `methods.ambiguity` 中选择
  `Homography Validation`。
- 出现 `OpenCV is required`：确认已激活按照根目录 README 创建的环境。
- CI profile 运行 2 次；paper profile 运行 1000 次。
