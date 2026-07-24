# Platt Calibration 集成指南

## 完整流程 (4 step)

```
Step 1: 训练                              Step 2: 拟合 Platt              Step 3: 注入 DCP               Step 4: 导出
───────────                            ─────────────                   ───────────────            ───────────
tzrec.train_eval                       platt_calibrate.py              platt_inject_into_export.py    tzrec.export
     │                                       │                                │                               │
     ▼                                       ▼                                ▼                               ▼
model.ckpt-{step}/         →    platt_fitted/platt_meta.json   →    injected/model.ckpt-{now}/   →   export/saved_model/
```

### Step 1: 训练（照旧）

使用新的 v16_platt_calibration.config，与现有 train_eval 完全兼容：

```bash
python -m tzrec.train_eval \
    --pipeline_config_path data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config \
    --train_input_path <训练数据ODPS路径> \
    --model_dir /path/to/output/train/
```

产出：`/path/to/output/train/model.ckpt-{step}/` + `pipeline.config`

**注意：** 该 config 中 `platt_calibration_enabled: true` 但 `use_calibration: false`，确保没有双重校准。

### Step 2: 拟合 Platt 参数

```bash
python tools/platt_calibrate.py \
    --config data/pepnet_demo/config/v16/home_flow_2604_v16_platt_calibration.config \
    --checkpoint_dir /path/to/output/train/ \
    --val_data_path <验证集ODPS路径> \
    --batch_size 4096 \
    --device cuda:0 \
    --output_dir /path/to/output/platt_fitted/
```

产出：

- `platt_fitted/platt_meta.json` — 可读的 a,b 参数
- `platt_fitted/platt_params.pt` — PyTorch state_dict 格式

### Step 3: 注入 DCP checkpoint

```bash
python tools/platt_inject_into_export.py \
    --config /path/to/output/train/pipeline.config \
    --trained_ckpt /path/to/output/train/model.ckpt-{step}/ \
    --platt_meta /path/to/output/platt_fitted/platt_meta.json \
    --output /path/to/output/injected_for_export/
```

产出：

- `injected_for_export/model/` — DCP 格式 patched checkpoint（含 fitted a,b buffers）
- `injected_for_export/platt_patch_meta.json` — 补丁元信息

### Step 4: 导出模型

```bash
torchrun --nproc_per_node=1 -m tzrec.export \
    --pipeline_config_path /path/to/output/train/pipeline.config \
    --checkpoint_path /path/to/output/injected_for_export/ \
    --export_dir /path/to/output/export/final_with_fg/
```

线上加载这个 saved_model，Platt 校准在 predict() 时自动生效。

## 技术细节

### platt_calibrate.py 做了什么

1. 加载训练好的模型 checkpoint
1. 在验证集上跑 forward，收集每个塔的 logits + labels
1. 对每个塔用 Newton 法拟合 a,b
1. 冻结参数为 buffer，输出 JSON 元数据

### platt_inject_into_export.py 做了什么

1. 加载同样的 config 创建模型结构
1. 从原始 checkpoint 恢复权重（支持 DCP 和 .pt 两种格式）
1. 从 meta.json 读取 fitted a,b，写入模型 buffer
1. 用 dist_cp.save 重新保存为 DCP 格式（兼容 tzrec.export 加载）

### 为什么需要两步？

Platt calibrate 是单卡 GPU 操作，不需要分布式初始化。Inject 需要加载 DCP checkpoint（可能有多卡训练的数据），然后重新保存。两步分离保证了灵活性。

### 注意事项

- **不要同时启用** `use_calibration: true` 和 `platt_calibration_enabled: true`
- 验证数据必须独立于训练集，否则拟合参数会 overfitting
- FX tracing 保护确保 model export 阶段不会报错
