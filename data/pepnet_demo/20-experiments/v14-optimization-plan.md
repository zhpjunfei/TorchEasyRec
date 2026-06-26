______________________________________________________________________

## date: 2026-06-26 tags: [experiment, v14, roadmap] status: updated related: \["\[[v14-experiments]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v14+ 优化方案与路线图（dropout 修复验证后修订）

> 基于 v12–v14 共 27+ 实验 + ctr45 线上 A/B + LHUC_PPNet dropout 修复验证

______________________________________________________________________

## 一、核心认知（27+ 个实验的教训）

### 1.1 什么有效、什么无效

| 状态          | 方向                                     |  证据强度  | 机制                                                             |
| :------------ | :--------------------------------------- | :--------: | :--------------------------------------------------------------- |
| ✅✅ **强效** | out_task=0.02 + dropout=0.1              | ⭐⭐⭐⭐⭐ | ots002 +0.57%，非点击梯度 ≈ 28%，最优 ots 值                     |
| ✅✅ **强效** | out_task=0.05 + dropout=0.1              |  ⭐⭐⭐⭐  | ots005 +0.50%，ots 略过饱和                                      |
| ✅✅ **强效** | out_task=0.01 + dropout=0.3              |  ⭐⭐⭐⭐  | dropout03 +0.41%，高 dropout + ots 梯度补偿 = 协同               |
| ✅ **有效**   | out_task=0.01 + dropout=0.1              |   ⭐⭐⭐   | Config C +0.18%，基线组合                                        |
| ✅ **有效**   | CTR weight 放大（3.3→4.5）               |    ⭐⭐    | pv 级正向（+0.10%/+0.04%），但 uv 级负向                         |
| ❌ **已证伪** | out_task + no dropout 路径（旧结论）     |   ⭐⭐⭐   | dropout0 −0.83% 证伪。无 dropout 时 CVR 过拟合崩塌，ots 无法补偿 |
| ❌ **已修正** | "ots 与 dropout 互斥"（旧结论两轮推翻）  |   ⭐⭐⭐   | 实际关系：**dropout 越高 → CVR 越好**（在 ots 配合下）           |
| ➖ **转中性** | 容量缩减 [256,128] + real dropout=0.1    |    ⭐⭐    | 修复后从 −0.14% 转 +0.08%，上限不足                              |
| ❌ 无效       | weight_decay=0.03 on CVR                 |     ⭐     | 不补偿容量损失                                                   |
| ❌ 无效       | 梯度隔离（isolate）                      |    ⭐⭐    | −1.15% CVR，CVR 信号有价值                                       |
| ❌ 无效       | 自适应加权（uw/pareto）                  |     ⭐     | 全部负向                                                         |
| ❌ 无效       | 梯度手术（pcgrad/pcgrad_ctr45/纯pcgrad） |     ⭐     | 全部负向或中性                                                   |
| ❌ 无效       | 辅助 loss（ctcvr）                       |     ⭐     | 中性                                                             |
| ❌ 无效       | 真 ESMM（use_ctcvr_loss 替换 CVR BCE）   |     ⭐     | −0.11%，CTCVR 梯度被 pCTR 门控                                   |

### 1.2 核心发现：out_task_space × dropout 协同（←推翻旧互斥结论）

**更新（2026-06-26 11:59 — dropout0/ls005/ots005 结果纳入）：**

| 实验               | out_task | CVR dropout |    Δcvr    | 解释                        |
| :----------------- | :------: | :---------: | :--------: | :-------------------------- |
| **ots002** 🚀      |   0.02   |     0.1     |   +0.57%   | 最优 ots 值                 |
| **ots005** 🚀      |   0.05   |     0.1     |   +0.50%   | ots 略过饱和                |
| **dropout03** 🚀   |   0.01   |   **0.3**   |   +0.41%   | 更高 dropout = 更好 CVR     |
| Config C           |   0.01   |     0.1     |   +0.18%   | 基线                        |
| ots0005            |  0.005   |     0.1     |   +0.02%   | ots 过低                    |
| Config B           |    0     |     0.3     |   −0.10%   | 纯 dropout 无 ots → 有害    |
| **dropout0** ❌    |   0.01   |    **0**    | **−0.83%** | 无 dropout → CVR 过拟合崩塌 |
| **dropout0_ls005** |   0.01   |      0      | **−0.74%** | LS 弱补偿无效               |

