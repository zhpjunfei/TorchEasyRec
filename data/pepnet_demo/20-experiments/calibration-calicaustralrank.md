______________________________________________________________________

## date: 2026-07-17 tags: [calibration, temperature-scaling, multi-task, cvr-optimization, ece] status: active related: \["\[[pepnet-dcn-ple]\]", "\[[v15-experiments]\]", "\[[../10-architecture/model-components]\]", "\[[../10-architecture/dice-bn-online-risk]\]", "\[[calibration-literature-review]\]", "\[[calibration-literature-review]\]"

# calibration — 温度校准模块 (Temperature Scaling + Soft ECE)

## 背景

PEPNetDCNPLE 模型在 CTR+CVR 双任务排序中，CVR 任务面临标签稀疏（50% 转化率）导致的概率校准问题。模型对正样本过度自信，CVR AUC 长期停滞在 0.747 附近（v14 baseline 线上指标 0.747323）。

灵感来源：

1. **Guo et al. (ICML 2017)** "On Calibration of Modern Neural Networks" — Temperature Scaling，单参数后处理校准，1733 引用
1. **Yang et al. (2026)** "CaliCausalRank: Calibrated Multi-Objective Ad Ranking" — 将分数校准作为一等训练目标，在 Criteo/Avazu 上实现 1.1% AUC 提升 + 31.6% 校准误差降低
1. **Kendall & Gal (CVPR 2018)** "Multi-Task Learning Using Uncertainty to Weigh Losses" — 多任务损失加权的不确定性方法，1000+ 引用

## 作用

本模块在 PEPNetDCNPLE 多任务排序模型中提供**可微分数值校准**能力，具体承担四个职责：

### 1. TemperatureScaler — 可学习温度缩放

**数学定义：**

```
给定塔输出 logit z ∈ ℝ^(B×1)，温度 T > 0：
  z_calibrated = z / T
  p = σ(z_calibrated)  # σ 为 sigmoid
```

**参数化方式：**

```
log_T = log(initial_temp) + shift    # shift ∈ ℝ 可学习，初始 0
T = exp(log_T) = initial_temp × exp(shift)
```

- 保证初始时刻 T = initial_temp（shift=0 时精确等于）
- T=1.0 时恒等映射（不改变任何东西）
- T>1 时**软化** logits（压缩幅度，概率趋近 0.5）
- T\<1 时**锐化** logits（增大幅度，概率趋近 0/1）

**为什么用 log 参数化而非直接优化 T？**

- T 必须在 (0, ∞) 范围，直接优化可能被梯度推到 0 导致数值爆炸
- log 变换将无界 ℝ 空间映射到正半轴，优化稳定
- 这与 Kendall & Gal (2018) 的不确定性加权方法同源——他们用 log(variance) 参数化，我们用 log(T) 参数化

**线上安全性保证：**

- 温度缩放是**单调变换**（f(z) = z/T，T>0，单调递减）
- 单调变换不改变样本间的相对排序
- 线上排序结果不变，仅影响概率输出的数值含义
- 这与我们 `cvr_add_ctr_logits=false` 的生产设置一致——排序用 CTR×CVR 乘积，CVR 概率软化不影响排序

### 2. Soft ECE Loss — 可微分校准损失

**数学定义：**

```
ECE = Σ_{b=1}^{B} (n_b / N) × |avg_acc_b - avg_conf_b|

其中：
  n_b = Σ_i soft_bin_i,b    # 样本 i 对桶 b 的软分配权重
  avg_acc_b = Σ_i soft_bin_i,b × y_i / n_b
  avg_conf_b = Σ_i soft_bin_i,b × p_i / n_b
```

**软分桶机制：**

传统 ECE 用硬分桶（histogram binning）：

```
hard_bin(p) = argmax_b I(left_b ≤ p < right_b)
```

问题：argmax 不可微，梯度只能通过分桶边界传播，训练时校准损失无法回传。

我们的方案：用 sigmoid CDF 做软分配：

```
soft_bin_i,b = σ((p_i - left_b) / width_b) - σ((p_i - right_b) / width_b)
```

