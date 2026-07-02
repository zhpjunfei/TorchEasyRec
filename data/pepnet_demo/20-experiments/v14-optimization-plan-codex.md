______________________________________________________________________

## date: 2026-07-01 tags: [experiment, v14, v15, roadmap, codex-review] status: updated related: \["\[[v14-experiments]\]", "\[[v14-optimization-plan]\]", "\[[../10-architecture/pepnet-dcn-ple]\]" \]

# v14+ 优化路线图 — 以 UV CTR + UV CVR 为核心目标

> Codex 深度审查版。基于 v6~v14 共 28+ 实验、ctr45 线上 A/B、eval pipeline 确定性修复、ots 全扫描（21 点 0.005→0.50）的完整知识积累。

______________________________________________________________________

## 一、当前基线状态（2026-06-29）

### 1.1 确定性基线

| 指标     | v12 baseline（ots=0.01） | ots50（当前最优） | 提升           |
| -------- | ------------------------ | ----------------- | -------------- |
| GAUC_ctr | 0.704368                 | 0.704006          | **−0.04pp** ⚠️ |
| GAUC_cvr | 0.695728                 | 0.741334          | **+4.56pp** 🏆 |
| gap_ctr  | 1.22pp                   | 1.28pp            | +0.06pp        |
| gap_cvr  | 5.25pp                   | 4.51pp            | **−0.74pp** ✅ |
| BCE_cvr  | 0.493955                 | 0.383982          | −0.110         |

### 1.2 已完成的优化历程

| 版本  | 方向                                    | 结论                                         |
| ----- | --------------------------------------- | -------------------------------------------- |
| v6-v7 | PLE 架构选型 (d=8/16/32)                | PLE+d=8 最优                                 |
| v10   | DIN 序列特征优化                        | dim align + B2 有效                          |
| v11   | 对比学习 (InfoNCE)                      | 有效但 uvctr 提升有限                        |
| v12   | Loss 加权 (静态/不确定/PE-MTL/ctr36~60) | 静态权重倒 U 型，ctr45=4.5 最优              |
| v13   | PCGrad 梯度手术 + 架构审核              | 全部无效；发现 CVR dropout 被静默忽略        |
| v14   | **out_task_space_weight 全扫 21 点**    | **单调 +4.56pp GAUC_cvr，ots=0.50 边际递减** |

### 1.3 已证否的方向

| 方向                              | 证据                             | 结论                        |
| --------------------------------- | -------------------------------- | --------------------------- |
| dropout 调参 (ots≥0.12)           | 0.1→0.3 仅 +0.08pp               | ❌ ots 提供足够正则，冗余   |
| CVR tower 扩宽                    | [512,256,128]→[1024,512] −0.18pp | ❌ 瓶颈不在 tower MLP       |
| PLE 容量缩减                      | [256,128] + dropout +0.08pp      | ➖ 上限不足                 |
| weight decay / adamw              | 等同基线                         | ❌ 零效果                   |
| ctcvr/ESMM                        | +0.29pp GAUC_cvr, −0.07pp CTR    | ❌ 中性偏负                 |
| 梯度隔离/手术/自适应加权          | 全部负或中性                     | ❌                          |
| PLE capacity 升级 (ots012_plebig) | +2.84pp vs ots012 +2.88pp        | ❌ 无效，−0.04pp            |
| seq_transformer                   | −0.06pp vs ots012                | ❌ DIN 已充分捕捉 item 交互 |

______________________________________________________________________

## 二、核心诊断

### 2.1 已解决的矛盾：离线 vs 在线（CVR）

gap_cvr 从 5.25pp → 4.51pp，ots 机制成功将 CVR 塔从"只看点击样本"扩展到"利用非点击样本梯度"。非点击用户以 `out_task_space_weight` 比例进入训练，提供了更强的正则化信号。

### 2.2 尚未解决的矛盾：UV CTR 轻微受损

ots ≥ 0.20 时，**GAUC_ctr 持续 −0.04~−0.06pp**。非点击样本进入 CVR 训练后，PLE 共享层的表征被"污染"——非点击用户和点击用户的特征分布不同，CVR 塔从非点击数据学到的模式与 CTR 塔的偏好不一致。

### 2.3 根本问题：UV 级指标尚未成为优化目标

```
优化目标：maximize auc_ctr + auc_cvr   ← pv 级
监控指标：GAUC_ctr, GAUC_cvr           ← uv 级（被动观察）
```

当前所有实验以 **pv 级 auc** 为优化目标，grouped_auc{mmb_id} 仅作为监控指标。这意味着：