**机制修正（关键）：**

- 修复前 dropout 未生效（所有 CVR tower 等效 d=0）→ Config C" +0.43%" 实际上是无 dropout 的结果
- 修复后 dropout 真实生效 → 发现 **dropout 不是可选项，而是必须项**
- 无 dropout 时 CVR −0.83%，d=0.3 时 +0.41%。**dropout 越高 → CVR 越好**
- out_task 非点击梯度补偿 dropout 的容量损失，同时 dropout 防止在少量转化样本上过拟合

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

| 实验                        | 结果                                                 | 结论                           |
| :-------------------------- | :--------------------------------------------------- | :----------------------------- |
| out_task 参数扫描 (d=0.1)   | ots0005 +0.02%, ots002 **+0.57%**, ots005 **+0.50%** | ots 最优值 ≈ 0.02              |
| C + dropout=0.3 (dropout03) | **+0.41%**                                           | 高 dropout + ots = 协同        |
| dropout0 (d=0)              | **−0.83%**                                           | ❌ 无 dropout → CVR 过拟合崩塌 |
| dropout0_ls005              | **−0.74%**                                           | ❌ LS 无法补偿 dropout 缺失    |
| 真 ESMM                     | −0.11%                                               | ❌ 证伪                        |

### Phase 2（当前，1 轮实验）

| 序号 | 实验                            | 内容                                               | 目的                             | 优先级 |
| :--: | :------------------------------ | :------------------------------------------------- | :------------------------------- | :----: |
|  1   | **ots002_uv**                   | ots002 + grouped_auc { grouping_key: "mmb_id" }    | uv 级指标验证（user-level GAUC） | **P0** |
|  2   | **dropout03_uv**                | dropout03 + grouped_auc { grouping_key: "mmb_id" } | uv 级指标验证（user-level GAUC） | **P0** |
|  3   | **dropout04** (ots=0.02, d=0.4) | 在最优 ots 下验证 dropout 越高越好趋势             | dropout 上限探索                 | **P1** |
|  4   | **ots002_ctr54_uv**             | ots002 + CTR w=5.4 + mmb_id GAUC                   | 两机制独立叠加 + uv 验证         | **P1** |

### Phase 3（参数精调）

| 序号 | 实验                | 内容                                  | 目的                       | 优先级 |
| :--: | :------------------ | :------------------------------------ | :------------------------- | :----: |
|  5   | ots 更细扫描        | 0.015/0.025（基于 ots002 邻域）       | 精确最优 ots 值            |   P1   |
|  6   | dropout+ots 网格    | d=0.2/0.4/0.5 × ots=0.02/0.03         | 探索交互面最优组合         |   P2   |
|  7   | CTR weight 上限验证 | 5.4–6.0 在 user-level metric 下的表现 | 确认 CTR weight 的安全边界 |   P2   |

### Phase 4（长期）

| 方向          | 说明                                             |  预计工作量  |
| :------------ | :----------------------------------------------- | :----------: |
| 独立 CVR 模型 | 完全解耦 CVR 预测，不再受多任务干扰              | 高（2–4 周） |
| 特征工程      | 新增 CVR 专属特征（用户近 7 天/30 天转化频次等） | 中（1–2 周） |
| 在线学习      | 基于实时反馈的增量更新                           | 高（4+ 周）  |

______________________________________________________________________

## 四、实验提交顺序建议

```
Round 1（当前）: ots002_uv → dropout03_uv → dropout04    # uv 验证 + 探索
Round 2:          ots002_ctr54_uv → ots015 → ots025       # 叠加实验 + 细扫描
```

**Round 1 优先级最高（ots005 已跑完，结果 +0.50%）：**

1. **ots002_uv** — 最优 CVR config（+0.57%）的 user-level GAUC 安全性验证
1. **dropout03_uv** — 次优 config（+0.41%）的 user-level GAUC 安全性验证
1. **dropout04** (ots=0.02, d=0.4) — 验证 dropout 越高越好趋势，探索上限
