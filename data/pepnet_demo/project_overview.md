# PEPNet_v2 推荐排序模型项目

## 项目背景

首页推荐流（Home Feed）是 MMB 电商平台的核心流量入口。推荐系统需要同时优化 **点击率（CTR）** 和 **转化率（CVR）**，采用多任务学习（Multi-Task Learning）框架。

当前线上模型为 **DBMtl_DCNv2（v1c）**，基于 TF 1.12。为技术栈升级和效果优化，在 PyTorch + TorchEasyRec 框架下复现并增强 **PEPNet_v2** 模型。

## 业务场景

| 维度 | 说明                                      |
| ---- | ----------------------------------------- |
| 平台 | MMB 电商（东南亚/新兴市场）               |
| 场景 | 首页推荐流                                |
| 任务 | 多目标排序                                |
| 目标 | 点击率 (CTR) → 转化率 (CVR)               |
| 样本 | 53 天训练 / 7 天验证                      |
| 特征 | ~100+ 特征（ID类/序列/KV/统计Ratio/Bias） |
| 指标 | AUC（CTR AUC, CVR AUC）                   |

## 项目目标

1. 在 TorchEasyRec（PyTorch）上完成 PEPNet_v2 模型搭建
1. 找到最优超参组合，最大化 **CVR AUC**（CVR 稀疏，优化难度大于 CTR）
1. 与线上 v1c（DBMtl_DCNv2）对齐对比
1. 择优上线 A/B Test

## 模型架构

### PEPNet_v2

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

#### 核心组件

| 组件            | 功能                                           |
| --------------- | ---------------------------------------------- |
| LHUC-EPNet      | domain-level 门控，tanh [-4,6] 缩放 deep_input |
| LHUC-PPNet      | per-layer scale-before-Dense 门控              |
| CDOT            | slot-level 动态特征压缩变换                    |
| Bias            | 每个特征首维 1-dim 偏置                        |
| CrossV2 (DCNv2) | 低秩显式特征交叉                               |
| Component LN    | 每组件独立 LayerNorm 后 concat                 |

## 实验设置

- **框架**: TorchEasyRec 1.2.x, PyTorch 2.11, CUDA 12.9
- **GPU**: NVIDIA A10 (sm_86)
- **训练**: 1 epoch, AdamW, cosine warmup 200
- **Batch**: 4096
- **评估**: step-based (每 500 步)
- **优化器**: AdamW, weight_decay 仅作用 MLP.weight + cdot.sub_compress_weight
- **加速**: Torchrec SPMD 分布式训练

## 实验结果汇总

| #   | Config                       |  CDOT  | DCNv2 | Epoch |  CTR AUC  |  CVR AUC  | 说明             |
| --- | ---------------------------- | :----: | :---: | :---: | :-------: | :-------: | ---------------- |
| 1   | pepnet                       |  all   |  ❌   |   1   |   0.685   |   0.736   | 基线             |
| 2   | pepnet_nocdot                |   ❌   |  ❌   |   1   |   0.686   |   0.736   | CDOT all 无用    |
| 3   | pepnet_nocdot_noadd          |   ❌   |  ❌   |   1   |     —     |   0.731   | cvr_add_ctr 必开 |
| 4   | pepnet_tower256              |  all   |  ❌   |   1   |   略差    |   略差    | 小 tower 弱      |
| 5   | pepnet_epoch3                |  all   |  ❌   |   3   |   0.658   |   0.704   | 3 epoch 过拟合   |
| 6   | pepnet_cdot_domain           | domain |  ❌   |   1   |   0.690   |   0.739   | CDOT domain 有效 |
| 7   | **pepnet_cdot_domain_dcnv2** | domain |   ✓   |   1   | **0.693** | **0.740** | 🏆 最优          |

## 关键发现

### 验证的假设

- ✅ **CDOT all 无用** — 100+ 特征噪声大，CDOT 1 epoch 不收敛
- ✅ **CDOT domain 有用** — 3 个核心特征信号干净，CDOT 学到有效交互
- ✅ **DCNv2 有效** — CrossV2 提供 CDOT 不具备的显式交叉
- ✅ **cvr_add_ctr_logits 必开** — CTR→CVR 信号传递至关重要
- ✅ **1 epoch 最优** — CTR 电商场景 1 epoch 后过拟合
- ✅ **step-based eval 必要** — epoch-based 和 step-based 互斥

### 当前瓶颈

- PEPNet_v2 结构和 v1c 有结构差：**缺少 relation_mlp**
- v1c 预估比 PEPNet_v2 高约 2pp CVR，核心差距在 relation_mlp

## 后续计划

### 短期（微调上线）

| 方向        | 描述                      |
| ----------- | ------------------------- |
| DCNv2 调参  | cross_num=2, low_rank=128 |
| LR 调试     | cosine warmup 500         |
| PPNet gamma | 1.0 更保守门控            |

### 中期（对齐效果）

| 方向             | 描述                                              |
| ---------------- | ------------------------------------------------- |
| **relation_mlp** | CVR tower 接入 CTR logits 做额外 MLP 输入         |
| 特征精选         | CDOT 在 domain 3 个基础上加 1-2 个高价值 KV/ratio |

### 长期

- 与 v1c 效果对齐后上线 A/B Test
- 探索更高效的交叉结构（Cross Network 变体）

## 文件清单

| 文件                                                    | 说明                                        |
| ------------------------------------------------------- | ------------------------------------------- |
| `tzrec/models/pepnet_v2.py`                             | PEPNet_v2 模型 (含 DCNv2, CDOT, Bias, LHUC) |
| `tzrec/modules/cdot.py`                                 | CDOT 模块                                   |
| `tzrec/modules/lhuc_net.py`                             | LHUC-EPNet + LHUC-PPNet 模块                |
| `tzrec/modules/interaction.py`                          | CrossV2 (DCNv2) 模块                        |
| `config/home_flow_2604_pepnet.config`                   | 基线配置                                    |
| `config/home_flow_2604_pepnet_cdot_domain_dcnv2.config` | 🏆 最优配置                                 |
| `experiment_summary.md`                                 | 实验小结                                    |