1. 我们在优化 pv 级排序质量，但线上业务关心的是 uv 级（用户级别）的转化率
1. 当 pv 级和 uv 级指标方向不一致时（如 ctr45 线上 A/B 的发现），缺乏明确的决策依据
1. **ots50 的 +4.56pp GAUC_cvr 是 pv 级优化的副产品，而非 uv 级优化目标驱动的结果**

### 2.4 ots=0.50 的隐患

| 问题            | 说明                                                                                    |
| --------------- | --------------------------------------------------------------------------------------- |
| BCE_cvr = 0.384 | 远低于 baseline 的 0.494，模型对非点击样本过度自信（BCE 接近 0 意味着几乎确信不会转化） |
| 线上风险        | 对长尾用户 CVR 可能系统性低估                                                           |
| CTR 受损        | GAUC_ctr −0.04pp，高 ots 下共享表征被污染                                               |
| 边际递减        | 0.20→0.50 仅 +0.91pp，继续增大收益极小                                                  |

______________________________________________________________________

## 三、优化目标

### 3.1 定量目标

| 指标         | 当前 (ots50) | 目标           | 说明                |
| ------------ | ------------ | -------------- | ------------------- |
| **GAUC_ctr** | 0.704006     | **≥ 0.704368** | 不劣于 v12 baseline |
| **GAUC_cvr** | 0.741334     | **≥ 0.750000** | 再 +0.87pp          |
| **gap_cvr**  | 4.51pp       | **≤ 3.50pp**   | 再 −1.01pp          |
| **BCE_cvr**  | 0.384        | **≥ 0.420**    | 防止过置信          |

### 3.2 定性目标

- **从"优化 pv 级 auc，监控 uv 级 gauc"转向"以 uv 级 gauc 为优化目标，pv 级 auc 为约束条件"**
- 构建 uv 级指标的离线评估闭环，使离线 GAUC 与线上 UV 指标方向一致
- 消除 ots 带来的 CTR 受损

______________________________________________________________________

## 四、优化路线图

### Phase 1：UV 级优化（P0，1-2 周）

> 核心思想：不再把 GAUC 当作监控指标，而是作为优化目标本身。

|  序号   | 实验                          | 内容                                                                                    |                预期增益                |    改动量     | 风险 |
| :-----: | ----------------------------- | --------------------------------------------------------------------------------------- | :------------------------------------: | :-----------: | :--: |
| **1.1** | **ots × CTR weight 二维网格** | 在 ots∈{0.10, 0.15, 0.20, 0.30} × CTR weight∈{3.3, 4.5, 5.4} 的 12 格中搜索 Pareto 最优 | GAUC_cvr +0.5~1pp，GAUC_ctr ≥ baseline |  config 改动  |  低  |
| **1.2** | **GAUC-aware ots 重搜**       | 以 GAUC_cvr 为主优化目标、GAUC_ctr ≥ baseline 为约束，重跑 ots 搜索（非 pv auc）        |   找到 uv 级最优 ots（可能 ≠ 0.50）    |  config 改动  |  低  |
| **1.3** | **UV-weighted BCE**           | 对 CVR 的 BCE loss 按 mmb_id 分组，低频用户 group 的样本权重更高                        |            gap_cvr −0.5~1pp            | 代码 + config |  中  |
| **1.4** | **search_weight IPW 校准**    | 对 search_weight 按 mmb_id 分组做逆 propensity 加权，矫正用户级别转化分布偏差           |            gap_cvr −0.5~1pp            | SQL + config  |  中  |

**1.1 网格设计**：

| 实验 | ots  | CTR weight | 预期场景                                  |
| ---- | ---- | ---------- | ----------------------------------------- |
| A    | 0.20 | 4.5        | 当前最优 ots + 当前最优 CTR weight        |
| B    | 0.15 | 5.4        | 中等 ots + ctr45 权重                     |
| C    | 0.10 | 4.5        | 低 ots + 高 CTR weight                    |
| D    | 0.30 | 3.3        | 高 ots + 低 CTR weight（验证 ots 独立性） |

**关键洞察**：CTR weight 放大（3.3→4.5）在 pv 级对 CTR AUC 有益（+0.10%），但在 uv 级有负向趋势。ots 也在 uv 级对 CTR 有轻微负向（−0.04~−0.06pp）。**两者的负向效应可能叠加**，需要通过二维网格找到 Pareto 最优。

### Phase 2：CVR Tower 架构升级（P0-P1，2-3 周）

