# PEPNet Baseline v15 优化方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 基于对 `home_flow_2604_v15_baseline.config` 的深度分析，给出可落地的业务优化思路和技术优化方案。

**Architecture:** 当前模型 = DCNv2(特征交叉) + CDOT(意图压缩) + PLE(分层专家) + LHUC_PPNet(任务个性化) + 425个特征(179 ID + 44 combo + 8 seq + 194 raw)。95%+ 参数在 embedding 层。

**Tech Stack:** TorchEasyRec, Protobuf config, ODPS dataset, ZCH online cache, DIN attention, AdamW optimizer

## Global Constraints

- 保持 pre-encoded pipeline 不变（配置驱动的特征工程）
- 不引入新的外部依赖
- 所有优化必须可实验验证（A/B test 友好）
- 线上推理延迟增加不能超过 5%
- 训练 epoch 不超过 1（当前配置）

______________________________________________________________________

## 洞察总结

### 业务洞察

1. **特征工程是真正的护城河**：425 个特征中，141 个 ratio 特征（15天/60天行为统计）、44 个 combo 交叉特征、14 个 ZCH 在线缓存特征构成了核心信号
1. **搜索场景的特殊性**：`search_weight` sample_weight、`chaprice_click_50_seq` 价格区间序列、`f_req_page/f_req_domain` 请求上下文特征
1. **CVR 漏斗建模精细**：task_space_indicator + CTCVR loss + CVR shortcut 三层约束
1. **用户-商品交叉特征是组合爆炸**：login_city(4360) × cate_id_path(200K) = 8.7亿组合，ZCH 缓存是必须的

### 技术洞察

1. **参数分布极度不均**：Embedding 1.3B (95%+) vs Dense 15M (5%)
1. **CDOT 4 维瓶颈可疑**：从 64 维压缩到 4 维，压缩率 8x
1. **ZCH eviction_interval=2 过高频**：2 个 step 就淘汰，可能导致 embedding 震荡
1. **8 个 DIN encoder 共享相同结构**：[128, 64] attention MLP，可能存在冗余
1. **EPNet/PPNet/LHUC 调制链路过长**：domain → EPNet → PLE → PPNet → Tower，信息经过 4 次调制

______________________________________________________________________

## 优化方案

### 优化1：CDOT 瓶颈扩容实验（高优先级）

**问题**：CDOT 将 domain 特征（mmb_id 32dim + item_id 32dim = 64dim）压缩到 4dim，压缩率 8x。这相当于把用户+商品的完整意图压缩到 4 个数字。

**假设**：4 维不足以表达 domain 组的意图，信息瓶颈导致 PLE 和 PPNet 接收的信号质量下降。

**实验设计**：

```
Baseline: output_dim=4
Exp1:   output_dim=8
Exp2:   output_dim=16
Exp3:   output_dim=32（去掉压缩，直接拼接）
```

**预期**：如果 output_dim=8 就有显著提升，说明 4 维确实是瓶颈。如果 output_dim=32 也差不多，说明 CDOT 本身可能是冗余组件。

**风险**：output_dim 增大 → CDOT 输出 concat_dim 增大 → 后续 PLE 输入维度增大 → 参数量和延迟增加。

**验证指标**：CTR-AUC、CVR-AUC、推理延迟（ms）、模型参数量。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — cdot.output_dim

______________________________________________________________________

### 优化2：ZCH Eviction Interval 调优（高优先级）

**问题**：14 个 ZCH 特征的 eviction_interval=2，意味着每 2 个 training step 就评估一次淘汰。对于 online embedding 来说，2 太激进。

**假设**：高频 evict 导致 hot item 的 embedding 频繁重建，训练不稳定，尤其是对长尾 item 不利。

**实验设计**：

```
Baseline: eviction_interval=2
Exp1:   eviction_interval=10
Exp2:   eviction_interval=50
Exp3:   eviction_interval=100（接近离线训练）
```

**阈值过滤函数** `dynamic_threshold_filter(x, 3.0)` 保持不变，只调 eviction 频率。

**风险**：eviction 频率降低 → ZCH 内存占用增加。需要评估 250 万 × 32 × 4 bytes ≈ 320MB 的缓存是否可接受。

