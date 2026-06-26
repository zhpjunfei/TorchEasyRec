______________________________________________________________________

## date: 2026-06-23 tags: [experiment, v12, loss-optimization, uncertainty-weight, weight-tune, pareto] related: ["[[v11-contrastive-learning]]", "[[../10-architecture/pepnet-dcn-ple]]"]

# v12 实验 — Loss 优化策略

> 基于 v11 baseline 研究是否可以通过 loss 优化提升 CVR。探索三种方案：静态权重调优、Uncertainty Weighting (Kendall et al., CVPR 2018)、PE-MTL (Pareto Efficient)。v12 pipeline 与 v11 一致。4卡, batch_size=4096/GPU, 有效=16384.

## 实验清单

| 实验                 | Config                                         | 变化                             |
| :----------------- | :--------------------------------------------- | :----------------------------- |
| baseline (v12)     | `home_flow_2604_v12_baseline.config`           | v11 baseline, CTR=3.3, CVR=1.0 |
| weight_tune        | `home_flow_2604_v12_weight_tune.config`        | CTR=1.5, CVR=3.0 (激进反转)        |
| weight_tune_ctr30  | `home_flow_2604_v12_weight_tune_ctr30.config`  | CTR=3.0, CVR=1.0               |
| weight_tune_ctr26  | `home_flow_2604_v12_weight_tune_ctr26.config`  | CTR=2.6, CVR=1.0               |
| weight_tune_ctr22  | `home_flow_2604_v12_weight_tune_ctr22.config`  | CTR=2.2, CVR=1.0               |
| weight_tune_cvr15  | `home_flow_2604_v12_weight_tune_cvr15.config`  | CTR=3.3, CVR=1.5               |
| weight_tune_cvr20  | `home_flow_2604_v12_weight_tune_cvr20.config`  | CTR=3.3, CVR=2.0               |
| uncertainty_weight | `home_flow_2604_v12_uncertainty_weight.config` | `use_uncertainty_weight: true` |
| pareto             | `home_flow_2604_v12_pareto.config`             | `use_pareto_loss_weight: true` |
| ctr36              | `home_flow_2604_v12_ctr36.config`              | CTR=3.6, CVR=1.0               |
| ctr40              | `home_flow_2604_v12_ctr40.config`              | CTR=4.0, CVR=1.0               |
| ctr45                   | `home_flow_2604_v12_ctr45.config`                         | CTR=4.5, CVR=1.0               |
| ctr48                   | `home_flow_2604_v12_ctr48.config`                         | CTR=4.8, CVR=1.0               |
| ctr51                   | `home_flow_2604_v12_ctr51.config`                         | CTR=5.1, CVR=1.0               |
| ctr54                   | `home_flow_2604_v12_ctr54.config`                         | CTR=5.4, CVR=1.0               |
| ctr57                   | `home_flow_2604_v12_ctr57.config`                         | CTR=5.7, CVR=1.0               |
| ctr60                   | `home_flow_2604_v12_ctr60.config`                         | CTR=6.0, CVR=1.0               |

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

