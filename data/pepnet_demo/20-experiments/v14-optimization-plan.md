______________________________________________________________________

## date: 2026-06-26 tags: [experiment, v14, roadmap] status: updated related: \["\[[v14-experiments]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v14+ 优化方案与路线图（dropout 修复验证后修订）

> 基于 v12–v14 共 27+ 实验 + ctr45 线上 A/B + LHUC_PPNet dropout 修复验证

______________________________________________________________________

## 一、核心认知（27+ 个实验的教训）

### 1.1 什么有效、什么无效

| 状态          | 方向                                     | 证据强度 | 机制                                                                                |
| :------------ | :--------------------------------------- | :------: | :---------------------------------------------------------------------------------- |
| ✅ **有效**   | out_task_space_weight=0.01               |  ⭐⭐⭐  | CVR tower 从非点击样本接收弱负信号，离线 +0.18% CVR AUC（修复后），需配合 dropout=0 |
| ✅ **有效**   | CTR weight 放大（3.3→4.5）               |   ⭐⭐   | pv 级正向（+0.10%/+0.04%），但 uv 级负向                                            |
| ✅ **有效**   | Embedding dropout（keep_prob=0.8）       |   ⭐⭐   | 丢失 75/168 embedding → CVR −0.32%（反向证明正则化价值）                            |
| ❌ **已证伪** | LHUC_PPNet dropout on [512,256,128]      |   ⭐⭐   | 修复后 CVR −0.10%，全容量 CVR tower 不需要 dropout                                  |
| ➖ **转中性** | 容量缩减 [256,128] + real dropout=0.1    |   ⭐⭐   | 修复后从 −0.14% 转 +0.08%，上限不足                                                 |
| ❌ 无效       | weight_decay=0.03 on CVR                 |    ⭐    | 不补偿容量损失                                                                      |
| ❌ 无效       | 梯度隔离（isolate）                      |   ⭐⭐   | −1.15% CVR，CVR 信号有价值                                                          |
| ❌ 无效       | 自适应加权（uw/pareto）                  |    ⭐    | 全部负向                                                                            |
| ❌ 无效       | 梯度手术（pcgrad/pcgrad_ctr45/纯pcgrad） |    ⭐    | 全部负向或中性                                                                      |
| ❌ 无效       | 辅助 loss（ctcvr）                       |    ⭐    | 中性                                                                                |

### 1.2 核心发现：out_task_space_weight 与 dropout 在 CVR tower 上互斥

- **out_task_space=0.01** + CVR **dropout=0** → **+0.43%** CVR（修复前，等同全容量）
- **out_task_space=0.01** + CVR **dropout=0.1** → **+0.18%** CVR（修复后，−0.25%）
- **out_task_space=0** + CVR **dropout=0.3** → **−0.10%** CVR（修复后，纯 dropout 有害）

**解释：** out_task_space 的弱监督信号需要 CVR tower 100% 的表征容量。dropout 消耗的容量损失远大于其正则化收益。两者是竞争关系，不是互补关系。

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

### Phase 1（当前，1–2 轮实验）

| 序号 | 实验                       | 内容                                    | 目的                   | 优先级 |
| :--: | :------------------------- | :-------------------------------------- | :--------------------- | :----: |
|  1   | **Config C dropout0**      | out_task_space=0.01 + **CVR dropout=0** | 恢复原始 +0.43% 条件   | **P0** |
|  2   | **C + user-level metrics** | Config C dropout0 + grouped_auc         | 验证 uv 级指标同步提升 | **P0** |
|  3   | **C + ctr45 叠加**         | Config C dropout0 + CTR weight=5.4      | 两机制独立，可叠加     | **P1** |

### Phase 2（参数优化，1 轮实验）

| 序号 | 实验                | 内容                                  | 目的                       | 优先级 |
| :--: | :------------------ | :------------------------------------ | :------------------------- | :----: |
|  4   | out_task_space 扫描 | 0.005/0.02/0.05（CVR dropout=0）      | 寻找最优值                 |   P1   |
|  5   | CTR weight 上限验证 | 5.4–6.0 在 user-level metric 下的表现 | 确认 CTR weight 的安全边界 |   P2   |

### Phase 3（已取消方向）

| ~~原方向~~                                   | ~~理由~~                                  |
| :------------------------------------------- | :---------------------------------------- |
| ~~C + dropout 叠加（原 Phase 1-2）~~         | ❌ 已证伪，out_task_space 与 dropout 互斥 |
| ~~修复后单独测试 dropout（原 Phase 3-7）~~   | ❌ 已测，Config B −0.10% 负向             |
| ~~A/D + dropout 参数扫描（原 Phase 3-8/9）~~ | ❌ 已测，从负转平但上限不足               |

### Phase 4（长期）

| 方向          | 说明                                             |  预计工作量  |
| :------------ | :----------------------------------------------- | :----------: |
| 独立 CVR 模型 | 完全解耦 CVR 预测，不再受多任务干扰              | 高（2–4 周） |
| 特征工程      | 新增 CVR 专属特征（用户近 7 天/30 天转化频次等） | 中（1–2 周） |
| 在线学习      | 基于实时反馈的增量更新                           | 高（4+ 周）  |

______________________________________________________________________

## 四、实验提交顺序建议

```
Round 1（当前）: dropout0 → segdiag → ctr54    # 3 个 config（建议并行提交）
Round 2:          ots0005 → ots002 → ots005       # 参数扫描（依赖 dropout0 结果定向）
```

**Round 1 优先级最高：**

1. **Config C dropout0** — 验证 +0.43% 是否可恢复（out_task_space 回归纯条件）
1. **Config C + grouped_auc** — C 的 uv 级安全性验证，避免 ctr45 覆辙
1. **Config C + CTR weight=5.4** — 两机制独立叠加
