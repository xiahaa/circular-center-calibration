# 三维压力测试：配置与运行

[English](README.md)

以下命令均在仓库根目录执行，用于生成论文 Figure 6 对应的热图和逐次结果。

## 1. 准备环境

按照仓库根目录 [README Installation](../../../README.md#installation) 完成安装，并构建
PCL baseline。

## 2. 快速检查

```bash
circular-center-run \
  configs/experiments/synthetic_3d_stress/ci.yaml \
  --output-dir outputs/synthetic_3d_stress_ci
```

CI profile 在缩减后的 `2 x 2` 网格上运行四种角度分布，每格 2 次，用于检查数据生成、
两个三维插件、汇总和绘图链路。

## 3. 运行完整实验

```bash
circular-center-run \
  configs/experiments/synthetic_3d_stress/paper.yaml \
  --output-dir outputs/synthetic_3d_stress
```

`paper` profile 使用半径 `0.12 m`、噪声 `sigma=0.005r`、点数
`{5,8,16,32,64,128}`、可见圆弧 `{45,60,90,120,180,270,360}` 度、四种采样分布和
每格 300 次。`CGA` 与 `PCL SACMODEL` 接收相同样本，共生成 100,800 条记录。

## 4. 配置方法

```yaml
schema_version: 1
experiment: synthetic_3d_stress
datasets: [paper]
methods:
  2d: null
  3d: [CGA, PCL SACMODEL]
  ambiguity: null
```

论文网格、分布、成功判据和方法参数覆盖位于
`experiments/synthetic_3d_stress/`。若要在同一网格测试新方法，先注册该三维方法，再将
名字加入 `methods.3d`。

## 5. 输出

```text
outputs/synthetic_3d_stress/
├── summary.json
└── paper/
    ├── stress_heatmap_nominal_noise.pdf
    ├── stress_heatmap_nominal_noise.png
    ├── raw_results.csv
    ├── cell_summary.csv
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/synthetic_3d_stress/paper/raw_results.csv \
  outputs/synthetic_3d_stress/paper/cell_summary.csv
```

包含表头时，预期分别为 100,801 行和 337 行。

![生成的 Figure 6 热图](../../../outputs/synthetic_3d_stress/paper/stress_heatmap_nominal_noise.png)

## 6. 实验结果

完整实验复现了论文中的主要跃迁位置：CGA 在 8 点/90 度时成功率为
`0.950`，在 16 点/90 度时为 `1.000`；PCL 在 32 点/120 度时为 `1.000`。CGA 对
单圆弧和带状分布的平均成功率绝对差分别为 `0.020`、`0.029`；PCL 分别为 `0.088`、
`0.092`。

论文没有发布生成器、带内抖动、拟合阈值或逐次数据。`paper_comparison.csv` 因此将当前
确定性实现与从论文热图近似解码的参考值比较。

## 常见问题

- `PCL SACMODEL ... unavailable`：按根目录 README 构建 PCL 库，或设置
  `CIRCULAR_CENTER_PCL_LIBRARY`。
- CI profile 使用缩减的 `2 x 2` 网格；paper profile 使用完整参数网格。