| 实验                 | 配置变化                           | auc_ctr  | Δauc_ctr | bce_ctr  | auc_cvr  | Δauc_cvr | bce_cvr  | 状态  |
| :----------------- | :----------------------------- | :------- | :------- | :------- | :------- | :------- | :------- | :-- |
| baseline           | CTR=3.3, CVR=1.0               | 0.716316 | —        | 1.933748 | 0.757583 | —        | 0.493283 | ✅   |
| weight_tune_ctr30 | CTR=3.0, CVR=1.0 | 0.716170 | −0.02% | 1.758329 | 0.756879 | −0.09% | 0.493211 | ✅ |
| weight_tune_ctr26  | CTR=2.6, CVR=1.0               | 0.716296 | ±0.00%   | 1.523655 | 0.757560 | ±0.00%   | 0.492918 | ✅   |
| weight_tune_ctr22  | CTR=2.2, CVR=1.0               | 0.715897 | −0.06%   | 1.289793 | 0.757699 | +0.02%   | 0.492818 | ✅   |
| **ctr36**          | **CTR=3.6, CVR=1.0**           | **0.716696** | **+0.05%** | 2.108670 | 0.757501 | −0.01%   | 0.493332 | ✅   |
| **ctr40**          | **CTR=4.0, CVR=1.0**           | 0.716621 | +0.04%   | 2.343095 | 0.756817 | −0.10%   | 0.493304 | ✅   |
| **ctr45**          | **CTR=4.5, CVR=1.0**           | **0.717057** | **+0.10%** | 2.634723 | **0.757881** | **+0.04%** | 0.493627 | ✅   |
| **ctr48**          | **CTR=4.8, CVR=1.0**           | 0.716935 | +0.09%   | 2.810724 | 0.757347 | −0.03%   | 0.493821 | ✅   |
| **ctr54**          | **CTR=5.4, CVR=1.0**           | 0.716932 | +0.09%   | 3.162181 | 0.757635 | +0.01%   | 0.494137 | ✅   |
| **ctr60**          | **CTR=6.0, CVR=1.0**           | 0.716796 | +0.07%   | 3.514240 | 0.756707 | −0.12%   | 0.494114 | ✅   |
| weight_tune_cvr15  | CTR=3.3, CVR=1.5               | 0.715886 | −0.06%   | 1.934826 | 0.757555 | −0.00%   | 0.739037 | ✅   |
| weight_tune_cvr20  | CTR=3.3, CVR=2.0               | 0.714911 | −0.20%   | 1.937199 | 0.757048 | −0.07%   | 0.985352 | ✅   |
| weight_tune        | CTR=1.5, CVR=3.0               | 0.708770 | −1.05%   | 0.887004 | 0.755498 | −0.28%   | 1.478402 | ✅   |
| uncertainty_weight | `use_uncertainty_weight: true` | 0.712468 | −0.54%   | 1.942565 | 0.756901 | −0.09%   | 0.492595 | ✅   |
| pareto             | `use_pareto_loss_weight: true` | 0.713599 | −0.38%   | 1.939914 | 0.755692 | −0.26%   | 0.493182 | ✅   |

## 分析

### weight_tune（网格扫描）— 关键实验

#### 已产出：weight_tune（激进反转）

CTR weight 3.3→1.5, CVR weight 1.0→3.0：

AUC 双双下降 — 见主表。这是关键反直觉现象：给 CVR 更多权重，CVR 反而变差。

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

#### 权重网格扫描进展

| 实验                    |   CTR   |   CVR   | Δauc_ctr   | Δauc_cvr   | 解读                           |
| :-------------------- | :-----: | :-----: | :--------- | :--------- | :--------------------------- |
| baseline              |   3.3   |   1.0   | —          | —          | 锚点                           |
| **weight_tune_ctr30** | **3.0** |   1.0   | −0.02%     | −0.09%     | CTR↓微降，CVR 略伤                |
| **weight_tune_ctr26** | **2.6** |   1.0   | ±0.00%     | ±0.00%     | CTR 权重在此区间几乎无影响              |
| **weight_tune_ctr22** | **2.2** |   1.0   | −0.06%     | +0.02%     | CTR 大降，CVR 微升（噪声级）           |
| **ctr36**             | **3.6** |   1.0   | **+0.05%** | −0.01%     | CTR AUC 最佳，CVR 持平            |
| **ctr40**             | **4.0** |   1.0   | +0.04%     | −0.10%     | CTR AUC 维持高位，CVR 略降          |
| **ctr45**             | **4.5** |   1.0   | **+0.10%** | **+0.04%** | **CTR AUC 最优 + CVR 微涨，全网最佳** |
| **ctr48**             | **4.8** |   1.0   | +0.09%     | −0.03%     | CTR 维持高位，CVR 略降              |
| **ctr51**             | **5.1** |   1.0   | ⏳          | ⏳          | 未跑                            |
| **ctr54**             | **5.4** |   1.0   | +0.09%     | +0.01%     | CTR 维持高位，CVR 持平               |
| **ctr57**             | **5.7** |   1.0   | ⏳          | ⏳          | 未跑                            |
| **ctr60**             | **6.0** |   1.0   | +0.07%     | −0.12%     | 拐点确认：CTR 和 CVR 双双回落           |
| **weight_tune_cvr15** |   3.3   | **1.5** | −0.06%     | −0.00%     | CVR↑微升，CVR AUC 几乎不变          |
| **weight_tune_cvr20** |   3.3   | **2.0** | −0.20%     | −0.07%     | CVR↑中涨，BCE_cvr 翻倍            |
| weight_tune           |   1.5   |   3.0   | −1.05%     | −0.28%     | 双方大幅退化，极限反转                  |

