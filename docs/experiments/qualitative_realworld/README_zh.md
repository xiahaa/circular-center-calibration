# 真实场景定性实验

该实验分别从相机图像和高强度 LiDAR 点中提取圆形标定板，估计 LiDAR 到相机的外参，
并生成点云与圆心投影结果，对应论文 Figure 11。

## 1. 下载数据

下载
[`circular-center-calibration-data.zip`](https://drive.google.com/file/d/15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC/view?usp=sharing)，
其中已经包含两套真实场景数据。也可以在仓库根目录直接运行：

```bash
mkdir -p data/downloads
curl --fail --location \
  'https://drive.usercontent.google.com/download?id=15KnnDbFxnf1pKnCbVjomoJlxTrxz39tC&export=download&confirm=t' \
  --output data/downloads/circular-center-calibration-data.zip
```

解压后，将其中的两个数据集目录放到仓库的 `data/` 下：

```bash
unzip -q data/downloads/circular-center-calibration-data.zip -d data/downloads
mv data/downloads/circular-center-calibration-data/orbbec_livox_lab data/
mv data/downloads/circular-center-calibration-data/orbbec_livox_office data/
```

## 2. 检查数据目录

解压后的目录结构如下：

```text
data/
├── orbbec_livox_office/
│   ├── dataset.yaml
│   ├── camera_info.yaml
│   ├── img/*.png             # 37 张图像
│   └── pcd/*.pcd             # 37 份点云
└── orbbec_livox_lab/
    ├── dataset.yaml
    ├── camera_info.yaml
    ├── img/*.png             # 67 张图像
    └── pcd/*.pcd             # 67 份点云
```

每对图像和点云使用相同的数字文件名。使用以下命令检查数量：

```bash
find data/orbbec_livox_office/img -name '*.png' -type f | wc -l
find data/orbbec_livox_office/pcd -name '*.pcd' -type f | wc -l
find data/orbbec_livox_lab/img -name '*.png' -type f | wc -l
find data/orbbec_livox_lab/pcd -name '*.pcd' -type f | wc -l
```

四行输出应依次为 `37`、`37`、`67` 和 `67`。

## 3. 运行实验

先完成根目录 README 中的 [Installation](../../../README.md#installation)，然后对每套
数据运行前 10 帧：

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/default.yaml \
  --max-frames 10 \
  --output-dir outputs/qualitative_realworld_preview
```

运行全部 104 对数据：

```bash
circular-center-run \
  configs/experiments/qualitative_realworld/default.yaml \
  --output-dir outputs/qualitative_realworld
```

默认配置依次使用 `Refined Center`、`CGA-RANSAC` 和 `Quasi-RANSAC`。如需更换方法或
数据集，修改 `configs/experiments/qualitative_realworld/default.yaml`。

每套数据中，成功提取的全部 `Refined Center` 二维圆心和 `CGA-RANSAC` 三维圆心共同
参与一次联合标定。`Quasi-RANSAC` 对二维圆心的两个候选结果进行消歧，最终使用全部
共识内点执行迭代 PnP 优化。

## 4. 输出文件

```text
outputs/qualitative_realworld/
├── summary.json
├── orbbec_livox_office/
│   ├── 00001.png
│   └── ...
└── orbbec_livox_lab/
    ├── 00001.png
    └── ...
```

`summary.json` 逐帧记录二维候选圆心、最终圆心、三维圆心和半径、圆拟合内点、标定内点、
外参以及重投影误差。

## 5. 实验结果

完整运行结果如下：

| 数据集 | 输入帧数 | 成功提取圆心 | 标定内点 | 平均重投影误差 |
| --- | ---: | ---: | ---: | ---: |
| `orbbec_livox_lab` | 67 | 60 | 57 | 3.094 px |
| `orbbec_livox_office` | 37 | 27 | 27 | 2.734 px |

图中投影完整 LiDAR 点云，并按强度由蓝色（低）到红色（高）着色。黄色曲线是图像
椭圆，绿色圆点是最终选择的二维圆心，青色十字是投影后的三维圆心。

### Lab

![Lab 投影结果](assets/lab-00026.png)

### Office

![Office 投影结果](assets/office-00033.png)