**验证指标**：训练 loss 曲线稳定性、收敛速度、长尾 item 的 AUC 提升。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — 所有 zch.eviction_interval

______________________________________________________________________

### 优化3：特征重要性消融实验（中优先级）

**问题**：425 个特征中，有多少是真正有区分度的？很多特征可能是历史迭代的遗留，没有经过系统性的消融。

**假设**：去掉 bottom 30% 的特征（按训练后的 feature importance 排序），模型性能下降不超过 0.1%，但推理延迟降低 15%。

**实验设计**：

1. 训练 baseline 模型
1. 对每个 ID 特征，计算其对 AUC 的贡献（通过 permutation importance 或 embedding norm 作为 proxy）
1. 按贡献度排序，移除 bottom 30%
1. 重新训练，对比指标

**重点关注**：

- **低基数特征**：os_type (hash=40)、week_day (hash=70)、item_type (hash=50) — 这些特征的 embedding 容量极小，可能只是 noise
- **冗余 ratio 特征**：141 个 ratio 特征中，`gender__ratio_click_exposure_15d` 和 `gender__ratio_conversion_click_15d` 高度相关
- **combo 特征的必要性**：44 个 combo 特征中，`login_city_x_*` 系列有 15 个，是否都需要？

**风险**：特征移除是离散选择，可能错过"单个特征无用但组合有用"的情况。

**验证指标**：AUC 变化、特征数量、推理延迟、模型大小。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — 删除/注释不需要的 feature_configs

______________________________________________________________________

### 优化4：DIN Encoder 共享参数（中优先级）

**问题**：8 个 DIN encoder 结构完全相同（[128, 64] attention MLP），只是输入不同（click_10_seq, click_50_seq, conversion_5_seq 等）。

**假设**：不同行为类型的注意力机制应该有差异，但当前共享相同结构。或者反过来——它们确实应该共享，因为注意力机制是通用的。

**两个方向**：

**方向 A：参数共享**

- 所有 8 个序列共用一个 DIN encoder
- 通过 sequence_type embedding 区分
- 参数量从 8×100K ≈ 800K 降到 100K

**方向 B：差异化设计**

- CTR 相关序列（click_10, click_50）用更深的 attention
- CVR 相关序列（conversion_5, conversion_20）用更浅的 attention
- 因为转化行为的信号更强，可能需要更少的层就能捕捉

**风险**：方向 A 可能丢失序列类型的特异性；方向 B 增加配置复杂度。

**验证指标**：参数量、训练速度、各序列的 attention weight 分布。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — sequence_encoders 配置
- `tzrec/modules/` — DIN encoder 实现（如果需要方向 B）

______________________________________________________________________

### 优化5：LHUC 调制链路的梯度冲突监控（中优先级）

**问题**：当前代码已有 gradient hooks 收集 CTR/CVR 梯度余弦相似度，但没有在 training loop 中使用这个信息。

**假设**：如果 CTR 和 CVR 的梯度余弦相似度持续为负（冲突），说明 EPNet→PLE→PPNet 的主干在为两个任务学习通用表示时存在根本性冲突。

**实验设计**：

1. 在 training loop 中监控 gradient cosine similarity
1. 如果平均余弦相似度 < -0.3（强冲突），启用以下策略之一：
   - **策略 A**：增加 PPNet 的 task-specific 容量（增大 ppnet_hidden_units）
   - **策略 B**：降低 EPNet 的调制强度（减小 LHUC gate 的 learning rate）
   - **策略 C**：增加 share expert 的数量（从 2 增加到 4）
1. 对比不同策略下的 AUC 和梯度冲突程度

**风险**：梯度冲突不一定是坏事——适度的冲突说明任务确实在学习不同的表示。

**验证指标**：梯度余弦相似度分布、CTR/CVR AUC、训练稳定性。

**文件修改**：

- `tzrec/models/pepnet_dcn_ple.py` — 在 training loop 中添加梯度冲突检测和自适应调整

______________________________________________________________________

### 优化6：CTCVR Loss 的权重搜索（高优先级）

