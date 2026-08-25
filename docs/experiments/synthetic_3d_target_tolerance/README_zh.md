# 三维标定板容差实验：配置与运行

[English](README.md)

以下命令均在仓库根目录执行，用于生成论文 Figure 7 对应的曲线和逐次结果。

## 1. 准备环境

按照仓库根目录 [README Installation](../../../README.md#installation) 完成安装，并构建
PCL baseline。

## 2. 快速检查

```bash
circular-center-run \
  configs/experiments/synthetic_3d_target_tolerance/ci.yaml \
  --output-dir outputs/synthetic_3d_target_tolerance_ci
```

CI profile 只使用变形量 `0` 和 `0.05`，每个设置运行 2 次，用于检查三个三维插件、
汇总、比较和绘图链路。

## 3. 运行完整实验

```bash
circular-center-run \
  configs/experiments/synthetic_3d_target_tolerance/paper.yaml \
  --output-dir outputs/synthetic_3d_target_tolerance
```

`paper` profile 对法向翘曲和椭圆轴偏差扫描
`{0,0.0025,0.005,0.01,0.02,0.05}`，每个设置运行 300 个配对 trial。实验使用半径
`0.12 m`、180 度圆弧上的 64 个点和 `sigma=0.005r` 噪声；三个方法共生成 10,800 条
记录。

## 4. 配置方法

```yaml
schema_version: 1
experiment: synthetic_3d_target_tolerance
datasets: [paper]
methods:
  2d: null
  3d: [PCL SACMODEL, CGA, CGA-RANSAC]
  ambiguity: null
```

恢复出的变形模型和论文专用参数覆盖位于
`experiments/synthetic_3d_target_tolerance/`。新增已注册三维方法时，只需将名字加入
`methods.3d`。

## 5. 输出

```text
outputs/synthetic_3d_target_tolerance/
├── summary.json
└── paper/
    ├── target_tolerance.pdf
    ├── target_tolerance.png
    ├── raw_results.csv
    ├── tolerance_summary.csv
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/synthetic_3d_target_tolerance/paper/raw_results.csv \
  outputs/synthetic_3d_target_tolerance/paper/tolerance_summary.csv
```

包含表头时，预期分别为 10,801 行和 37 行。

![生成的 Figure 7 曲线](../../../outputs/synthetic_3d_target_tolerance/paper/target_tolerance.png)

## 6. 实验结果

完整实验在变形量 `0.05` 时得到以下平均圆心误差（mm）：

| 变形类型 | PCL SACMODEL | CGA | CGA-RANSAC |
| --- | ---: | ---: | ---: |
| 法向翘曲 | 5.773 | 5.347 | 5.325 |
| 轴偏差 | 11.298 | 9.786 | 10.625 |

直接 CGA 曲线与论文矢量图高度一致，平均绝对差小于 `0.07 mm`，并复现了“轴偏差比
法向翘曲影响更大”的主要结论。论文未发布原始生成器和鲁棒方法阈值；PCL 与
CGA-RANSAC 在最大变形处比图中参考值低约 `3.4 mm`。精确差异保存在
`paper_comparison.csv`。

## 常见问题

- `PCL SACMODEL ... unavailable`：按根目录 README 构建 PCL 库，或设置
  `CIRCULAR_CENTER_PCL_LIBRARY`。
- CI profile 使用缩减参数网格检查完整链路。
