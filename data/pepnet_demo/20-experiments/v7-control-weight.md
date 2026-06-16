______________________________________________________________________

## date: 2026-06-13 tags: [experiment, v7, control-weight, selection-bias] related: \["[v10-experiments]", "[../10-architecture/pepnet-dcn-ple]"\]

# v7 样本加权 + Control 特征实验

> 精排只控制 **5% 流量**（随机均匀抽样），95% 由另一模型控制。
> 训练数据 100% 流量，但 label 存在选择偏差——non-control 95% 的 label 隐含了另一模型的选品偏好。
> 目标：一个月内替换掉另一模型，全流量上线。

## 核心思路

### 问题诊断：选择偏差（Selection Bias）

```
100% 流量
  ├── 5% (control)  → 本模型曝光 → 用户反馈 → label 无偏 ✅
  └── 95% (non-control) → 另一模型曝光 → 用户反馈 → label 有偏 ⚠️
```

Non-control 的 label 是「另一模型筛选后的用户反馈」——另一模型倾向推荐高转化商品，导致 CVR 正样本被系统性放大。模型在这 95% 数据上学到的 pattern 部分是对另一模型选品策略的拟合，而非真实用户行为。

### 矫正方法：IPW（Inverse Probability Weighting）

IPW 通过给每个样本赋权，让加权后的训练分布近似于无偏的全流量分布：

$$E[Y] = E\\left[\\frac{Z \\cdot Y}{\\pi(X)} + \\frac{(1-Z) \\cdot Y}{1-\\pi(X)}\\right]$$

其中 $Z$ = 是否为 control，$\\pi(X)$ = 倾向分 = control 概率。

由于 control 是随机均匀抽样（5%），$\\pi(X) = 0.05$ 恒成立，IPW 简化为：

```
control      = 1/0.05 = 20
non-control  = 1/0.95 ≈ 1.053
```

### 权重选择：×5 而非 ×20

ESS（Effective Sample Size）约束：

$$ESS = \\frac{(\\sum w_i)^2}{\\sum w_i^2}$$

|   倍数    | Control 梯度占比 |   ESS   | 风险     |
| :-------: | :--------------: | :-----: | :------- |
|    ×1     |        5%        |  100%   | 无纠正   |
|    ×3     |       14%        |   91%   | 纠正不足 |
|  **×5**   |     **21%**      | **65%** | ✅ 平衡  |
|    ×10    |       34%        |   39%   | 噪声大   |
| ×19 (IPW) |       50%        |   26%   | 训练不稳 |

**×5 的理由**：

- Control 梯度贡献从 5%→21%，偏差已有明显纠正
- ESS 保持 65%，训练噪声可控
- 保留 non-control 的主流信号，避免全量上线时分布漂移

### 与 f_is_control 特征互补

| 机制            | 作用                                                  | 互补                 |
| :-------------- | :---------------------------------------------------- | :------------------- |
| sample_weight   | 放大 control 样本的 loss 信号（全局梯度重分配）       | 让模型更关注 control |
| is_control 特征 | DCN 学习 control × item_id 等交叉模式（局部特征交互） | 让模型区分两种流量   |

## 实验计划

### W1：v7 baseline + sample_weight + is_control feature

**Config**: `home_flow_2604_v7_sw.config`

改动：

1. `data_config { sample_weight_fields: "sample_weight" }`
1. `task_towers { tower_name: "cvr" sample_weight_name: "sample_weight" }`
1. 新增 `f_is_control` id_feature → domain group

### W2：v7 + dot-product attention + 16-dim seq（简化模型）

依赖 W1 结果。如果 W1 CVR 提升，说明选择偏差确实是障碍。W2 在上限基础上进一步降低过拟合。

### W3：合并最优 → 全流量 A/B

## 训练

**Config**: `data/pepnet_demo/config/v7/home_flow_2604_v7_sw.config`

脚本基于 `train_v7_ple_d_variants.sh`，数据表不变：

```
TRAIN_TABLE = "home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_train"
VAL_TABLE   = "home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_shuffled_30d_v3_val"
```

## 结果

| 实验                  | CTR AUC | ΔCTR | CVR AUC | ΔCVR |
| :-------------------- | :-----: | :--: | :-----: | :--: |
| v7_ple_d16 (baseline) |    —    |  —   |    —    |  —   |
| v7_sw (W1)            |   ⏳    |  ⏳  |   ⏳    |  ⏳  |
| v7_simplify (W2)      |   ⏳    |  ⏳  |   ⏳    |  ⏳  |

## 备注

- `f_is_control` 的数据字段名待确认，当前占位 `sample:is_control`
- sample_weight 需要数据 pipeline 产出：`sample_weight = is_control ? 5 : 1`
