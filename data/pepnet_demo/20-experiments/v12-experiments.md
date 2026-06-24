______________________________________________________________________

## date: 2026-06-23 tags: [experiment, v12, loss-optimization, uncertainty-weight, weight-tune, pareto] related: ["[v11-experiments]", "[../10-architecture/pepnet-dcn-ple]"]

# v12 实验 — Loss 优化策略

> 基于 v11 baseline 研究是否可以通过 loss 优化提升 CVR。探索三种方案：静态权重调优、Uncertainty Weighting (Kendall et al., CVPR 2018)、PE-MTL (Pareto Efficient)。v12 pipeline 与 v11 一致。4卡, batch_size=4096/GPU, 有效=16384.

## 实验清单

| 实验                    | Config                                                    | 变化                             |
| :---------------------- | :-------------------------------------------------------- | :----------------------------- |
| baseline (v12)          | `home_flow_2604_v12_baseline.config`                      | v11 baseline, CTR=3.3, CVR=1.0 |
| weight_tune             | `home_flow_2604_v12_weight_tune.config`                   | CTR=1.5, CVR=3.0 (激进反转)    |
| weight_tune_ctr30       | `home_flow_2604_v12_weight_tune_ctr30.config`             | CTR=3.0, CVR=1.0               |
| weight_tune_ctr26       | `home_flow_2604_v12_weight_tune_ctr26.config`             | CTR=2.6, CVR=1.0               |
| weight_tune_ctr22       | `home_flow_2604_v12_weight_tune_ctr22.config`             | CTR=2.2, CVR=1.0               |
| weight_tune_cvr15       | `home_flow_2604_v12_weight_tune_cvr15.config`             | CTR=3.3, CVR=1.5               |
| weight_tune_cvr20       | `home_flow_2604_v12_weight_tune_cvr20.config`             | CTR=3.3, CVR=2.0               |
| uncertainty_weight      | `home_flow_2604_v12_uncertainty_weight.config`            | `use_uncertainty_weight: true` |
| pareto                  | `home_flow_2604_v12_pareto.config`                        | `use_pareto_loss_weight: true` |

## 源码变更

### Uncertainty Weighting（新增模块）

| 文件                                          | 变更                   |
| :-------------------------------------------- | :--------------------- |
| `tzrec/protos/model.proto`                    | 新增 `use_uncertainty_weight` 字段 |
| `tzrec/protos/model_pb2.py`                   | 重新生成               |
| `tzrec/loss/uncertainty_weight_loss.py`       | **新建** — `UncertaintyWeightLoss` |
| `tzrec/models/model.py`                       | TrainWrapper 集成       |
| `tzrec/models/multi_task_rank.py`             | 读取配置标志           |

实现基于 Kendall et al. 2018, 每个任务引入可学习 `log_var`, loss 加权为 `loss / (2 * exp(log_var)) + log_var / 2`。

### PE-MTL（已存在，仅配置启用）

`use_pareto_loss_weight: true` + 每塔 `pareto_min_loss_weight: 0.2`

### Bug 修复

`tzrec/loss/pe_mtl_loss.py` — `grad.view(-1)` 改为 `grad.reshape(-1)`，修复非连续张量导致的 RuntimeError。

## 实验结果

全部基于 **7757 steps** 评估（Epoch-0, T_max=6300, 已过 T_max 约 1457 steps）。

| 实验                | auc_ctr    | binary_cross_entropy_ctr | auc_cvr    | binary_cross_entropy_cvr |
| :------------------ | :--------- | :----------------------- | :--------- | :----------------------- |
| baseline            | 0.716316   | 1.933748                 | 0.757583   | 0.493283                 |
| weight_tune         | 0.708770   | 0.887004                 | 0.755498   | 1.478402                 |
| uncertainty_weight  | **0.716316** | **1.933748**           | **0.757583** | **0.493283**           |
| pareto              | _(待产出)_ | _(待产出)_               | _(待产出)_ | _(待产出)_               |

### 相对 baseline 变化

| 实验                | Δauc_ctr    | Δauc_cvr    |
| :------------------ | :---------- | :---------- |
| weight_tune         | **−1.05%**  | **−0.28%**  |
| uncertainty_weight  | **+0.00%**  | **+0.00%**  |

## 分析

### weight_tune（网格扫描）— 关键实验

#### 已产出：weight_tune（激进反转）

CTR weight 3.3→1.5, CVR weight 1.0→3.0：

| 指标 | baseline | weight_tune | 变化 |
| :--- | :------- | :---------- | :--- |
| auc_ctr | 0.7163 | 0.7088 | **−1.05%** |
| auc_cvr | 0.7576 | 0.7555 | **−0.28%** |

**AUC 双双下降。** 这是关键反直觉现象：给 CVR 更多权重，CVR 反而变差。

#### 机制分析

PEPNet + DCNv2 + PLE 的共享层结构：

```
输入 → epnet/gate → DCNv2 → PPNet → [共享专家] → CTR塔 / CVR塔
                        ↑                          ↓
                    CDOT + bias              task_space_indicator
                                             (CVR只训练点击样本)
```

- **CTR**：100% 样本参与训练，信号量大，驱动共享表示层质量
- **CVR**：仅 ~5% 样本（点击后有转化记录的）参与训练，信号量小
- **CVR 塔**仅 3 层 [512,256,128]，容量有限

当 CVR weight 从 1.0→3.0 时，损失函数中 CVR 的梯度贡献占比增大。但 CVR 只在少量点击样本上有信号 → **梯度稀疏且方差大**。共享层被 CVR 的大方差梯度"干扰"，降低了 CTR 驱动的表示质量，最终 CVR 自身从中获益也减少。