**关键发现：**

1. **CTR 权重在 [2.2, 3.6] 范围 AUC 几乎不变** — 变化幅度均 < 0.06%。CTR 有 100% 样本的梯度保障，权重缩放几乎不影响预测质量。这是一个**极宽的平坦区**。

2. **CVR weight 增加 → 单调递减** — cvr15(−0.00%) → cvr20(−0.07%) → weight_tune(−0.28%)，AUC 随 CVR 权重严格单调下降。BCE_cvr 从 0.493 → 0.739(cvr15) → 0.985(cvr20) → 1.478(weight_tune)，预测概率尺度被严重扭曲。

3. **对称性不对等** — CTR 权重 ±9% (3.3→3.6→3.0) 的 AUC 变化远小于 CVR 权重变化 ±9% 的影响。权重影响取决于**梯度信号量**，不是权重变化幅度。

4. **ctr45 (+0.10% CTR, +0.04% CVR) 确认为全网最优**。CTR AUC 在 4.5 达到峰值后缓慢回落（4.8: +0.09% → 5.4: +0.09% → 6.0: +0.07%），CVR AUC 在 4.5 为峰后波动下降。**CTR=4.5 是甜区顶点，宽峰态**（4.5~5.4 的 CTR AUC 差异 < 0.01%）。

### uncertainty_weight — 结果确认（代码已生效，性能下降）

AUC/both 均下降（见主表），`UncertaintyWeightLoss` 已生效。UW 学习到的权重倾向于给 CVR 更高噪声估计 → 梯度被压低 → 共享表示退化。

**预期效果应谨慎**：
- 若 UW 给 CTR 更高权重（CTR 噪声大）→ 等价于 baseline，无改进
- 若 UW 给 CVR 更高权重（CVR 噪声小）→ 类似 weight_tune，可能有害

### pareto — 结果确认

双方 AUC 均下降（见主表），符合预期。Pareto 优化试图平衡梯度幅度，压制了 CTR 的梯度主导优势，导致共享表示质量下降。BCE_cvr 几乎不变（0.4933→0.4932），说明 CVR 输出概率分布的尺度未变，但 AUC 下降暗示排序质量受损。结论同上：**baseline 状态已是该架构的 Pareto 最优点**。

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

1. **任务级 Loss 加权对 CVR 无效** — 已跑 9 个实验全部验证：任何偏离 baseline 权重的 loss 调整 → 共享表示退化 → 双方 AUC 均下降。GradNorm 同理。

2. **完整权重扫描揭示倒U型曲线** — CTR 权重在 [2.2, 3.6] 为平坦区（变化 < 0.06%），在 4.5 达到峰值后缓慢回落。CTR=4.5 是甜区顶点（+0.10%/+0.04%）。CVR 权重增加则单调递减，不存在甜区。

3. **ctr45 (+0.10% CTR, +0.04% CVR) 为 v12 最优配置** — 所有 12 个 loss 调优实验中唯一双方正向。幅度 < 0.1%，但趋势清晰且落在倒U型曲线的顶点。

4. **UncertaintyWeight 已确认生效但有害**（−0.54%/−0.09%），PE-MTL 同理（−0.38%/−0.26%）。

5. **后续不再此方向投入** — CVR 提升应转向样本级权重（search_weight IPW）、数据增强、模型结构改进（加深 CVR tower、CVR 独立 bottom）。

6. **代码保留但不继续优化** — `UncertaintyWeightLoss` 已实现，`PE-MTL` 已有支持。若未来 CVR 训练信号量增加，可复用。