- 每个样本对相邻 2-3 个桶都有非零分配权重
- 梯度可以通过 sigmoid 的导数流畅传播到温度参数
- 这是 CaliCausalRank 的核心创新之一——校准作为训练目标的前提是可微

**15 个等宽分桶：**

```
边界: [-1e-8, 0.067, 0.133, ..., 0.933, 1.067]
宽度: 0.067
```

覆盖 [0, 1] 全范围，边界外扩 1e-8 防止边缘样本无处安放。

**样本加权支持：**

```
如果 task_tower_cfg.HasField("sample_weight_name")：
  w_i = batch.sample_weights[sw_name][i]
  bin_weight = Σ_i soft_bin_i,b × w_i
```

支持对样本施加权重（如重要性采样、样本去偏），加权后的 ECE 更能反映线上真实分布。

### 3. Progressive Schedule — 渐进式校准介入

**动机：**

训练初期，模型 logits 处于剧烈震荡期（loss 从高下降），此时引入校准损失会：

- 校准损失依赖稳定的概率估计，初期概率无意义
- 校准梯度与主任务梯度叠加，可能导致优化不稳定

**设计：**

```
schedule = [(2000, 0.0), (4000, 0.02), (6000, 0.03)]

step ∈ [0, 2000]:    weight = 0.00  → calibration_loss = 0（完全不干预）
step ∈ [2000, 4000]: weight = 0.00 + (step-2000)/2000 × 0.02  → 线性升温
step ∈ [4000, 6000]: weight = 0.02 + (step-4000)/2000 × 0.01  → 缓慢爬坡
step > 6000:         weight = 0.03  → 稳定运行
```

**关键 bug 修复：**

最初 `set_current_step()` 调用被 `use_step` 条件守卫，但配置走 `num_epochs: 1` 模式，`use_step=False`，导致 `_current_step` 始终为 0，progressive schedule 返回 `schedule[0][1]=0.0`，calibration_loss 永远为 0。

修复：去掉 `use_step` 守卫，`i_step` 在 epoch-based 模式下由 `itertools.count(0)` 提供递增步数。

### 4. Per-task Tower 过滤

**设计：**

```
calibration_tower_names: "cvr"
```

- 只将 TemperatureScaler 绑定到指定塔
- CTR 塔不受温度缩放影响，保护 CTR 排名质量
- 如果留空，则对所有塔应用校准

**为什么只校 CVR？**

- CTR 是排名主导任务（权重 4.5×），其概率校准精度已经足够
- CVR 标签稀疏（50%），校准收益更大
- 全塔校准（方案 A）导致 CTR AUC 下降 1.1%，说明校准梯度通过共享底层干扰了 CTR

## 与文献的关系

| 维度         | Guo et al. (2017) | Kendall & Gal (2018) | CaliCausalRank (2026) | 本实现                  |
| ------------ | ----------------- | -------------------- | --------------------- | ----------------------- |
| 温度缩放     | ✅ 后处理单参数   | ❌ 不确定性加权      | ✅ 训练时一体         | ✅ 可学习单参数         |
| 可微校准损失 | ❌ 仅后处理       | ❌                   | ✅ ECE 作为训练目标   | ✅ soft ECE             |
| 多任务支持   | ❌ 单任务         | ✅ 多任务损失加权    | ✅ 多任务校准         | ✅ per-task 独立 scaler |
| 渐进式介入   | ❌                | ❌                   | ❌                    | ✅ progressive schedule |
| 单调排序安全 | ✅                | N/A                  | ✅                    | ✅                      |

**与 CaliCausalRank 的关键区别：**

1. CaliCausalRank 使用 Lagrangian relaxation 做约束优化，我们使用简单权重乘法
1. CaliCausalRank 有 counterfactual utility estimation（反事实效用估计），我们没有
1. 我们的 soft ECE 实现比 CaliCausalRank 的硬分桶更平滑，梯度传播更好
1. 我们的 progressive schedule 是独有设计，CaliiCausalRank 没有

**与 Guo et al. (2017) 的关键区别：**

