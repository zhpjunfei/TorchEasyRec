______________________________________________________________________

## date: 2026-06-07 tags: [architecture, pepnet, baseline] related: \["\[[pepnet-dcn-ple]\]", "\[[model-components]\]"\]

# PEPNet_v2 — 基础架构

> PEPNet_v2 是本项目的**基础架构**, 本项目实际使用的是其扩展版本 \[[pepnet-dcn-ple|PEPNetDCNPLE]\] (含 PLE).

## 数据流 (PEPNet_v2)

```
Features → Embedding
  ├── main_group (all) → LN ──────────────┐
  ├── cdot_group (domain) → CDOT → LN     ├── concat → deep_input
  ├── bias_group (domain) → Bias → LN     │
  └── dcnv2_group (all) → CrossV2 → LN ───┘
                                              ↓
  lhuc_group (domain) → LHUC-EPNet → scale → deep_input *= scale
                                              ↓
  CTR Tower (LHUC-PPNet) ───────────────────→ logit_ctr ──→ probs_ctr
  CVR Tower (LHUC-PPNet) ── + CTR logits ──→ logit_cvr ──→ probs_cvr
```

## 核心组件

| 组件            | 功能                                           | 详见                           |
| :-------------- | :--------------------------------------------- | :----------------------------- |
| LHUC-EPNet      | domain-level 门控, tanh [-4,6] 缩放 deep_input | \[[model-components#LHUC]\]    |
| LHUC-PPNet      | per-layer scale-before-Dense 门控              | \[[model-components#LHUC]\]    |
| CDOT            | slot-level 动态特征压缩变换                    | \[[model-components#CDOT]\]    |
| Bias            | 每个特征首维 1-dim 偏置                        |                                |
| CrossV2 (DCNv2) | 低秩显式特征交叉                               | \[[model-components#CrossV2]\] |
| Component LN    | 每组件独立 LayerNorm 后 concat                 |                                |

## 关键设计点

1. **CVR = logit-level addition with CTR**: `tower_output + ctr_logits_val` (前 sigmoid), 不走标准 `cvr_add_ctr_probs`
1. **cvr_add_ctr_logits = true**: 见 `multi_task_rank.proto`
1. **AdamW weight_decay 仅作用**:
   - MLP `.weight` (Dense 层)
   - `cdot.sub_compress_weight`
   - **不作用** LayerNorm, biases, embeddings
1. **优化器 regex**:
   ```
   (.*)(epnet\.gate|cdot\.compress_mlp|task_towers\..*tower_layers|task_towers\..*gate_mlps)\.(.*)\.weight
   (.*)cdot\.sub_compress_weight
   ```

## v1c 基线 (DBMtl_DCNv2, 53-day 数据集)

| 模型                        |  CTR AUC   |  CVR AUC   |
| :-------------------------- | :--------: | :--------: |
| v1c (DBMtl_DCNv2) 线上      |   0.690    | **0.768**  |
| PEPNet_v2 (warmup1000) 最佳 |   0.694    |   0.742    |
| 差距                        | +0.4pp CTR | -2.6pp CVR |

PEPNet_v2 CTR 略好但 CVR 差距 2.6pp. **当时认为架构性差距, 后续被推翻** (见 \[[../20-experiments/v6-design-matrix|v6 设计矩阵]\]).

## 文件位置

- `tzrec/models/pepnet_v2.py` — PEPNet_v2 主类
- `tzrec/models/pepnet_dcn_ple.py` — PEPNetDCNPLE (本项目实际使用)
- `tzrec/modules/cdot.py` — CDOT
- `tzrec/modules/lhuc_net.py` — LHUC-EPNet + LHUC-PPNet
- `tzrec/modules/interaction.py` — CrossV2

## 下一步

- \[[pepnet-dcn-ple|PEPNetDCNPLE]\] — 本项目使用, 在 PEPNet_v2 基础上加 PLE
- \[[../20-experiments/v6-design-matrix|v6 设计矩阵]\] — PEPNet_v2 vs PEPNetDCNPLE 对比
