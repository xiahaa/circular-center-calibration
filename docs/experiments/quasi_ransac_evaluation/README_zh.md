# Quasi-RANSAC 评估：配置与运行

[English](README.md)

以下命令均在仓库根目录执行，用于生成论文 Table II 对应的逐次结果和 TeX 表格。

## 1. 准备环境

按照仓库根目录 [README Installation](../../../README.md#installation) 完成环境安装。
本实验不需要额外构建 PCL。

## 2. 快速检查

```bash
circular-center-run \
  configs/experiments/quasi_ransac_evaluation/ci.yaml \
  --output-dir outputs/quasi_ransac_evaluation_ci
```

CI profile 包含 8 个参数单元，每格只运行 1 次，用于检查数据生成、方法调用、位姿成功
判据、CSV 汇总和 TeX 输出，并与完整配置使用同一执行链路。

## 3. 运行完整实验

```bash
circular-center-run \
  configs/experiments/quasi_ransac_evaluation/paper.yaml \
  --output-dir outputs/quasi_ransac_evaluation
```

`paper` profile 包含：

- 对应点数 `n = {8, 12, 20}`；
- 离群率 `{0, 0.1, 0.2, 0.3}`；
- 置信度 `{0.95, 0.99, 0.999}`；
- 每个参数单元 1000 次，共 36,000 次。

生成的 TeX 表使用与 Table II 一致的 `0.99` 置信度；CSV 汇总保留全部 36 个单元。
复现时直接使用现有 `paper` profile，不要修改实验协议。

## 4. 配置方法

外层配置只选择歧义消解方法，未使用的阶段设为 `null`：

```yaml
schema_version: 1
experiment: quasi_ransac_evaluation
datasets: [paper]
methods:
  2d: null
  3d: null
  ambiguity: Quasi-RANSAC
```

论文专用的候选点分布、成功判据和方法参数覆盖位于
`experiments/quasi_ransac_evaluation/`。

## 5. 输出

```text
outputs/quasi_ransac_evaluation/
├── summary.json
└── paper/
    ├── raw_results.csv
    ├── full_summary.csv
    ├── quasi_ransac_table.tex
    └── paper_comparison.csv
```

用以下命令检查逐次记录和汇总行数：

```bash
wc -l \
  outputs/quasi_ransac_evaluation/paper/raw_results.csv \
  outputs/quasi_ransac_evaluation/paper/full_summary.csv
```

包含表头时，预期分别为 36,001 行和 37 行。

## 6. 实验结果

一次完整运行得到下表结果。

| 对应点数 | 离群率 | 成功率 | 平均迭代数 | 时间（ms） |
| ---: | ---: | ---: | ---: | ---: |
| 8 | 0% | 0.984 | 72.0 | 3.83 |
| 8 | 10% | 0.947 | 123.5 | 6.45 |
| 8 | 20% | 0.879 | 228.4 | 11.77 |
| 8 | 30% | 0.858 | 229.0 | 11.79 |
| 12 | 0% | 0.997 | 72.0 | 3.85 |
| 12 | 10% | 0.992 | 102.9 | 5.41 |
| 12 | 20% | 0.987 | 150.4 | 7.81 |
| 12 | 30% | 0.928 | 367.0 | 18.74 |
| 20 | 0% | 1.000 | 72.0 | 3.90 |
| 20 | 10% | 1.000 | 109.7 | 5.84 |
| 20 | 20% | 0.998 | 176.9 | 9.24 |
| 20 | 30% | 0.992 | 302.9 | 15.61 |

在 `0.99` 置信度下，所有成功率与论文归档表的绝对差异均不超过 `0.02`，平均迭代数
也符合相同的规划上限。时间取决于硬件：本次 Intel Core i9-14900K 运行约比论文 Xeon
环境快 4 倍。精确差异保存在 `paper_comparison.csv` 中。

## 常见问题

- 正式配置会执行 36,000 次位姿拟合；CI profile 将参数网格缩减为 8 个单元。
- 出现 `OpenCV is required`：确认已激活按照根目录 README 创建的环境。
- `Time (ms)` 随 CPU 变化；成功率和迭代数由实验协议决定。
