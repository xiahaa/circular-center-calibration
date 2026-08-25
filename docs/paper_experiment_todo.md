# 论文实验实现清单

## 目标与约定

复现 `paper/sections/experiments.tex` 中的实验图表。方法实现及默认 YAML 统一放在
`src/circular_center/methods/` 和 `configs/methods/`；实验协议、数据生成、参数扫描、
指标和绘图放在 `experiments/<name>/`。最外层实验 YAML 放在
`configs/experiments/<name>/`，只选择 profile 和方法；论文实验使用 `paper.yaml` 和
`ci.yaml`，非论文实验可使用 `default.yaml`。

每个实验应提供：

- `paper` profile：保留论文实验规模，用于正式生成图表；
- `ci` profile：只运行少量样本，验证完整调用链；
- `docs/experiments/<name>/README.md` 和 `README_zh.md`；
- 逐次结果、汇总 JSON，以及论文所需的图片或 CSV/TeX 表格。

文档约定：无后缀的 `README.md` 为英文版，`README_zh.md` 为中文版。实验文档只说明
如何配置、运行和核对结果；安装步骤统一引用仓库根目录的 `README.md#installation`。

## 框架与方法状态

- [x] 同一实验可选择同一类型的多个方法。
- [x] 不使用的 `2d`、`3d` 或 `ambiguity` 阶段可设为 `null`。
- [x] 实验可在不修改中央默认值的情况下应用论文协议参数。
- [x] `PCL SACMODEL`：真实 PCL `SACMODEL_CIRCLE3D + SAC_RANSAC` C++ baseline。
- [x] PnP-RANSAC 统一评估工具：供 2D 圆心位姿实验复用。

现有插件：

- 2D：`Ellipse Center`、`Mass Center`、`Refined Center`；
- 3D：`CGA`、`CGA-RANSAC`、`PCL SACMODEL`；
- ambiguity：`Homography Validation`、`Quasi-RANSAC`。

## 已完成实验

### `synthetic_3d_accuracy`

- [x] 对应论文 Figure 5：A-D 四种三维采样场景，每种 1000 次；直接 `CGA`
  对比 `PCL SACMODEL`。
- [x] 对应论文 Table I：`10%–50%` 五档离群比例，每档 100 次；
  `CGA-RANSAC` 对比 `PCL SACMODEL`。
- [x] 提供 `paper` 和 `ci` profile，以及多方法配置。
- [x] 生成 `3d-monte.pdf/png`、`raw_results.csv`、`outlier_summary.csv`、
  `outlier_table.tex`、`paper_comparison.csv` 和 `summary.json`。
- [x] 完整运行产生 9000 条记录；Python、C++/PCL 和 lint 回归通过。
- [x] 使用文档：
  [English](experiments/synthetic_3d_accuracy/README.md) / [中文](experiments/synthetic_3d_accuracy/README_zh.md)。

数据说明：原始离群点实验的 100 份基础点云未公开，当前实现确定性生成统计等价数据，
并在 `paper_comparison.csv` 中记录与论文表格的差异。

### `synthetic_2d_accuracy`

- [x] 对应论文 Figure 8：两个共面不同心圆、`sigma=1 px` 轮廓噪声，共运行
  1000 次。
- [x] 通过中央插件比较 `Ellipse Center`、`Mass Center` 和 `Refined Center`，并用
  `Homography Validation` 选择双候选。
- [x] 提供 `paper` 和 `ci` profile，生成 `validation_error_distribution.png`、
  `raw_results.csv`、`method_summary.csv`、`paper_comparison.csv` 和 `summary.json`。
- [x] 完整运行产生 3000 条成功记录；两个 baseline 与论文归档统计达到数值精度
  一致，`Refined Center` 的中位数一致、p95 相差约 `1.8%`。
- [x] 使用文档：
  [English](experiments/synthetic_2d_accuracy/README.md) / [中文](experiments/synthetic_2d_accuracy/README_zh.md)。

数据说明：归档逐次 CSV 与后期发布的 CCFinder 源码在少量退化候选搜索上存在差异，
`Refined Center` 的长尾和均值差异记录在 `paper_comparison.csv`。

### `synthetic_2d_pose`

- [x] 对应论文 Figure 9：每个 trial 生成 20 对圆心对应关系，比较
  `Ellipse Center`、`Mass Center`、`Refined Center` 和图中标为 `RANSAC Center`
  的 `Quasi-RANSAC`。
- [x] 使用统一 PnP-RANSAC 工具统计重投影、旋转和平移误差。
- [x] 提供 `paper` 和 `ci` profile，生成 `error_bar_comparison.png`、
  `raw_results.csv`、`method_summary.csv`、`paper_comparison.csv` 和 `summary.json`。
- [x] 完整运行 50 个唯一 trial，产生 200 条成功记录；两个 baseline 与归档均值差异
  小于 `0.3%`，两种改进方法均明显优于 baseline。
- [x] 使用文档：
  [English](experiments/synthetic_2d_pose/README.md) / [中文](experiments/synthetic_2d_pose/README_zh.md)。

数据说明：发布的 99 行 Figure 9 数据只包含 50 个唯一 trial，且 NPZ 中间数据和旧版未
设种子的 RANSAC 状态未发布。当前实现去除重复权重并确定性重建；两种改进方法的相对
排序与归档图相反，差异完整记录在 `paper_comparison.csv`。

### `quasi_ransac_evaluation`

- [x] 对应论文 Table II：扫描 `n={8,12,20}`、离群率
  `{0,0.1,0.2,0.3}` 和置信度 `{0.95,0.99,0.999}`，每格 1000 次。
