______________________________________________________________________

## date: 2026-06-26 tags: [experiment, v14, roadmap] status: updated related: \["\[[v14-experiments]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v14+ 优化方案与路线图（dropout 修复验证后修订）

> 基于 v12–v14 共 27+ 实验 + ctr45 线上 A/B + LHUC_PPNet dropout 修复验证

______________________________________________________________________

## 一、核心认知（27+ 个实验的教训）

### 1.1 什么有效、什么无效

| 状态          | 方向                                     |  证据强度  | 机制                                                                     |
| :------------ | :--------------------------------------- | :--------: | :----------------------------------------------------------------------- |
| ✅✅ **强效** | out_task_space=0.02 + dropout=0.1        | ⭐⭐⭐⭐⭐ | ots002 离线 +0.57% CVR，非点击梯度比例 ≈ 28%，最优 ots 值                |
| ✅✅ **强效** | out_task_space=0.01 + dropout=0.3        |  ⭐⭐⭐⭐  | dropout03 离线 +0.41%，out_task 提供梯度补偿，dropout 防过拟合，两者协同 |
| ✅ **有效**   | out_task_space_weight=0.01 + dropout=0.1 |   ⭐⭐⭐   | Config C +0.18%，基线组合                                                |
| ✅ **有效**   | CTR weight 放大（3.3→4.5）               |    ⭐⭐    | pv 级正向（+0.10%/+0.04%），但 uv 级负向                                 |
| ❌ **已证伪** | out_task_space 与 dropout 互斥（旧结论） |   ⭐⭐⭐   | dropout03 +0.41% 证伪此结论。实际为协同关系                              |
| ➖ **转中性** | 容量缩减 [256,128] + real dropout=0.1    |    ⭐⭐    | 修复后从 −0.14% 转 +0.08%，上限不足                                      |
| ❌ 无效       | weight_decay=0.03 on CVR                 |     ⭐     | 不补偿容量损失                                                           |
| ❌ 无效       | 梯度隔离（isolate）                      |    ⭐⭐    | −1.15% CVR，CVR 信号有价值                                               |
| ❌ 无效       | 自适应加权（uw/pareto）                  |     ⭐     | 全部负向                                                                 |
| ❌ 无效       | 梯度手术（pcgrad/pcgrad_ctr45/纯pcgrad） |     ⭐     | 全部负向或中性                                                           |
| ❌ 无效       | 辅助 loss（ctcvr）                       |     ⭐     | 中性                                                                     |
| ❌ 无效       | 真 ESMM（use_ctcvr_loss 替换 CVR BCE）   |     ⭐     | −0.11%，CTCVR 梯度被 pCTR 门控                                           |

### 1.2 核心发现：out_task_space × dropout 协同（←推翻旧互斥结论）

**更新（2026-06-26）：**

| 实验             | out_task | CVR dropout |  Δcvr  | 解释                             |
| :--------------- | :------: | :---------: | :----: | :------------------------------- |
| **ots002** 🚀    |   0.02   |     0.1     | +0.57% | 非点击梯度 ≈ 28%，最优 ots 值    |
| **dropout03** 🚀 |   0.01   |     0.3     | +0.41% | 高 dropout + ots 梯度补偿 = 协同 |
| Config C         |   0.01   |     0.1     | +0.18% | 基线组合                         |
| Config B         |    0     |     0.3     | −0.10% | 纯 dropout 无 ots → 有害         |
| ots0005          |  0.005   |     0.1     | +0.02% | ots 过低，信号不足               |

**机制解释：** out_task_space 的非点击梯度信号增加了有效样本量，使 dropout 的容量损失被补偿。不带 ots 的纯 dropout（Config B −0.10%）因为转化样本太少而过度正则化。带 ots 时，非点击梯度提供了足够的训练信号来填充被 dropout 丢弃的容量，同时 dropout 减少了少数转化样本上的过拟合。两者是**互补关系**，不是竞争关系。

### 1.3 ctr45 线上 A/B 的关键教训

| 发现                                          | 影响                                     |
| :-------------------------------------------- | :--------------------------------------- |
| 离线 AUC（pv 级）不能预测 uv 级指标           | **需要 user-level metrics 纳入离线评估** |
| CTR weight 放大改变曝光分配策略               | 高意向用户曝光集中，低意向用户被忽略     |
| pv_cvr +4.39% 但 uv_ctr −2.96%, uv_cvr −1.22% | 离线评估体系存在结构性 gap               |