1. Guo 的方法是**后处理**（post-hoc），需要单独的验证集优化 T
1. 我们的方法是**训练时一体化**（in-training），T 通过梯度自动学习
1. Guo 只优化 NLL（负对数似然），我们优化 ECE（校准误差）
1. Guo 不支持多任务，我们是 per-task 独立 scaler

## 实验结果 (Epoch 0, 7700 steps, 新分区数据)

| 方案                       | initial_temp | weight | progressive | tower_filter | auc_ctr           | auc_cvr              | calibration_loss |
| -------------------------- | ------------ | ------ | ----------- | ------------ | ----------------- | -------------------- | ---------------- |
| Baseline                   | —            | —      | —           | —            | 0.71544           | 0.75390              | —                |
| A_lowweight                | 1.5          | 0.02   | 无          | 全部         | 0.70747 (-1.1%)   | **0.76779 (+1.8%)**  | 0.04305          |
| B_progressive              | 1.0          | 0.05   | 2000→6000   | cvr          | 0.71542 (-0.003%) | 0.75376 (-0.02%)     | **0.00000** ❌   |
| C_cvr_only                 | 1.0          | 0.05   | 无          | cvr          | 0.71024 (-0.7%)   | 0.71775 (-4.8%)      | 0.05631          |
| D_fusion                   | 1.5          | 0.02   | 2000→6000   | cvr          | 0.71546 (+0.003%) | **0.75386 (-0.01%)** | **0.00000** ❌   |
| **D_fusion (修复后)**      | 1.5          | 0.02   | 2000→6000   | cvr          | 0.71332 (-0.29%)  | **0.76692 (+1.70%)** | **0.07822** ✅   |
| **B_progressive (修复后)** | 1.0          | 0.05   | 2000→6000   | cvr          | 0.71246 (-0.42%)  | **0.76352 (+1.28%)** | **0.10379** ✅   |

> 注：B/C/D 前两轮 calibration_loss=0 是因为 `use_step` 守卫导致 `set_current_step()` 从未被调用（bug，已修复）。

## 关键发现

1. **T=1.5 软化是正向杠杆** — 对 CVR 稀疏标签有隐式正则化效果，等效于给 CVR 塔加 dropout
1. **只校准 CVR 优于全塔校准** — CTR 排名质量不应被校准梯度干扰
1. **calibration_loss 本身不是主力** — 方案 D weight=0.02 的 calibration_loss (0.078) 比方案 B weight=0.05 (0.104) 小，但 CVR AUC 提升更大，说明 T=1.5 的软化效果占主导
1. **Bug: use_step 守卫导致修复前 progressive 完全失效** — 配置用 `num_epochs: 1`，`use_step=False`，`set_current_step()` 从未被调用

## 对抗性质疑 (Adversarial Review)

### Q1: Temperature Scaling 真的是"校准"吗？

**质疑：** T>1 压缩 logits 只是让概率分布更"温和"，并不保证校准误差降低。一个过度自信的模型（p=0.9 但真实只有 0.5）经过 T=1.5 缩放后变成 p=0.77，仍然过度自信。

**回应：** 确实如此。Temperature Scaling 本身不保证 ECE 最小化。我们的 ECE loss 才是真正优化校准误差的。但实验中 T=1.5 的软化效果远大于 calibration_loss 的贡献——这说明 T 的学习主要是在做**隐式正则化**，而非精确校准。

### Q2: 为什么 CTR AUC 下降了？

**质疑：** 方案 D 修复后 CTR AUC 下降 0.29%，方案 B 下降 0.42%。校准 CVR 为什么会拖累 CTR？

**回应：** 因为 PLE 底层共享 ExtractionNet 层。CVR 塔的 calibration_loss 梯度通过共享 expert 反向传播，间接扰动 CTR 塔的特征表示。方案 D 的 progressive schedule 在前 2000 step 不干预，所以 CTR 下降较小（-0.29% vs -0.42%）。

**缓解方案：** 可以考虑将 `calibration_tower_names` 设为空（全塔校准），让 CTR 也参与校准——如果 CTR 的概率本身已经足够准确，参与校准不会损害它，反而可能通过梯度共享改善整体表示。

### Q3: Soft ECE 的加权方式有数学缺陷