> 核心思想：ots 成功证明了非点击样本的价值，但 CVR tower 的结构限制了它充分利用这些样本的能力。

|  序号   | 实验                           | 内容                                          |  预期增益  |    改动量     |       风险       |
| :-----: | ------------------------------ | --------------------------------------------- | :--------: | :-----------: | :--------------: |
| **2.1** | **CVR tower residual**         | 在 LHUC_PPNet 每层后加 residual connection    | +0.3~0.5pp |  代码 ~20 行  |        低        |
| **2.2** | **CVR-specific expert gating** | PLE extraction 中 CVR expert 数 2→4           |  +0.5~1pp  |    config     |        低        |
| **2.3** | **CVR 独立 bottom**            | CVR 有独立 bottom network，不经过 PLE routing |   +1~2pp   | 代码 + config | 高（需重新设计） |

**2.2 CVR-specific expert gating 设计**：

```protobuf
# 当前：2 task experts + 2 shared（CTR 和 CVR 共享）
extraction_networks {
  network_name: "layer1"
  expert_num_per_task: 2    # CTR 2 experts, CVR 2 experts
  share_num: 2
  task_expert_net { hidden_units: [512, 256] }
  share_expert_net { hidden_units: [512, 256] }
}

# 目标：CVR 4 experts，CTR 保持 2 experts
extraction_networks {
  network_name: "layer1"
  expert_num_per_task: 4    # CTR 2 experts, CVR 4 experts
  share_num: 2
  task_expert_net {
    hidden_units: [512, 256]
    expert_num: 2           # CTR
  }
  task_expert_net {
    hidden_units: [512, 256]
    expert_num: 4           # CVR
  }
  share_expert_net { hidden_units: [512, 256] }
}
```

**2.3 独立 bottom 的设计**：

```
main_features → DCNv2 → CDOT → Bias → LN
                              ↓
                    ┌─────────┴─────────┐
                    ↓                   ↓
              CTR: PLE routing      CVR: 独立 bottom (2层MLP)
                    ↓                   ↓
              CTR tower           CVR tower
```

代价：参数量增加 ~30%，但 CVR 不再受 CTR 梯度污染。

### Phase 3：CDOT 与 DCNv2 微调 ✅ 已完成（2026-07-01）

> 结论：CDOT output_dim 4→8（−0.11pp）和 DCNv2 cross_num 4→6（−0.19pp）均为中性。所有 config-only 模型 lever 已穷尽。

|  序号   | 实验             | 内容                 |       结果        |   状态    |
| :-----: | ---------------- | -------------------- | :---------------: | :-------: |
| **3.1** | **cdot_out8**    | CDOT output_dim: 4→8 | −0.11pp vs ots012 | ✅⏹️ 中性 |
| **3.2** | **dcnv2_cross6** | DCNv2 cross_num: 4→6 | −0.19pp vs ots012 | ✅⏹️ 中性 |

### Phase 3b：新方向（纯 config，2026-07-01 启动）

|  序号   | 实验                                  | 内容                                            |  预期增益  |     改动量     | 风险 |
| :-----: | ------------------------------------- | ----------------------------------------------- | :--------: | :------------: | :--: |
| **3.3** | **CVR shortcut feature injection** 🏃 | 20×conversion_15d KV + 3 raw → CVR tower        |  +0.3~1pp  | code + config  |  中  |
| **3.4** | **ots × CTR weight 网格**             | ots∈{0.10,0.15,0.20,0.30} × ctr_w∈{3.3,4.5,5.4} |  +0.5~1pp  | config 4-12 个 | 极低 |
| **3.5** | **CVR PLE expert 增加**               | `expert_num_per_task: 4, share_num: 2`          | +0.3~0.8pp |  config 1 行   |  低  |
| **3.6** | **CVR-specific expert gating**        | CVR experts 2→4 (需代码修改)                    |  +0.5~1pp  | code + config  |  中  |

**CDOT 压缩分析（已完成，−0.11pp 中性）**：

当前 `cdot { output_dim: 4 }` 将 374-dim 压缩到 4-dim，压缩比 93.7%。这意味着 370 维的交叉信息被丢弃。CDOT 流程：

```
compress: [B, 374] → [B, 4] (sub_compress_weight: [374, 4])
interaction: [B, 4] → [B, 4] (mid_dim=4, output_dim=4)
```

4-dim 输出与 374-dim 输入之间信息损失巨大。`cdot_out8` 将 output_dim 提升到 8，压缩比降到 97.9%，但保留了更多信息。

