# Inference-time Platt Calibration — Implementation Summary

## 背景

Temperature Scaling (T=1.5) + ECE Loss 在线下 AUC 微涨但线上 AB 全负向。根因是 temperature scaling 改变了绝对概率尺度，导致曝光池重构。

## 方案

**Inference-time Platt Scaling** — 在训练结束后，用验证集拟合 `a*logit + b` 两个参数的线性校准，冻结后作为 buffer 随 checkpoint 一起导出。推理时作为 post-processing 应用，**零影响训练目标**。

### 与 Temperature Scaling 的对比

| 维度     | Temperature Scaling | Platt Scaling                    |
| -------- | ------------------- | -------------------------------- |
| 参数量   | 1 (T)               | 2 (a, b)                         |
| 自由度   | logit/T（仅缩放）   | sigmoid(a\*logit+b)（缩放+偏移） |
| 优化目标 | 训练时 ECE loss     | 验证集上 NLL（离线拟合）         |
| 影响训练 | 有（改变梯度）      | 无（纯推理时 post-processing）   |
| 单调性   | 保持（不改变排序）  | 保持（sigmoid 是单调函数）       |

## 实现文件

### 1. tzrec/modules/calibration.py

新增 `PlattScaler` 类：

- `fit_from_logits(logits, labels)` — 牛顿法拟合 a, b
- `fit_from_problabels(probs, labels)` — 从 probs 反推 logits 再拟合
- `freeze()` — 冻结参数为 buffer
- `forward(logits)` — 应用 sigma(a\*logit + b)

### 2. tzrec/models/pepnet_dcn_ple.py

- `__init__`: 初始化 `_platt_scalers` (nn.ModuleList)
- `predict()`: 在 TemperatureScaler 之后、sigmoid 之前应用 Platt
- FX tracing 保护：`not is_fx_tracing()` 避免 Proxy 问题

### 3. proto/model.proto

新增 field 25: `platt_calibration_enabled: bool = false`

### 4. tools/platt_calibrate.py

离线拟合工具：

```bash
python tools/platt_calibrate.py \
  --config data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config \
  --checkpoint /path/to/trained/checkpoint/ \
  --output /path/to/platt_params.pt \
  --data_path /path/to/validation/data
```

### 5. Config

v16_platt_calibration.config — 启用 platt，关闭 training-time calibration

## 工作流程

```
训练完成 → 加载 checkpoint → 跑验证集 → 收集 logits+labels
    → 拟合 Platt a,b → 注册为 buffer → 保存 checkpoint
    → 导出模型 → 上线自动使用 calibrated probs
```

## 关键设计决策

1. **不在训练时加 calibration loss** — 避免 CTCVR BCE 暴涨
1. **只在 inference 时应用** — 训练完全不受影响
1. **先过拟合小块数据验证 pipeline** — 用小验证集先测通拟合流程
1. **FX tracing 保护** — model export 阶段不应用 Platt
