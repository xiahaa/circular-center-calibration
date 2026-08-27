# 三维运行时间实验：配置与运行

[English](README.md)

以下命令均在仓库根目录执行，用于生成论文 Table III 对应的运行时间和进程内存结果。

## 1. 准备环境

按照仓库根目录 [README Installation](../../../README.md#installation) 完成安装，并构建
PCL baseline。

## 2. 快速检查

```bash
circular-center-run \
  configs/experiments/benchmark_3d_runtime/ci.yaml \
  --output-dir outputs/benchmark_3d_runtime_ci
```

CI profile 在一个隔离进程中对每种方法计时 9 次，用于检查 worker 启动、方法加载、
latency/RSS 收集、CSV 汇总和 TeX 输出。

## 3. 运行完整实验

先停止无关的 CPU 密集任务，再运行：

```bash
circular-center-run \
  configs/experiments/benchmark_3d_runtime/paper.yaml \
  --output-dir outputs/benchmark_3d_runtime
```

`paper` profile 对每种方法使用同一个 64 点圆，精确计时 1000 次。这些拟合被分到五个
顺序执行的隔离进程，每个进程先做 20 次不计时预热。p50/p95 使用全部 1000 个样本；
Peak RSS 是五个进程峰值的中位数。每个 worker 内的 BLAS/OpenMP 线程数固定为 1。

## 4. 配置方法

```yaml
schema_version: 1
experiment: benchmark_3d_runtime
datasets: [paper]
methods:
  2d: null
  3d: [CGA, CGA-RANSAC, PCL SACMODEL]
  ambiguity: null
```

固定输入、预热策略、RANSAC 预算和论文参考值位于
`experiments/benchmark_3d_runtime/`。若要在同一隔离策略下测试新方法，将已注册的
三维方法名字加入 `methods.3d`。

## 5. 输出

```text
outputs/benchmark_3d_runtime/
├── summary.json
└── paper/
    ├── runtime_records.csv
    ├── process_rss.csv
    ├── runtime_summary.csv
    ├── runtime_table.tex
    ├── environment.json
    └── paper_comparison.csv
```

```bash
wc -l \
  outputs/benchmark_3d_runtime/paper/runtime_records.csv \
  outputs/benchmark_3d_runtime/paper/process_rss.csv \
  outputs/benchmark_3d_runtime/paper/runtime_summary.csv
```

包含表头时，预期分别为 3001、16 和 4 行。

## 6. 实验结果

一次 Intel Core i9-14900K 运行得到：

| 方法 | p50（ms） | p95（ms） | Peak RSS（MiB） |
| --- | ---: | ---: | ---: |
| CGA | 0.110 | 0.118 | 42.5 |
| CGA-RANSAC | 2.967 | 3.017 | 44.5 |
| PCL SACMODEL | 0.118 | 0.121 | 69.4 |

论文使用 Intel Xeon Gold 5218，CGA 报告为 `1.407/1.489 ms`，CGA-RANSAC 为
`6.130/7.769 ms`，PCL 为 `0.098/0.100 ms`。PCL 延迟处于相同数量级，当前优化后的
Python CGA 路径更快。本机 PCL RSS 较高，是因为隔离进程会映射当前构建的动态 PCL
依赖。`environment.json` 保存该表对应的硬件和构建信息。

## 常见问题

- 完整运行前关闭竞争负载；CI profile 对每种方法计时 9 次。
- `PCL SACMODEL ... unavailable`：按根目录 README 构建 PCL 库，或设置
  `CIRCULAR_CENTER_PCL_LIBRARY`。