______________________________________________________________________

## 二、离线评估体系改进

### 2.1 新增 user-level metrics

在 eval pipeline 中增加按 user 聚合的评估指标：

```python
# 伪代码：offline user-level metric
user_predictions = group_by(predictions, by="user_id")
user_labels = group_by(labels, by="user_id")

# user-weighted AUC
user_auc = auc_weighted(user_predictions, user_labels,
                        weights=1/log(user_freq))  # 低频用户高权重

# user coverage
coverage_gini = gini_coefficient(impressions_per_user)
```

### 2.2 推荐配置

| 组件              | 建议                                           | 优先级 |
| :---------------- | :--------------------------------------------- | :----- |
| `grouped_auc`     | 按 lifecycle_tags 分组（已有 config）          | P0     |
| user-weighted BCE | 对低频用户 impression 施加 loss 重加权         | P1     |
| 覆盖度指标        | Gini 系数、unique users reached 纳入 eval 报告 | P1     |
| 长期              | 离线模拟 uv 级指标（rerank 场景下）            | P2     |

______________________________________________________________________

## 三、实验路线图（修复后修订）

### Phase 1（✅ 已完成 — 2026-06-26）

| 实验                        | 结果                                       | 结论               |
| :-------------------------- | :----------------------------------------- | :----------------- |
| out_task_space 参数扫描     | ots0005 +0.02%, ots002 +0.57%, ots005 待跑 | ots=0.02 最优      |
| C + dropout=0.3 (dropout03) | **+0.41%**                                 | ots × dropout 协同 |
| 真 ESMM                     | −0.11%                                     | ❌ 证伪            |

### Phase 2（当前，1 轮实验）

| 序号 | 实验                             | 内容                            | 目的              | 优先级 |
| :--: | :------------------------------- | :------------------------------ | :---------------- | :----: |
|  1   | **ots005**（out_task=0.05）      | CVR dropout=0.1, ots=0.05       | 确认 ots 上限边界 | **P0** |
|  2   | **ots002 + segdiag**             | ots002 + grouped_auc metrics    | uv 级安全性验证   | **P0** |
|  3   | **dropout03 + segdiag**          | dropout03 + grouped_auc metrics | uv 级安全性验证   | **P1** |
|  4   | **ots002 + CTR w=5.4 + segdiag** | 两机制独立叠加，带 uv 安全验证  | 机制叠加验证      | **P1** |

### Phase 3（参数精调）

| 序号 | 实验                | 内容                                  | 目的                       | 优先级 |
| :--: | :------------------ | :------------------------------------ | :------------------------- | :----: |
|  5   | ots 更细扫描        | 0.015/0.025（基于 ots002 邻域）       | 精确最优 ots 值            |   P1   |
|  6   | dropout 参数扫描    | dropout=0.2/0.4 + ots=0.02            | 探索 ots × dropout 交互面  |   P2   |
|  7   | CTR weight 上限验证 | 5.4–6.0 在 user-level metric 下的表现 | 确认 CTR weight 的安全边界 |   P2   |

### Phase 4（长期）

### Phase 4（长期）

| 方向          | 说明                                             |  预计工作量  |
| :------------ | :----------------------------------------------- | :----------: |
| 独立 CVR 模型 | 完全解耦 CVR 预测，不再受多任务干扰              | 高（2–4 周） |
| 特征工程      | 新增 CVR 专属特征（用户近 7 天/30 天转化频次等） | 中（1–2 周） |
| 在线学习      | 基于实时反馈的增量更新                           | 高（4+ 周）  |

______________________________________________________________________

## 四、实验提交顺序建议

```
Round 1（当前）: ots005 → ots002_segdiag → dropout03_segdiag    # 2+1 个 config
Round 2:          ots002_ctr54_segdiag → ots015 → ots025          # 叠加实验 + 细扫描
```

**Round 1 优先级最高：**

1. **ots005** — 确认 ots=0.05 是否已经过饱和（边界验证）
1. **ots002 + segdiag** — 最优 CVR config 的 uv 级安全性验证
1. **dropout03 + segdiag** — 次优 config 的 uv 级安全性验证
1. **ots002 + CTR w=5.4 + segdiag** — 两机制叠加，确认是否正正交