**问题**：当前配置 `use_ctcvr_loss: true`，但 CTR weight=4.5，CVR weight=1.0。这个权重比是通过网格搜索得到的吗？还是经验值？

**假设**：CTR 和 CVR 的损失权重没有经过充分搜索，4.5:1.0 可能不是最优比。

**实验设计**：

```
网格搜索 weight 比：
- 1:1, 2:1, 3:1, 4:1, 4.5:1, 5:1, 8:1, 10:1, 15:1
```

同时搜索：

- CTCVR loss 的 temperature 参数（如果用了 temperature-scaled CTCVR）
- CVR sample_weight 的缩放因子（当前用 search_weight）

**风险**：权重搜索需要在同一个数据集上跑多次训练，计算成本高。

**验证指标**：CVR-AUC（主要关注，因为 CVR 通常更难优化）、CTR-AUC、Business Metrics（GMV/Revenue）。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — task_towers.weight

______________________________________________________________________

### 优化7：特征分桶策略优化（低优先级但低成本）

**问题**：`fg_mode: FG_BUCKETIZE` 表示特征分桶，但不知道具体的分桶策略。

**假设**：部分连续特征（如 current_price）的分桶边界可能不是最优的。

**实验设计**：

1. 检查 raw_feature 中连续特征的分桶边界（boundaries）
1. 对高基数特征（如 cate_id_path, hash=200K），考虑使用 hash embedding 代替 lookup table
1. 对低基数特征（如 os_type, hash=40），直接使用 one-hot 可能比 embedding 更好

**风险**：分桶策略改变可能影响线上推理的一致性。

**验证指标**：各特征对 AUC 的边际贡献。

**文件修改**：

- `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config` — raw_feature.boundaries

______________________________________________________________________

## 实验优先级矩阵

| 优化                 | 预期收益 | 实施成本 | 风险 | 优先级 |
| -------------------- | -------- | -------- | ---- | ------ |
| 1. CDOT 瓶颈扩容     | 高       | 低       | 低   | P0     |
| 2. ZCH Eviction 调优 | 中       | 低       | 低   | P0     |
| 6. CTCVR 权重搜索    | 中       | 中       | 中   | P0     |
| 3. 特征消融实验      | 中       | 中       | 中   | P1     |
| 4. DIN Encoder 共享  | 低       | 中       | 低   | P1     |
| 5. 梯度冲突监控      | 低       | 低       | 低   | P1     |
| 7. 分桶策略优化      | 低       | 低       | 低   | P2     |

______________________________________________________________________

## 推荐的实验顺序

```
Week 1: 优化6（权重搜索）+ 优化1（CDOT扩容）
  → 这两个改动最小，见效最快，可以并行做

Week 2: 优化2（ZCH调优）+ 优化5（梯度监控）
  → 需要观察训练稳定性，适合放在第二位

Week 3: 优化3（特征消融）
  → 需要完整的消融实验流程，耗时最长

Week 4: 优化4（DIN共享）+ 优化7（分桶优化）
  → 作为后续的精细化优化
```

______________________________________________________________________

## 关键风险与缓解

1. **CDOT 扩容可能增加延迟** → 先在小 batch 上测延迟，再决定是否全量
1. **ZCH eviction 降低可能 OOM** → 监控 GPU memory 使用，设置上限
1. **特征消融可能破坏线上一致性** → 先在离线验证，再逐步上线
1. **CTCVR 权重搜索计算成本高** → 先用 1/10 的数据做 grid search

______________________________________________________________________

## 总结

**核心认知**：这个模型的 95%+ 参数在 embedding 层，架构贡献是边际的。优化应该优先集中在：

1. **特征质量**（消融低价值特征、优化 combo 特征）
1. **训练稳定性**（ZCH eviction、CTCVR 权重）
1. **架构瓶颈**（CDOT 4 维是否真的够用）

**Karpathy 式的一句话**： "Everything else is just efficiency" — 你现在拥有的不是一个复杂的 PEPNet 架构，而是一个精心构造的 425 维特征向量 + 一个用 LHUC 调制的 routing 机制。把特征工程做好，比折腾架构更有效。