- [x] 按论文阈值统计位姿成功率，并记录理论置信度、实际迭代数和耗时。
- [x] 提供 `paper` 和 `ci` profile，生成 `raw_results.csv`、
  `full_summary.csv`、`quasi_ransac_table.tex`、`paper_comparison.csv` 和
  `summary.json`。
- [x] 完整运行产生 36,000 条记录；Table II 展示的 0.99 档成功率与论文绝对差异均
  不超过 `0.02`，迭代数趋势一致。
- [x] 使用文档：
  [English](experiments/quasi_ransac_evaluation/README.md) / [中文](experiments/quasi_ransac_evaluation/README_zh.md)。

数据说明：论文未发布逐次数据，当前实现按文中分布确定性重建。本机为
Core i9-14900K，论文环境为 Xeon Gold 5218，CPU 信息随结果一并记录。

### `synthetic_3d_stress`

- [x] 对应论文 Figure 6：扫描点数 `5-128`、可见圆弧 `45-360 deg` 和四种角度
  分布；每格 300 次。
- [x] 使用相同样本比较 `CGA` 与 `PCL SACMODEL`，按圆心误差 `<1 cm` 统计成功率。
- [x] 提供 `paper` 和 `ci` profile，生成 `stress_heatmap_nominal_noise.pdf/png`、
  `raw_results.csv`、`cell_summary.csv`、`paper_comparison.csv` 和 `summary.json`。
- [x] 完整运行产生 100,800 条记录；主要概率跃迁位置与论文一致，测试和 lint 通过。
- [x] 使用文档：
  [English](experiments/synthetic_3d_stress/README.md) / [中文](experiments/synthetic_3d_stress/README_zh.md)。

数据说明：论文未发布生成器、带内抖动、拟合阈值和逐次数据。当前实现严格按正文分布确定性
重建，并用从 PDF 热图近似解码的概率作比较；CGA 单圆弧/带状平均绝对差约为
`0.020/0.029`，PCL 约为 `0.088/0.092`。

### `synthetic_3d_target_tolerance`

- [x] 对应论文 Figure 7：法向翘曲和椭圆轴偏差扫描
  `{0,0.0025,0.005,0.01,0.02,0.05}`。
- [x] 比较 `PCL SACMODEL`、`CGA` 和 `CGA-RANSAC`，绘制 `1 cm` 边界。
- [x] 提供 `paper` 和 `ci` profile，生成 `target_tolerance.pdf/png`、逐次 CSV、
  汇总 CSV、论文比较 CSV 和汇总 JSON。
- [x] 完整运行产生 10,800 条记录；直接 CGA 曲线与论文矢量图的平均绝对差小于
  `0.07 mm`，测试和 lint 通过。
- [x] 使用文档：
  [English](experiments/synthetic_3d_target_tolerance/README.md) / [中文](experiments/synthetic_3d_target_tolerance/README_zh.md)。

数据说明：论文只给出变形范围和最终曲线。当前 64 点、180 度圆弧、二次法向翘曲和对称
椭圆模型由 CGA 曲线恢复；鲁棒方法的原始阈值未发布，PCL 和 CGA-RANSAC 在最大变形
处比图中参考值低约 `3.4 mm`。

### `benchmark_3d_runtime`

- [x] 对应论文 Table III：`n=64`，比较 `CGA`、`CGA-RANSAC` 和
  `PCL SACMODEL`。
- [x] 每种方法精确计时 1000 次，分布到五个顺序执行的隔离进程；统计 p50、p95 和
  进程 Peak RSS 中位数。
- [x] 提供 `paper` 和 `ci` profile，生成逐次 latency CSV、进程 RSS CSV、汇总
  CSV/JSON、环境 JSON 和 TeX 表。
- [x] 完整运行产生 3000 条计时记录；输出包含 CPU、系统、Python、NumPy、PCL 和
  线程限制信息，测试和 lint 通过。
- [x] 使用文档：
  [English](experiments/benchmark_3d_runtime/README.md) / [中文](experiments/benchmark_3d_runtime/README_zh.md)。

环境说明：论文使用 Xeon Gold 5218，本机为 Core i9-14900K，Python/PCL 构建也不同；
完整环境信息保存在 `environment.json`。

## 本轮实现状态

除下节明确排除的两个实验外，论文 Figure 5-9、Table I-III 对应的实验代码、
`paper/ci` 配置、完整实验结果和中英文使用文档均已完成。当前没有待实现实验。

## 本轮不实现

- `gazebo_calibration`：对应 Figure 10 和 Table IV；依赖 ROS Noetic、Gazebo 11、
  simulator seeds 及 `velo2cam` 对比流程，本轮明确跳过。
- `qualitative_realworld`：对应 Figure 11 的真实数据投影结果；当前仅保留已有基础代码，
  不扩展为论文完整实验，本轮明确跳过。当前数据下载、运行和结果文档：
  [English](experiments/qualitative_realworld/README.md) /
  [中文](experiments/qualitative_realworld/README_zh.md)。

## 正确性约束

- 2D 实验必须生成真实圆投影轮廓，不能用 oracle 候选或人为中点代替基线。
- 同一对比中的方法必须接收完全相同的样本和匹配的 RANSAC 预算。
- 方法构造默认值放在中央方法 YAML；论文协议覆盖和扫描参数放在对应实验目录。
- 实验实现不得依赖后续不会保留的外部参考项目。
- 论文没有给出参数或原始数据时，记录参数恢复方式和数据来源。
- runtime 结果必须记录环境、硬件信息和隔离方式。

## 非实验资源

`3D.pdf`、`2D-points.pdf`、`schme.pdf`、`project.pdf`、作者照片和设备照片属于
说明图或静态资源，不需要通过实验生成。