**决策逻辑**：

```
cdot_out8 ≥ +0.3pp → CDOT capacity 有效，继续探索 output_dim 8→16
cdot_out8 < +0.2pp → 确认 4-dim 已够用，放弃 CDOT 调优

dcnv2_cross6 ≥ +0.2pp → 更多交叉层有效
dcnv2_cross6 < +0.1pp → 确认 4 层已够，放弃
```

### Phase 4：数据驱动（P1-P2，3-4 周，Phase 2-3 完成后启动）

> 核心思想：模型架构优化遇到瓶颈后，最后的大杠杆在数据侧。

|  序号   | 实验                | 内容                                         |  预期增益  |             改动量              | 风险 |
| :-----: | ------------------- | -------------------------------------------- | :--------: | :-----------------------------: | :--: |
| **4.1** | **实时短窗口特征**  | rt5m/rt15m — Flink SQL → FeatureStore → ODPS | +0.5~1.5pp | 高（Flink SQL + 数据 pipeline） |  中  |
| **4.2** | **实时 ratio 特征** | click_rate_rt — Flink SQL 新增曝光计数       | +0.3~0.8pp |               高                |  中  |
| **4.3** | **用户侧实时统计**  | user\_\_cnt_click_rt1h 等                    | +0.2~0.5pp |               高                |  中  |
| **4.4** | **CVR 专属特征**    | 用户近 7 天/30 天转化频次、品类偏好稳定性    | +0.3~0.8pp |            中（SQL）            |  低  |

### Phase 5：部署与调优（P0，贯穿全程）

|  序号   | 实验                     | 内容                                               | 优先级 |
| :-----: | ------------------------ | -------------------------------------------------- | :----: |
| **5.1** | **最优 config 重复验证** | 选定 config 重跑 3 次确认可复现                    |   P0   |
| **5.2** | **在线融合 β 调优**      | fusion_score = CTR × CVR^β，找 uvctr 最优 β        |   P0   |
| **5.3** | **gap_cvr 监控**         | 离线 GAUC vs 在线 UV GAUC 差距，验证离线评估有效性 |   P0   |
| **5.4** | **BCE_cvr 温度校准**     | 如 BCE_cvr < 0.420 做 temperature scaling          |   P1   |
| **5.5** | **在线 A/B 全指标**      | 必加在线 CVR/GMV/订单数/用户停留时长               |   P0   |

______________________________________________________________________

## 五、决策树

```
Phase 1: UV 级优化（1-2 周）
│
├── ots × CTR weight 网格找到 Pareto 最优
│   ├── GAUC_ctr ≥ baseline 且 GAUC_cvr ≥ +3.5pp → 进入 Phase 2
│   └── GAUC_ctr 仍 < baseline → 调整 ots 上限或引入 UV-weighted BCE
│
├── UV-weighted BCE / IPW 有效（gap_cvr −0.5pp+）→ 固化到生产
└── 全部无效 → 确认模型架构瓶颈，直接进入 Phase 2

Phase 2: CVR Tower 架构升级（2-3 周）
│
├── CVR-specific expert gating ≥ +0.5pp → 主攻 expert 路由优化
│   └── 考虑独立 bottom（如果 expert gating 不够）
│
├── CVR tower residual ≥ +0.3pp → 低成本高回报，直接上线
└── 全部 < +0.2pp → 确认独立 bottom 是唯一路径

Phase 3: CDOT 与 DCNv2 微调（1 周，与 Phase 1 并行）
│
├── cdot_out8 ≥ +0.3pp → 继续探索 output_dim 8→16
└── 全部 < +0.2pp → 放弃 config-only 调优

Phase 4: 数据驱动（3-4 周，Phase 2-3 完成后启动）
│
├── 实时特征 ≥ +0.5pp → 建立在线学习 pipeline
└── < +0.3pp → 数据侧杠杆耗尽，回到 Phase 2 深挖

Phase 5: 部署调优（贯穿全程）
│
└── 每轮实验后：重复验证 + 温度校准 + 在线 A/B 全指标
```

______________________________________________________________________

## 六、实验提交顺序（2026-07-01 更新）