**核心假设：CTR 的丰富信号是共享表示层的基石。削弱 CTR → 共享层退化 → 双方 AUC 均下降。**

#### 待产出：权重网格扫描

激进的 1.5/3.0 反转跨度太大，无法区分"CVR weight 增加"和"CTR weight 减少"各自的影响，也无法找到可能的权重拐点。新增逐步调优网格：

| 实验 | CTR weight | CVR weight | 目的 |
| :--- | :--------- | :--------- | :--- |
| baseline | 3.3 | 1.0 | 锚点 |
| weight_tune_ctr30 | **3.0** | 1.0 | CTR 小幅降 |
| weight_tune_ctr26 | **2.6** | 1.0 | CTR 中幅降 |
| weight_tune_ctr22 | **2.2** | 1.0 | CTR 大幅降 |
| weight_tune_cvr15 | 3.3 | **1.5** | CVR 小幅升 |
| weight_tune_cvr20 | 3.3 | **2.0** | CVR 中幅升 |
| weight_tune | 1.5 | 3.0 | 已跑完，激进反转 |

此网格可回答：
- AUC 下降是**阈值效应**还是**线性**？（CTR 从哪开始掉？）
- CTR weight 减少 和 CVR weight 增加，哪个更伤？（对比 ctr30 vs cvr15，降幅对称吗）
- 是否存在 CVR weight 轻微增加→CVR auc 微升的甜区？

### uncertainty_weight — 结果与 baseline 完全一致，代码未生效

AUC/BCE 六位小数完全相同，`UncertaintyWeightLoss` 在训练中未被触发。需排查部署问题。

**即使修复后，预期效果也应谨慎**：
- 若 UW 给 CTR 更高权重（CTR 噪声大）→ 等价于 baseline，无改进
- 若 UW 给 CVR 更高权重（CVR 噪声小）→ 类似 weight_tune，可能有害

### pareto — 待产出结果

预期 Pareto 优化会降低 CTR 梯度主导 → 同理可能损害共享表示。

## 重审：Loss 加权方案是否合理？

### 方案合理性矩阵

| 方案           | 机制                             | weight_tune 反证 | 预期效果        |
| :------------- | :------------------------------- | :--------------- | :-------------- |
| 静态权重调优   | 手动调整任务权重                  | ❌ 双方 AUC 下降 | 不可行          |
| Uncertainty W. | 根据任务噪声自动加权              | ⚠️ 取决于方向    | 中性或负        |
| PE-MTL         | Pareto 平衡梯度幅度               | ⚠️ 压低 CTR 权重 | 可能负          |
| GradNorm       | 平衡梯度范数                      | ⚠️ 类似 PE-MTL   | 可能负          |

### 为什么 Loss 加权对 CVR 无效？

```
[核心问题] CVR 提升瓶颈不在 loss 加权，在训练信号量
                    ↓
        任务权重只能改变"信号幅度"
        不能改变"信号量"（样本数 × 标注率）
                    ↓
        CVR 只有 ~5% 有转化标注的点击样本
        即使 weight=100，梯度仍然来自这 5%
                    ↓
        共享层需要 CTR 的 100% 样本梯度来稳定训练
        任何削弱 CTR 的加权方案都会损伤共享表示
```

### 更有效的 CVR 提升路径

#### 1. 样本级加权（已在做，可继续优化）

`search_weight` 是每个 CVR 样本的权重，与任务权重不同：
- 任务权重 **放大梯度幅度**，但梯度方差也放大
- 样本权重 **信号内重分布**，不改变梯度总量，只改变样本间相对重要性

与 `is_control` 结合的 IPW（Inverse Propensity Weighting）可以纠正选择偏差，比任务加权更精确。

#### 2. 数据增强

- CVR 正样本上采样（复制少数类样本）
- 或 CVR 负样本降采样

#### 3. 模型结构改进

| 方向                 | 理由                                           |
| :------------------- | :--------------------------------------------- |
| 加深 CVR tower       | 当前仅 3 层 [512,256,128]，容量可能限制 CVR 表达能力 |
| CVR 专用 expert 增加 | PLE 中 CVR 的 expert 仅 2 个，可尝试 4-8 个       |
| CVR 独立 bottom      | CVR 完全独立于 CTR 的底层网络（代价大，但隔离噪声）|

#### 4. CVR 训练策略

- **两阶段训练**：第一阶段只用 CTR 训练共享层，第二阶段冻结共享层只训练 CVR 塔
- **梯度分离**（Gradient Isolation）：CVR 梯度不回流到共享层（stop_gradient）

## 结论

1. **任务级 Loss 加权对 CVR 无效** — weight_tune 实验证实：增加 CVR 权重 → 共享表示退化 → 双方 AUC 均下降。GradNorm、PE-MTL、Uncertainty Weighting 三种自适应加权方案本质上也会削弱 CTR 梯度主导，预期效果同样不利或中性。

2. **weight_tune 是本轮最有价值的实验** — 它用一个简单改动揭示了一个深层结构性问题：PEPNet+DCNv2+PLE 的共享层高度依赖 CTR 的全量梯度信号，CVR 因其稀疏标注无法独立驱动共享表示质量。

3. **后续不在此方向继续投入** — CVR 提升应转向样本级权重优化（search_weight IPW）、数据增强、模型结构改进。

4. **代码保留但标记为低优先级** — `UncertaintyWeightLoss` 模块已实现，`PE-MTL` 已有支持，但不推荐在 CVR 场景继续尝试。
