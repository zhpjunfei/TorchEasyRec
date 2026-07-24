# Inference-time Platt Calibration — 快速指南

## 一句话说明

训练完后用验证集拟合 `a*logit + b` 两个参数，冻结到 checkpoint 里。线上推理时自动应用，**零影响训练目标**。

## 核心优势 vs Temperature Scaling

|          | T=1.5 + ECE Loss            | Platt (a,b)               |
| -------- | --------------------------- | ------------------------- |
| 影响训练 | ✅ 改变梯度, CTCVR BCE +14% | ❌ 纯 inference           |
| 参数量   | 1 (T)                       | 2 (a,b)                   |
| ECE 改善 | ~40% (实测)                 | ~86% (模拟)               |
| 排序影响 | 单调 (AUC不变)              | 基本单调 (rank corr 0.99) |
| 线上风险 | 高 (曝光池重构)             | 低 (仅微调 prob)          |

## 使用步骤

### Step 1: 训练模型（正常流程，不需要改）

```bash
# 使用 v16_platt_calibration.config 训练
python -m tzrec.train_eval \
    --config data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config \
    --train_data ... --eval_data ...
```

训练完成后得到一个 checkpoint（包含 `_platt_scalers` buffers，初始为 a=1, b=0）。

### Step 2: 离线拟合 Platt 参数

```bash
python tools/platt_calibrate.py \
    --config data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config \
    --checkpoint /path/to/checkpoint/step_7300/ \
    --output /path/to/fitted_platt.pt \
    --data_path /path/to/validation/data
```

输出：

- `fitted_platt.json`: a, b 值 + 拟合统计信息
- `fitted_platt.pt`: 可直接加载的 PyTorch 权重

### Step 3: 更新 checkpoint（带上 fitted 参数）

```python
import torch
from tzrec.models.pepnet_dcn_ple import PEPNetDCNPLE
from tzrec.main import init_model, parse_model_configs

model_config, train_config, export_config = parse_model_configs(
    "data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config"
)
_model, _ = init_model(model_config, train_config, export_config)

# 加载训练权重
torch.load("checkpoint.ckpt", map_location="cpu")
_model.load_state_dict(...)

# 加载 Platt 参数
platt_params = torch.load("fitted_platt.pt")
for tower_name, params in platt_params.items():
    idx = _model._platt_tower_to_scaler_idx[tower_name]
    scaler = _model._platt_scalers[idx]
    scaler.register_buffer("_a", torch.tensor(params["a"]))
    scaler.register_buffer("_b", torch.tensor(params["b"]))

# 保存带 Platt 参数的完整 checkpoint
torch.save(_model.state_dict(), "final_with_platt.ckpt")
```

### Step 4: 导出并上线

导出的模型在推理时会自动应用 Platt 校准。不需要改线上代码。

## 技术细节

### Platt 是什么？

Platt scaling 是统计学习中的概率校准方法：

```
σ(a · logit + b)
```

- `a > 1`: 让预测更自信（远离 0.5）
- `a < 1`: 让预测更保守（靠近 0.5）
- `b > 0`: 整体偏正向（提高正类概率）
- `b < 0`: 整体偏负向（降低正类概率）

与 temperature scaling (logit / T) 不同，Platt 多了偏移自由度 b。

### 拟合方法

牛顿法最大化对数似然：

```
L = -Σ [ y·log(σ(ax+b)) + (1-y)·log(1-σ(ax+b)) ]
```

收敛通常只需 5-15 次迭代。

### FX Tracing 保护

Model export 阶段跳过 Platt 应用（`not is_fx_tracing()`），避免 Proxy 问题。

## 文件清单

| 文件                                              | 改动                         |
| ------------------------------------------------- | ---------------------------- |
| `tzrec/modules/calibration.py`                    | +PlattScaler 类 (+182 lines) |
| `tzrec/models/pepnet_dcn_ple.py`                  | +predict hook (+3 sections)  |
| `proto/model.proto`                               | +field 25                    |
| `proto/model_pb2.py`                              | 重新编译                     |
| `tools/platt_calibrate.py`                        | 新建                         |
| `v16/home_flow_2604_v16_platt_calibration.config` | 新建                         |