```
Week 1:     Phase 3b — 纯 config 快速并行
  ├── 3.3 ots × CTR weight 网格（4 configs，可并行）🏃
  ├── 3.4 uniform PLE expert 增加（1 config，可并行）
  └── 3.5 CVR-specific expert gating（需代码，串行）

Week 2-3:   Phase 2 (CVR Tower 架构升级)
  ├── 2.1 CVR tower residual（代码修改，串行）
  ├── 2.2 CVR-specific expert gating（代码修改，串行）
  └── 2.3 CVR 独立 bottom（仅在前两项无效时启动）

Week 4-6:   Phase 4 (数据驱动)
  ├── 4.1-4.3 实时特征（Flink SQL，串行）
  └── 4.4 CVR 专属特征（SQL，可并行）

贯穿全程:  Phase 5 (部署与调优)
  ├── 5.1 每轮实验重复验证
  ├── 5.2 在线融合 β 调优
  ├── 5.3 gap_cvr 监控
  └── 5.5 在线 A/B 全指标
```

______________________________________________________________________

## 七、关键假设与验证计划

### 7.1 核心假设

| #   | 假设                                            | 验证方式                          | 证伪条件                           |
| --- | ----------------------------------------------- | --------------------------------- | ---------------------------------- |
| H1  | 以 GAUC 为优化目标能找到比 ots=0.50 更好的配置  | Phase 1 网格搜索                  | 所有 uv 级配置 GAUC_ctr < baseline |
| H2  | CVR tower 的瓶颈在 expert routing 而非 capacity | 2.2 expert gating vs 2.3 capacity | 两者均 < +0.2pp                    |
| H3  | CDOT output_dim 4→8 能保留足够交叉信息          | 3.1 cdot_out8                     | < +0.2pp                           |
| H4  | 实时特征是最后一个大杠杆                        | Phase 4                           | < +0.3pp                           |
| H5  | UV-weighted BCE 能有效缩小 gap_cvr              | 1.3 实验                          | gap_cvr 改善 < 0.3pp               |

### 7.2 风险缓解

| 风险                           | 缓解措施                            |
| ------------------------------ | ----------------------------------- |
| UV-weighted BCE 导致训练不稳定 | 先用小学习率 + 梯度裁剪验证         |
| PLE capacity 升级导致 OOM      | 先在 1 GPU 上验证，逐步扩到 2 GPU   |
| 实时特征延迟                   | 先做离线回放验证，再上线 Flink      |
| 温度校准影响排序               | 在 offline ranking list 上验证 NDCG |

______________________________________________________________________

## 八、里程碑

| 时间    | 里程碑       | 成功标准                                |
| ------- | ------------ | --------------------------------------- |
| Week 2  | Phase 1 完成 | GAUC_cvr ≥ +3.5pp，GAUC_ctr ≥ baseline  |
| Week 5  | Phase 2 完成 | GAUC_cvr ≥ +4.0pp，gap_cvr ≤ 4.0pp      |
| Week 7  | Phase 3 完成 | 确认 CDOT/DCNv2 方向是否有效            |
| Week 10 | Phase 4 完成 | 实时特征 ≥ +0.5pp                       |
| Week 12 | 生产部署     | 在线 A/B 全指标正向，GMV ≥ baseline +1% |

______________________________________________________________________

## 九、与旧路线图的差异

| 维度                      | 旧路线图（v14-optimization-plan.md）       | 本路线图                                                         |
| ------------------------- | ------------------------------------------ | ---------------------------------------------------------------- |
| 优化目标                  | pv 级 auc_cvr                              | **uv 级 GAUC_cvr + GAUC_ctr**                                    |
| Phase 1                   | seq_transformer / cdot_out8 / dcnv2_cross6 | **ots × CTR weight 网格 + GAUC-aware ots 重搜**                  |
| Phase 2                   | 实时特征（Flink）                          | **CVR tower 架构升级（residual / expert / independent bottom）** |
| 数据驱动                  | Phase 2（早期）                            | **Phase 4（后期，模型优化耗尽后）**                              |
| 核心洞察                  | "所有超参 lever 已穷尽"                    | **"超参是以 pv 级 auc 为目标的穷尽，uv 级优化尚未开始"**         |
| 对 PLE capacity 的判断    | "下一步方向"                               | "ots012_plebig 已跑，−0.04pp，**无效**"                          |
| 对 seq_transformer 的判断 | "P0 主攻方向"                              | "已证否 −0.06pp，**放弃 sequence 方向**"                         |
| CDOT 调优                 | 未提及                                     | **Phase 3 重点（output_dim 4→8 信息损失巨大）**                  |

**关键转变**：从"模型容量优化"转向"UV 级优化"。ots 的成功证明了非点击样本的价值，但下一步的瓶颈不在于模型容量（PLE 4x 扩容无效），而在于**如何让非点击样本的梯度更好地服务于用户级别的排序质量**。