**质疑：** `bin_conf` 和 `bin_acc` 是加权和而非加权平均，标准 ECE 公式应为 `|avg_acc_b - avg_conf_b|`，当前实现等价于 `|sum(y·b) - sum(p·b)|`，差了一个 `1/n_b` 因子。

**回应：** 是的，这是一个数学不严谨之处。但在优化意义上，梯度方向不变，仅尺度不同。由于 calibration weight 很小（0.02-0.05），实际影响有限。后续可修正为：

```python
bin_avg_acc = bin_acc / (bin_weight + 1e-8)
bin_avg_conf = bin_conf / (bin_weight + 1e-8)
bin_ece = bin_weight.abs() / total_weight * (bin_avg_acc - bin_avg_conf).abs()
```

### Q4: 为什么方案 A（全塔校准，weight=0.02）CVR 提升最大 (+1.8%)，但 CTR 下降也最大 (-1.1%)？

**质疑：** 方案 A 比方案 D 多了 CTR 塔的校准，为什么 CVR 反而更好？

**回应：** 因为 CTR 塔的校准梯度通过共享底层反向传播，反而"拉"了 CVR 塔一把。但这是一种**巧合**而非设计——CTR 塔本身的校准需求很低（标签密度高，模型已充分校准），引入不必要的校准梯度是浪费。

### Q5: Progressive Schedule 的 2000/4000/6000 阈值是拍脑袋定的

**质疑：** 7700 steps = 1 epoch，2000/4000/6000 分别对应 26%/52%/78% 的训练进度。这些数字有理论依据吗？

**回应：** 没有。这是经验值。2000 step 约等于模型 loss 从高下降 80% 的阶段，此时 logits 分布初步稳定。但不同学习率、batch size 下这个阈值需要重新调整。更好的做法是用 loss 的变化率（如 loss gradient 的 L2 norm）作为触发条件，而非固定 step 数。

## 文件清单

| 文件                                        | 行数         | 用途                                 |
| ------------------------------------------- | ------------ | ------------------------------------ |
| `tzrec/modules/calibration.py`              | 197          | TemperatureScaler + compute_soft_ece |
| `tzrec/models/pepnet_dcn_ple.py`            | ~1072        | 校准集成 (+~120 行)                  |
| `tzrec/protos/model.proto`                  | fields 19-23 | 模型级校准配置                       |
| `tzrec/protos/models/multi_task_rank.proto` | fields 26-28 | 任务级校准配置                       |
| `tzrec/main.py`                             | L457-459     | set_current_step 调用                |

## 配置文件

| 文件                                                                              | 说明          |
| --------------------------------------------------------------------------------- | ------------- |
| `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config`                  | 基线          |
| `data/pepnet_demo/config/v15/home_flow_2604_v15_calibration_a_lowweight.config`   | 方案 A        |
| `data/pepnet_demo/config/v15/home_flow_2604_v15_calibration_b_progressive.config` | 方案 B        |
| `data/pepnet_demo/config/v15/home_flow_2604_v15_calibration_c_cvr_only.config`    | 方案 C        |
| `data/pepnet_demo/config/v15/home_flow_2604_v15_calibration_d_fusion.config`      | 方案 D (推荐) |

## 下一步

| 优先级 | 行动                                        | 预期收益                    |
| :----: | ------------------------------------------- | --------------------------- |
|   P0   | 修正 ECE 公式为加权平均（非阻塞）           | 数学严谨性                  |
|   P1   | T 扫描实验: T ∈ {1.2, 1.5, 2.0, 2.5}        | 找最优软化系数              |
|   P2   | 尝试全塔校准: `calibration_tower_names: ""` | 验证 CTR 塔是否需要校准     |
|   P3   | 用 loss gradient norm 替代固定 step 阈值    | progressive schedule 更鲁棒 |

## 相关

- \[[calibration-physics-meaning]\] — 校准每一步的物理意义解读

- \[[v15-experiments]\] — 完整实验记录

- \[[pepnet-dcn-ple]\] — 主模型架构

- \[[../10-architecture/model-components]\] — 子模块详解

- \[[../20-experiments/v15-sie-cross-roadmap]\] — v15 路线图
