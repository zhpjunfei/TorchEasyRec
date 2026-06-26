______________________________________________________________________

## date: 2026-05-30 tags: [archive, relation-mlp] status: archived related: ["[[../10-architecture/model-components]]"]

# Relation MLP 配置及原理

## 配置位置

文件：`config/v3/home_flow_2604_pepnet_cdot_domain_dcnv2_warmup1000_relation_mlp.config`

```protobuf
task_towers {
  tower_name: "cvr"
  label_name: "is_conversion"
  weight: 1.0
  train_metrics { auc {} }
  metrics { auc {} }
  losses { binary_cross_entropy {} }
  mlp {                     # ← PPNet tower MLP
    hidden_units: [512, 256, 128]
    use_ln: true
    dropout_ratio: 0.1
  }
  task_space_indicator_label: "is_click"  # ← 样本空间指示
  in_task_space_weight: 1
  out_task_space_weight: 0
  relation_tower_names: "ctr"   # ← 关联的 tower
  relation_mlp {                 # ← 关系 MLP 定义
    hidden_units: [64, 32]
    use_ln: true
  }
}
```

## 逐步解释

### `relation_tower_names: "ctr"`

声明 CVR tower 的关联 tower 是 CTR。告诉模型引擎：CVR tower 的 PPNet 隐层输出需要与 CTR tower 的 PPNet 隐层输出做融合。

可以有多个，例如 `["ctr", "ctcvr"]`。

### `relation_mlp { hidden_units: [64, 32]; use_ln: true }`

关系 MLP 本身的结构定义：

- `hidden_units: [64, 32]` — 两层 MLP，第一层输出 64，第二层输出 32
- `use_ln: true` — 每层后接 LayerNorm

### 全局开关 `cvr_add_ctr_logits: true`

独立于 relation_mlp。它做的是 **logit 级加法**（后 sigmoid），而 relation_mlp 做的是 **hidden 级融合**（前 sigmoid）。

______________________________________________________________________

## 模型内部执行流程

### 第一步：计算各 Tower PPNet 隐层

PEPNet_v2 先对每个 task_tower 独立跑 PPNet（LHUC 门控），输出 penultimate hidden：

```
tower_hidden["ctr"] = LHUC_PPNet_ctr(deep_input)    # (B, 128)
tower_hidden["cvr"] = LHUC_PPNet_cvr(deep_input)    # (B, 128)
```

128 来自 `ppnet_hidden_units: [512, 256, 128]` 的最后一位。

### 第二步：计算 Relation MLP

对配置了 `relation_mlp` 的 tower：

```
rel_inputs = [tower_hidden["cvr"]]                              # (B, 128)
rel_inputs.append(relation_hidden["ctr"])                        # (B, 128) — CTR 本身无 relation_mlp，所以 relation_hidden["ctr"] = tower_hidden["ctr"]
rel_inputs_concat = torch.cat(rel_inputs, dim=1)                  # (B, 256)
relation_hidden["cvr"] = relation_mlp(rel_inputs_concat)          # MLP: 256 → 64 → 32 → (B, 32)
```

对未配置 `relation_mlp` 的 tower：

```
relation_hidden["ctr"] = tower_hidden["ctr"]                     # (B, 128)，直接透传
```

### 第三步：计算最终 logit

```
tower_final["cvr"](relation_hidden["cvr"])        # Linear(32→1) → (B, 1) = logit_cvr_raw
tower_final["ctr"](relation_hidden["ctr"])        # Linear(128→1) → (B, 1) = logit_ctr

# 如果 cvr_add_ctr_logits = true:
logit_cvr = logit_cvr_raw + logit_ctr

# 否则:
logit_cvr = logit_cvr_raw + bias_sum
```

### 数据流图

```
                   ┌──────────────────────────────────────────────────┐
                   │                   deep_input                     │
                   └────────┬─────────────────────────┬───────────────┘
                            │                         │
                   ┌────────▼────────┐       ┌────────▼────────┐
                   │  PPNet CTR      │       │  PPNet CVR      │
                   │  [512,256,128]  │       │  [512,256,128]  │
                   └────────┬────────┘       └────────┬────────┘
                            │                         │
                   ┌────────▼────────┐       ┌────────▼────────┐
                   │  tower_hidden   │       │  tower_hidden   │
                   │  ["ctr"] (B,128)│       │  ["cvr"] (B,128)│
                   └────────┬────────┘       └────────┬────────┘
                            │                         │
                            │              ┌──────────▼──────────┐
                            │              │  concat(cvr, ctr)   │
                            │              │  → (B, 256)         │
                            │              └──────────┬──────────┘
                            │                         │
                            │              ┌──────────▼──────────┐
                            │              │   relation_mlp      │
                            │              │   [64, 32] + LN     │
                            │              │   → (B, 32)          │
                            │              └──────────┬──────────┘
                            │                         │
                   ┌────────▼────────┐       ┌────────▼────────┐
                   │ tower_final_ctr │       │ tower_final_cvr │
                   │ Linear(128→1)   │       │  Linear(32→1)   │
                   └────────┬────────┘       └────────┬────────┘
                            │                         │
                   ┌────────▼────────┐       ┌────────▼────────┐
                   │   logit_ctr    │       │  logit_cvr_raw  │
                   │    (B, 1)      │       │     (B, 1)      │
                   └────────┬────────┘       └────────┬────────┘
                            │                         │
                            └─────── cvr_add ─────────┘
                                        ↓
                               ┌────────────────┐
                               │  logit_cvr     │
                               │  (B, 1)        │
                               └────────────────┘
```

方框实线 = 有参数可学习，虚线 = 无参数操作。

## 与 v1c 的关系

DBMtl_DCNv2 (v1c) 的 relation_mlp 逻辑相同：

- CVR 塔的 PPNet penultimate hidden concat CTR 塔的 PPNet penultimate hidden
- 经过一个独立的 MLP（`[64, 32]`）后接 tower_final Linear 输出
- 之后再与 CTR logit 做 element-wise add

实现完全对齐，但实验结果表明在已有 `cvr_add_ctr_logits` 的前提下，relation_mlp 的 hidden 级融合未带来额外增益（CVR 0.741 vs 0.742 baseline），推测两路径信息冗余。

## 反向推理：v1c 的 2pp CVR 差距来源

relation_mlp 对齐后仍差 2pp，说明 v1c 和 PEPNet_v2 的核心差距**不在 relation_mlp**。可能方向：

1. CDOT 参数差异（dimension, activation, compress 结构）
1. LHUC 位置或 scale 范围差异
1. Loss 配置（weight, sample weight, 多任务 loss 组合）
1. 特征侧差异（v1c 可能有 PEPNet_v2 未使用的特征或 embedding 维度不同）
