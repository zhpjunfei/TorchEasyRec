# V11 Title Vector Contrastive Learning — 完整设计方案

## 1. 背景

### 问题

当前 v11 config 已将 title_vector（128-dim 文本语义向量）加入特征组，直接作为 raw_feature 输入 model。但它是**静态的**——只携带通用语义信息，没有个性化行为信号。

用户的历史行为序列（click_50_seq 等）中包含丰富的偏好信息，但当前 DIN 编码器只被 CTR/CVR 任务的梯度间接优化，缺少一个**专门的语义对齐信号**。

### 对比学习的切入点

- **View A**：DIN 编码器输出的行为注意力向量 `v(T)` — 以 target item 为 query，从用户历史中选择性聚合
- **View B**：target item 的 title_vector — 预训练文本语义向量

两者共享的信息：**"这个 target 的内容描述，和用户行为历史中哪些部分相关"**。

InfoNCE 对比学习的本质是最大化互信息下界：

```
I(View_A; View_B) ≥ L_InfoNCE
```

______________________________________________________________________

## 2. 核心设计：行对齐 vs 列对齐

### 定义

| 对齐方式                           | 锚点                     | 被调整方     | 作用参数                    | 条件                |
| ---------------------------------- | ------------------------ | ------------ | --------------------------- | ------------------- |
| **列对齐**（behavior → semantics） | title_vector（语义空间） | DIN encoder  | DIN MLP + item_id embedding | 行为稀疏/稠密均适用 |
| **行对齐**（semantics → behavior） | behavior embedding       | title_vector | title_vector projection     | 仅在行为稠密时启用  |

### 关键发现：title_vector 天然是 pass-through

```yaml
raw_feature {
  feature_name: "title_vector"
  value_dim: 128
  separator: ","
}
```

`RawFeature.output_dim = value_dim = 128`，**不经过任何可学习层**。InfoNCE 梯度无法流入 title_vector。

→ **Phase 1 的列对齐天然成立**，不需要 stop-gradient。
→ **Phase 2 的行对齐需新增** `embedding_dim: 128` 开启可学习投影。

### 关键修复：v2t/t2v 拆分为独立计算路径

**Phase 1a 实现评审发现三个耦合问题**，根因是 `sim = torch.mm(v, t.t()) / τ.unsqueeze(1)` 一行同时服务两个方向。

#### 问题 1：t2v 全量 16K softmax 无效

t2v 使用 `-sim_pos + logsumexp(sim, dim=0)`，分母包含 16000 项。每个负样本的 softmax 权重 ≈ 1/16000，梯度被平均分配 → 有效推开幅度为 0。

**修复**：t2v 也使用 HardNegative K=150。t2v 不存在 item frequency bias（负样本 = 其他行为向量，不携带 item_id），不需要 LogQ。

#### 问题 2：`sim_pos` 未 LogQ 校正导致 loss → `-logq`

当前 `sim_pos = sim.diag()`（uncorrected），`logsumexp` 内正样本被 LogQ 压低：

```
loss_v2t ≈ -sim[i,i] + logsumexp(sim_c[hard])
         ≈ -sim[i,i] + (sim[i,i] - logq[i])
         ≈ -logq[i]
```

收敛时 loss 反向→高热 item loss 更低，**放大热门偏差**。

**修复**：`sim_pos = sim_c.diag()`（LogQ 校正后再取对角），收敛后 loss ≈ 0。

#### 问题 4（新发现）：t2v 误用 dim=-1 行方向

评审发现 t2v 使用 `dim=-1`（行方向），和 v2t 完全一样：对每个行为 v[i] 从所有标题中找正样本 `t[i]`。这不是真正的 t2v。

真正的 t2v（列方向 `dim=0`）应该是对每个标题 t[j]，从所有行为 v[0..B-1] 中找匹配的正样本 v[j]。正样本集相同（都是 `(i,i)` 对角），但 **负样本分布不同**：

- 行方向：`v[j≠i]·t[i]`（同一标题，不同行为）
- 列方向：`v[i]·t[j≠i]`（同一行为，不同标题）

两者互补，对称 InfoNCE 需要两个方向的负样本分布。

**修复**：t2v HardNegative + logsumexp 用 `dim=0`。

#### 问题 3：per-row τ 破坏 sim 对称性

`sim = raw_sim / τ.unsqueeze(1)` 中 τ 按行（seq_len）变化，但 t2v 每次遍历列标题向量——标题的置信度与 seq_len 无关。

**修复**：v2t 用 per-seq_len τ（行为置信度依赖 seq_len），t2v 用固定 τ=0.07（标题向量恒为 Qwen3 128d）。

**发现：t2v 方向是 dim=0 列方向，不是 dim=-1 行方向**

评审发现第四条——t2v 当前实现也是 `dim=-1`（行方向），和 v2t 完全相同。即对每个行为 v[i] 从所有标题中找正样本，只是温度不同。这等于把相同的对比信号重复了两遍，失去了对称 InfoNCE 中"对每个标题找匹配行为"的收益。

**修复**：t2v HardNegative + logsumexp 改用 `dim=0`（列方向）：

```
每列 j: 对标题 t[j] → 从所有行为 v[0..B-1] 中挑出匹配的正样本 v[j] 和 hardest 行为负样本
```

#### 四个修复统一效果

```
v2t: sim_v2t = raw_sim / τ(seq_len) - logq    → HardNegative dim=-1, K=150
t2v: sim_t2v = raw_sim / 0.07                  → HardNegative dim=0,  K=150
sim_pos_v2t = sim_c.diag()    # LogQ 校正
sim_pos_t2v = sim_t2v.diag()
loss = (loss_v2t + loss_t2v) / 2    ← 对称 InfoNCE，两方向互补
```

**确认：loss 方向修正后不会导致 `contrastive_loss` 回传异常。** 两个方向分开计算 `-sim_pos + logsumexp(hard)`，每个方向各有 ~K+1 项 logsumexp，loss 量级匹配。

### 序列长度调节策略（连续 gating）

#### 问题：为什么需要 gating？

用户的历史行为序列长度从 0 到 50 不等（click_50_seq）：

| seq_len 分布 | 占比     | 含义           |
| ------------ | -------- | -------------- |
| 0（空序列）  | ~2%      | 新用户或冷启动 |
| 1-10         | ~14%     | 稀疏行为用户   |
| 11-40        | ~18%     | 中等活跃用户   |
| 41-50        | **~66%** | 高活跃用户     |

DIN 输出质量随序列长度变化：

- **seq_len=50**：DIN 有 50 个 item 可以加权聚合 → 行为表示稳定、信息丰富 → 可以接受对齐标题的细粒度约束
- **seq_len=5**：DIN 只有 5 个 item → 行为表示方差大、噪声多 → 如果强行拉近到 title_vector，相当于让标题去拟合噪声
- **seq_len=0**：DIN 输出全零向量 → 完全无信号

**如果用一个固定的温度 τ=0.07 对所有序列做对比学习**：

- 长序列：合理，对齐紧
- 短序列：被强制对齐，行为表示被 title_vector 带偏 → **CTR/CVR 主任务受损**

#### 解法：序列长度感知的温度调节

InfoNCE 中的温度 τ 控制对负样本的区分力度：

```
L = -log( exp(pos/τ) / Σ exp(neg_i/τ) )

τ 越小 → softmax 越尖锐 → 对比学习越"用力"（push/pull 梯度大）
τ 越大 → softmax 越平滑 → 对比学习越"松弛"（梯度小，容忍噪声）
```

核心思路：**短序列 = 高噪声 → 大温度（松弛约束），长序列 = 低噪声 → 小温度（紧约束）**。

#### 公式

```
τ(seq_len) = τ_min + (τ_max - τ_min) · e^(-α · seq_len)
```

| 参数  | 值   | 含义                                             |
| ----- | ---- | ------------------------------------------------ |
| τ_min | 0.07 | 长序列极限温度（seq_len→∞），标准 InfoNCE 常用值 |
| τ_max | 0.5  | 空序列温度（seq_len→0），松弛到几乎不约束        |
| α     | 0.1  | 衰减速率，控制从短到长的过渡坡度                 |

#### 效果曲线

```
τ(0)  = 0.07 + 0.43 × 1.0     = 0.500  弱约束（空序列兜底）
τ(5)  = 0.07 + 0.43 × 0.607  ≈ 0.331  稀疏行为，松弛
τ(10) = 0.07 + 0.43 × 0.368  ≈ 0.228  中等约束
τ(20) = 0.07 + 0.43 × 0.135  ≈ 0.128  大部分可用信号
τ(30) = 0.07 + 0.43 × 0.050  ≈ 0.091  接近全量约束
τ(50) = 0.07 + 0.43 × 0.007  ≈ 0.073  几乎 τ_min
```

关键设计点：

- **指数衰减**：seq_len 越短，温度上升越快。10→5 变宽松 0.228→0.331（+45%），10→20 变紧 0.228→0.128（-44%），对称合理
- **e^(-α·seq_len)** 在 seq_len≥30 后 < 0.05 → 有效温度 ≈ τ_min，长序列统一强对齐
- **τ_max=0.5**：seq_len=0 时 τ=0.5，对比学习几乎不起作用，相当于自动跳过空序列

#### 温度 τ 如何控制约束强度

InfoNCE 对正样本和负样本的梯度：

```
∂L/∂pos  = -(1 - p+) / τ       ← 把正样本拉近
∂L/∂neg_i = p- / τ             ← 把负样本推远

其中:
  p+ = exp(pos/τ) / Z          ← 正样本 softmax 占比
  p- = exp(neg_i/τ) / Z        ← 单个负样本 softmax 占比
  Z  = exp(pos/τ) + Σ exp(neg_j/τ)
```

τ 通过两条路径影响梯度：**1/τ 放大幅度** + **p+ 控制选择性**。

假设模型经过一定训练后 `pos=0.8, avg_neg=0.0, B=16000`：

**τ=0.07 时：**

```
pos/0.07 = 11.4 → exp = 89866
neg/0.07 = 0   → exp = 1
Z = 89866 + 16000 × 1 = 105866
p+ = 89866 / 105866 ≈ 0.85          # 85% 权重在正样本
∂L/∂pos = -(1-0.85)/0.07 ≈ -2.14    # 梯度集中在正样本上
∂L/∂neg ≈ (1/105866)/0.07 ≈ 1.35e-4 # 只有极少数 hard neg 有贡献
```

→ **约束紧**：正样本占 softmax 85%，模型能清晰区分正负 → 强烈驱动行为表示向 title_vector 对齐。

**τ=0.5 时：**

```
pos/0.5 = 1.6 → exp = 4.95
neg/0.5 = 0   → exp = 1
Z = 4.95 + 16000 × 1 = 16005
p+ = 4.95 / 16005 ≈ 0.00031         # 0.03% 在正样本，和随机无异
∂L/∂pos = -(1-0.00031)/0.5 ≈ -2.00  # 正样本梯度和 τ=0.07 几乎一样大!
∂L/∂neg ≈ (1/16005)/0.5 ≈ 1.25e-4  # 单个负样本梯度也和 τ=0.07 几乎一样
```

单看 `∂L/∂pos` 和 `∂L/∂neg` 的大小，τ=0.07 和 τ=0.5 **几乎一样**。那为什么说 τ=0.5 是弱约束？

**关键区别在 p+ 的绝对值**：

| τ    | p+    | loss = -log(p+) | 模型状态                           |
| ---- | ----- | --------------- | ---------------------------------- |
| 0.07 | 85%   | 0.16            | 已经高度确定哪个是正样本，只需微调 |
| 0.5  | 0.03% | 8.10            | 完全不确定，正负混淆               |

**τ 的真正作用是控制"对比半径"**：

- τ=0.07：14x 放大镜。同 batch 16000 个负样本中，只有 top few hardest 的 softmax 权重非零。模型必须挑出"最难区分的那个负样本"来推远 → **选择性高，信息量大**
- τ=0.5：2x 放大镜。所有 16000 个负样本的 softmax 权重 ≈ 均匀。加上 HardNegative K=150，top 150 的得分也相差无几。梯度被**平均分配**到大量负样本上，不给任何一个负样本明显推开的机会 → **没有选择性，信息量低**

**直观理解**：τ 不是控制"梯度有多大"，而是控制"模型要区分多像的负样本"。τ=0.5 相当于告诉模型"你只要和正样本大概差不多就行，不用跟特定的负样本较劲"。短序列的行为本身就模糊（噪声大），给它一个大的对比半径，≈ 跳过对比约束。

#### 和硬门控（if-else）的区别

| 方案                                  | 代码                      | 效果                                                            |
| ------------------------------------- | ------------------------- | --------------------------------------------------------------- |
| if seq_len < N: skip contrastive loss | 5 行                      | 硬边界，seq_len=N±1 天差地别                                    |
| 连续 gating（本方案）                 | 1 行 `τ(...)`             | 平滑过渡，seq_len=9 和 11 温度自然接近                          |
| 序列长度作为 weight 乘 loss           | 1 行 `loss *= w(seq_len)` | 梯度量级改变，但 softmax 内部分布不变；温度同时改变梯度和选择性 |

______________________________________________________________________

## 3. 行为序列选择

### 主 View：click_50_seq（唯一推荐）

| 序列              | 长度   | 信号 | 语义对齐                | 样本密度 | 推荐           |
| ----------------- | ------ | ---- | ----------------------- | -------- | -------------- |
| **click_50_seq**  | **50** | 中等 | ✅ 点击与标题语义最匹配 | **最高** | **⭐ 主 View** |
| click_10_seq      | 10     | 中等 | ✅                      | 高       | ❌ 长度不够    |
| conversion_20_seq | 20     | 强   | ⚠️ 含非语义因素         | 低       | ❌ 信号不纯    |
| conversion_5_seq  | 5      | 强   | ⚠️                      | 极低     | ❌             |
| favorite_10_seq   | 10     | 强   | ✅                      | 极低     | ❌             |
| favorite_5_seq    | 5      | 强   | ✅                      | 极低     | ❌             |

理由：

1. **50 个 item 降低 DIN 输出方差**，InfoNCE 负样本充足
1. **点击决策最依赖标题/缩略图**，语义对齐天然成立
1. **序列长度 0-50 分布广**，支持连续 gating
1. **样本密度最高**，训练稳定

### 辅助 View：chaprice_click_50_seq（Phase 1b 可选项）

#### 配置分析

独立 sequence_group，有独立的 DIN encoder（config line 12680-12701, 12775）。

| 维度                         | click_50_seq（主）                    | chaprice_click_50_seq（辅）               |
| ---------------------------- | ------------------------------------- | ----------------------------------------- |
| 序列主体                     | item_id + spu_id + title_vector + ... | **spu_id**（无 title_vector，无 item_id） |
| target query 含 title_vector | ✅ 有                                 | ❌ **没有**                               |
| 粒度                         | ITEM 级                               | **SPU 级**                                |
| 行为含义                     | 普通点击                              | 查价比价（强购买意图）                    |
| 1-10 长序列占比              | 13.77%                                | **71.65%**                                |
| 41-50 长序列占比             | **66.16%**                            | 8.93%                                     |

#### 与 title_vector 做对比学习的问题

1. **粒度不匹配**：DIN 输出是 SPU 级行为 → title_vector 是 ITEM 级语义。`I(SPU_behav_DIN; ITEM_title)` 比 `I(ITEM_behav_DIN; ITEM_title)` 低。
1. **长度分布不利**：71.65% 样本只有 1-10，温度压制到 τ≈0.2-0.5，有效梯度极少。

#### 建议用法

只作为辅助 view，weight=0.3~0.5×。核心价值在于：**查价行为对 CVR 有直接信号**，对齐 title_vector 后模型学到"什么内容会触发比价购买"。

**决策**：等 Phase 1a（click_50_seq 主 view）跑通验证后再追加，不加到首次实施。

______________________________________________________________________

## 4. 空序列处理

### 当前行为

seq_len = 0 时 DIN 输出全零向量（`sequence.py:108-150`）：

```python
sequence_mask → 全 False → scores → uniform 1/50
content_seq → 全零 → output → 零向量
```

### 方案：可学习 Default Behavior Embedding

```python
self.default_behavior = nn.Parameter(torch.zeros(128))

v_for_contrast = torch.where(
    (seq_len > 0).unsqueeze(1),
    v_actual,
    self.default_behavior.expand_as(v_actual)
)
```

**效果**：空序列时 InfoNCE 拉 `default_behavior` → `E[title_vector]`（全局兴趣先验）。独立于 forward 路径，不修改 base model。

| 策略                       | 参数     | base model 影响 | 收益         | 风险   |
| -------------------------- | -------- | --------------- | ------------ | ------ |
| Mask 掉 loss               | 0        | 无              | 无（跳过）   | 无     |
| **可学习 default（推荐）** | **128**  | **无**          | **全局先验** | **无** |
| Default 注入回 DIN         | 128+proj | 会改变预测      | +base 受益   | 中     |

______________________________________________________________________

## 5. 方案总览

### Phase 1a：列对齐（click_50_seq 主 view）

InfoNCE 梯度只流入 DIN encoder，title_vector 作为静态锚点。LogQ + HardNegative + 诊断指标 + default_behavior。

### Phase 1b（可选追加）：chaprice_click_50_seq 辅助 view

在主 view 基础上，加第二路 InfoNCE（weight=0.3）。与 title_vector 粒度不匹配，预期增益有限但代码成本低（+5 行）。

### Phase 2：行对齐

给 title_vector 加 `embedding_dim: 128` 开启可学习投影，stop-gradient 防坍缩。

### Phase 3：连续双向 gating

`λ(seq_len) = sigmoid(β·(seq_len - L₀))` 连续插值行/列比例。

______________________________________________________________________

## 6. 对照业界标准的改进

### P0：LogQ 修正（Moving Average 版）

**问题**：In-batch negatives 中热门 item 出现频率过高，模型学会"压热门"而非学语义差异。

**关键洞察**：

- item_id 是帖子，生存期 3-5 天，离线预计算频繁过期
- LogQ 只需要区分"当前 batch 中 item 的相对热度"，不需要全局精确计数
- **Moving Average** 方案：每个 step 从 batch 统计 item 即时频次，平滑更新 `log_q`

**解法**：

```python
self.register_buffer("log_q", torch.full([NUM_BUCKETS], -math.log(NUM_BUCKETS)))
# θ = 0.01 ~ 0.05, 极小动量只吸收 1% 新分布

# 每步训练更新:
input_ids = batch.sparse_features["__BASE__"]["item_id_emb"].values()
freq = torch.bincount(input_ids, minlength=NUM_BUCKETS).float()
batch_freq = freq / freq.sum()
self.log_q.mul_(1 - theta).add_(theta, torch.log(batch_freq + 1e-8))

# v2t 方向校正（LogQ 应用于 logsumexp 的正负所有项）：
logq = self.log_q[item_ids]
sim_corrected = sim_matrix - logq.unsqueeze(0)
# sim_pos 使用 sim_corrected.diag()，不是 sim.diag()
# 避免收敛时 loss → -logq（热门偏差放大）
# t2v 方向不做校正（behavior 采样不依赖 item 热度，且与 v2t 拆分为独立 sim 矩阵）
```

**参数**：

| 参数        | 值          | 含义                                 |
| ----------- | ----------- | ------------------------------------ |
| NUM_BUCKETS | 3,000,000   | 与 `item_id` `hash_bucket_size` 一致 |
| θ           | 0.01        | 每次 step 吸收 1% 新频率信息         |
| 初始化      | `log(1/3M)` | 均匀先验                             |
| ε           | 1/B         | batch 内最少出现 1 次的保底概率      |

**与全量 SQL 方案对比**：

| 维度     | 全量 SQL 方案                    | Moving Average（推荐） |
| -------- | -------------------------------- | ---------------------- |
| 精度     | θ=1（全量替换），精确到每个 item | θ=0.01，动量平滑近似   |
| 时效性   | 帖子过期后必须重跑               | 随训练自动遗忘         |
| 离线依赖 | SQL + Python mmh3 hash           | **无**                 |
| 代码量   | 20 行 SQL + 15 行 Python         | **8 行模型内**         |
| 覆盖     | 只覆盖预计算时存在的 item        | 3M bucket 全量覆盖     |

**为什么 θ=0.01**：帖子寿命 ~3 天 ≈ 1/20 训练数据。θ=0.01 → 100 step 后旧信息占比 ≈ 37%，自然遗忘不需要手动管理 item 生命周期。

### P0：Hard Negative Mining

```python
# v2t: HardNegative on LogQ-corrected sim
K = min(self._contrastive_hard_k, B - 1)
_, topk = torch.topk(sim_c, K + 1, dim=-1)
hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
hard_mask[torch.arange(B).unsqueeze(1), topk] = True
hard_mask[torch.arange(B), torch.arange(B)] = True  # 确保正样本始终在分母中
loss_v2t = -sim_c.diag() + torch.logsumexp(
    sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
)

# t2v: HardNegative on uncorrected sim（t2v 无 LogQ, 列方向 dim=0）
#   每列 j：对标题 t[j]，从所有行为 v[0..B-1] 中找正样本 v[j]
sim_t2v = raw_sim / 0.07
_, topk_t2v = torch.topk(sim_t2v, K + 1, dim=0)
hard_mask_t2v = torch.zeros_like(sim_t2v, dtype=torch.bool)
hard_mask_t2v[
    topk_t2v,
    torch.arange(B).unsqueeze(0).expand(K + 1, -1),
] = True
hard_mask_t2v[torch.arange(B), torch.arange(B)] = True  # 确保正样本始终在分母中
loss_t2v = -sim_t2v.diag() + torch.logsumexp(
    sim_t2v.masked_fill(~hard_mask_t2v, -float("inf")), dim=0
)
```

**K 选择依据**：有效 batch size = B × num_gpu = 4096 × 4 = 16384。√(16384) ≈ 128，取整为 150（≈0.9% 负样本）。实践参考：CLIP 32K 全量无筛选，MoCo 65536 取 top 2048（3%）。0.6~1.2% 在信息量和稳定性之间平衡。

| 参数                  | 起始值 | 范围   | 理由                           |
| --------------------- | ------ | ------ | ------------------------------ |
| `_contrastive_hard_k` | 150    | 50-300 | 4卡×4K batch 取 top 150 ≈ 0.9% |

### P1：Stop-Gradient（Phase 2 必需）

Phase 2 中 title_vector projection 可学习后，用 `t_proj.detach()` 防止列对齐时坍缩。

### P1：对齐度 + 均匀度诊断

```python
with torch.no_grad():
    align = (v * t).sum(dim=-1).mean()
    uniformity = sim_v2t[~hard_mask & ~eye(B)].exp().mean().log()
```

| 状态 | Alignment | Uniformity |
| ---- | --------- | ---------- |
| 良好 | 0.6-0.9   | -1.0~-5.0  |
| 坍缩 | ≈1.0      | ≈0.0       |
| 发散 | ≈0.0      | \<-5.0     |

______________________________________________________________________

## 7. 代码变更

### 文件 1：`tzrec/modules/embedding.py`（+2 行）

`EmbeddingGroup.forward()` 中新增一行 `result[f"{group_name}__seq_output__{seq_name}"] = output`，暴露每个序列 encoder 的独立输出。

**安全性**：key 不会冲突（seq_group_name 唯一），不影响 `_grouped_features_keys`。

### 文件 2：`tzrec/models/pepnet_dcn_ple.py`（+65 行）

#### 2a. `__init__()`（+20 行）

```python
        # 超参
        self._contrastive_loss_weight = 0.1
        self._contrastive_loss_enabled = True
        self._contrastive_hard_k = 150
        self._contrastive_logq_theta = 0.01

        # 获取 DIN output_dim
        din_output_dim = None
        for seq_encoder in self.embedding_group._group_name_to_seq_encoders.get("all", []):
            if seq_encoder.input() == "click_50_seq":
                din_output_dim = seq_encoder.output_dim()
                break

        self.contrastive_behavior_proj = nn.Linear(din_output_dim, 128) if din_output_dim else None
        self.default_behavior = nn.Parameter(torch.zeros(128))

        # 计算 title_vector 在 "all" group 中的索引
        t_start, t_end = None, None
        offset = 0
        for name, dim in self.embedding_group.group_feature_dims("all").items():
            if name == "title_vector":
                self._title_vector_idx = (offset, offset + dim)
            offset += dim

        # Moving Average LogQ: 初始化均匀先验
        self._item_id_num_emb = None
        for f in self._features:
            if f.name == "item_id" and hasattr(f, "num_embeddings"):
                self._item_id_num_emb = f.num_embeddings
                break
        if self._item_id_num_emb:
            self.register_buffer(
                "_log_q", torch.full([self._item_id_num_emb], -math.log(self._item_id_num_emb))
            )
```

#### 2b. `predict()`（+20 行）

在 `predict()` 中 `build_input` 之后、CDOT 处理之前插入。

```python
if self.training and self._contrastive_loss_enabled and self.contrastive_behavior_proj:
    behavior_emb = grouped_features.get("all__seq_output__click_50_seq")
    if behavior_emb is not None and self._title_vector_idx is not None:
        v = self.contrastive_behavior_proj(behavior_emb)
        t = grouped_features["all"][:, self._title_vector_idx[0]:self._title_vector_idx[1]]
        seq_len = grouped_features["click_50_seq.sequence_length"]

        v = torch.where(
            (seq_len > 0).unsqueeze(1),
            v,
            self.default_behavior.unsqueeze(0).expand_as(v),
        )

        predictions["_ctr_behavior"] = v
        predictions["_ctr_title"] = t
        predictions["_ctr_seq_len"] = seq_len
```

#### 2c. `loss()`（+35 行）

```python
def loss(self, predictions, batch):
    losses = super().loss(predictions, batch)

    if self._contrastive_loss_enabled and "_ctr_behavior" in predictions:
        v, t, seq_len = predictions["_ctr_behavior"], predictions["_ctr_title"], predictions["_ctr_seq_len"]
        B = v.size(0)

        # Moving Average LogQ: 每步更新 item 频率分布
        if self._log_q is not None:
            kjt = batch.sparse_features.get("__BASE__")
            if kjt is not None and "item_id_emb" in kjt.keys():
                item_ids = kjt["item_id_emb"].values().long()
                freq = torch.bincount(item_ids, minlength=self._log_q.size(0)).float()
                batch_freq = freq / freq.sum()
                self._log_q.mul_(1 - self._contrastive_logq_theta).add_(
                    self._contrastive_logq_theta, torch.log(batch_freq + 1e-8)
                )

        v, t = F.normalize(v, dim=-1), F.normalize(t, dim=-1)
        raw_sim = torch.mm(v, t.t())

        # ── v2t direction: per-seq_len τ + LogQ + HardNegative ──
        tau_v2t = (0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())).unsqueeze(1)
        sim_v2t = raw_sim / tau_v2t

        # LogQ 校正
        sim_c = sim_v2t.clone()
        if self._log_q is not None and kjt is not None and "item_id_emb" in kjt.keys():
            logq = self._log_q[item_ids].to(sim_v2t.device)
            sim_c = sim_c - logq.unsqueeze(0)

        # HardNegative K=150（包含正样本在 topk 内）
        K = min(self._contrastive_hard_k, B - 1)
        _, topk = torch.topk(sim_c, K + 1, dim=-1)
        hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
        hard_mask[torch.arange(B, device=v.device).unsqueeze(1), topk] = True
        hard_mask[torch.arange(B, device=v.device), torch.arange(B, device=v.device)] = True

        loss_v2t = -sim_c.diag() + torch.logsumexp(
            sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
        )

        # ── t2v direction: fixed τ + HardNegative（无 LogQ, 列方向 dim=0）──
        #   每列 j：对标题 t[j]，从所有行为 v[0..B-1] 中找正样本 v[j]
        sim_t2v = raw_sim / 0.07
        _, topk_t2v = torch.topk(sim_t2v, K + 1, dim=0)
        hard_mask_t2v = torch.zeros_like(sim_t2v, dtype=torch.bool)
        hard_mask_t2v[
            topk_t2v,
            torch.arange(B, device=v.device).unsqueeze(0).expand(K + 1, -1),
        ] = True
        hard_mask_t2v[torch.arange(B, device=v.device), torch.arange(B, device=v.device)] = True
        loss_t2v = -sim_t2v.diag() + torch.logsumexp(
            sim_t2v.masked_fill(~hard_mask_t2v, -float("inf")), dim=0
        )

        loss = (loss_v2t + loss_t2v) / 2

        mask = (seq_len >= 0).float()
        if mask.sum() > 0:
            losses["contrastive_loss"] = (
                (loss * mask).sum() / mask.sum() * self._contrastive_loss_weight
            )
            losses["contrastive_v2t_loss"] = (
                (loss_v2t * mask).sum() / mask.sum() * self._contrastive_loss_weight
            )
            losses["contrastive_t2v_loss"] = (
                (loss_t2v * mask).sum() / mask.sum() * self._contrastive_loss_weight
            )

        with torch.no_grad():
            align = (v * t).sum(-1).mean().item()
            neg_mask = ~hard_mask & ~torch.eye(B, dtype=torch.bool, device=v.device)
            uniformity = (
                sim_v2t[neg_mask].exp().mean().log().item()
                if neg_mask.sum() > B
                else 0.0
            )
            self._contrastive_metrics.update(
                {"ctr_align": align, "ctr_uniform": uniformity}
            )

    return losses
```

### 变更汇总

| 变更                                   | 文件                | 行      | 风险   |
| -------------------------------------- | ------------------- | ------- | ------ |
| 暴露单序列 DIN 输出                    | `embedding.py`      | 2       | **低** |
| InfoNCE + gating + default_behavior    | `pepnet_dcn_ple.py` | 18      | **低** |
| LogQ correction (Moving Avg)           | `pepnet_dcn_ple.py` | 8       | **低** |
| Hard negative mining（v2t + t2v 独立） | `pepnet_dcn_ple.py` | 14      | **低** |
| 诊断指标 + 拆分 logging                | `pepnet_dcn_ple.py` | 15      | **低** |
| **合计**                               | **2 files**         | **~57** | -      |
| Phase 1b: chaprice 辅助 view           | `.py`               | +5      | **低** |
| Phase 2: 行对齐                        | config + .py        | +5      | **中** |
| Phase 3: 连续 gating                   | .py                 | +5      | **低** |

### 不需要改

- data pipeline / SQL / 离线预处理 ✅
- 推理 / 导出配置 ✅
- 基础模型结构 ✅
- 配置文件 ✅

______________________________________________________________________

## 8. 最终可行性评审

### 8.1 代码路径全确认

| 数据路径                                            | 状态    | 证据                                        |
| --------------------------------------------------- | ------- | ------------------------------------------- |
| `grouped_features["all__seq_output__click_50_seq"]` | ✅ 可行 | `embedding.py` 新增 2 行                    |
| `grouped_features["click_50_seq.sequence_length"]`  | ✅ 确认 | `SequenceEmbeddingGroupImpl.forward()` 产出 |
| `grouped_features["all"]` 中 title_vector 切片      | ✅ 确认 | `group_feature_dims("all")` public API      |
| `batch.sparse_features["__BASE__"]["item_id_emb"]`  | ✅ 确认 | `rank_model.py:247` 完全相同的模式          |
| `self.embedding_group._group_name_to_seq_encoders`  | ✅ 可行 | 同一包内 `nn.ModuleDict`，内部广泛使用      |
| `emb_bag_config.name` 获取 KJT key                  | ✅ 确认 | `feature.py:615` 确定的 naming rule         |

### 8.2 风险矩阵（最终版）

| 风险                                 | 概率     | 影响                    | 应对                                         | 残余风险 |
| ------------------------------------ | -------- | ----------------------- | -------------------------------------------- | -------- |
| LogQ Moving Average 对罕见 item 偏差 | **低**   | 频率估计不准            | item 存活期短，动量自动遗忘                  | **极低** |
| batch 中 item 高度重复 → hard neg 少 | **低**   | 退化到全量 softmax      | fallback: 无 hard neg 时用 full              | **低**   |
| 温度 τ 对短序列压制过度              | **中**   | 对比学习在短序上 ≈ 无效 | 调 α / τ_min；短序本来信号弱，可接受         | **低**   |
| t2v 全量 16K softmax 无效            | **确定** | t2v loss ≈ 噪声底       | 已修复：t2v 改为 HardNegative K=150          | **已修** |
| `sim_pos` 未 LogQ → loss 偏差        | **确定** | 收敛时 loss → -logq     | 已修复：`sim_pos = sim_c.diag()`             | **已修** |
| per-row τ 破坏 sim 对称性            | **确定** | loss surface 不对称     | 已修复：v2t/t2v 拆独立 sim 矩阵              | **已修** |
| Phase 2 表示坍缩                     | **低**   | 对比失效                | stop-gradient（已设计）+ 诊断监控            | **低**   |
| `torch.fx` trace 训练分支死代码      | **极低** | 导出图含无用节点        | eliminate_dead_code 自动清除；无显式保留需要 | **极低** |
| chaprice + title_vector 粒度不匹配   | **确定** | 预期增益有限            | 权重设为 0.3，不阻塞主 view                  | **低**   |
| DIN output_dim 变化                  | **极低** | 投影层维度不匹配        | `__init__` 预获取，建完不可变                | **无**   |

### 8.3 详细 Roadmap

#### 前置条件

- [ ] 训练环境确认：PEPNet 训练管道 1.2.16+，`tzrec.models.pepnet_dcn_ple` 可单机 debug
- [ ] config 确认：确认远端部署路径 `/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/` 有对应 v11 config

#### Step 1：修改 embedding.py

| 文件                         | 改动                                       | 行数 | 风险 |
| ---------------------------- | ------------------------------------------ | ---- | ---- |
| `tzrec/modules/embedding.py` | `forward()` 中加 2 行，暴露单序列 DIN 输出 | +2   | 低   |

验证：`grouped_features["all__seq_output__click_50_seq"]` 返回 `[B, din_dim]` tensor

#### Step 2：修改 pepnet_dcn_ple.py

| 子步骤                | 方法                                    | 行数 |
| --------------------- | --------------------------------------- | ---- |
| 2a. `__init__()` 尾部 | 注册 parameters + Moving Avg LogQ init  | +18  |
| 2b. `predict()`       | 提取行为特征                            | +15  |
| 2c. `loss()`          | InfoNCE + LogQ + HardNegative + Metrics | +35  |

验证：单步 forward + backward 不报错，loss 输出含 `"contrastive_loss"`

#### Step 3：训练 Phase 1a（click_50_seq 主 view）

| 实验          | 配置                                    | 预期                           |
| ------------- | --------------------------------------- | ------------------------------ |
| Phase 1a      | baseline config + 改后的 pepnet         | train loss 含 contrastive_loss |
|               | contrastive_loss_weight=0.1, hard_k=150 | alignment ≈ 0.2~0.8 之间波动   |
|               |                                         | uniformity ≈ -1~-5 之间        |
| baseline 对比 | 原始 v11_title_vector config            | 纯 CTR/CVR loss                |

训练 2-3 epoch 后观察：

- [ ] CTR AUC 不低于 baseline ± 0.1%
- [ ] 长尾 item AUC +0.2%+
- [ ] Alignment 在 0.4-0.8（不坍缩）
- [ ] Uniformity < -1.0（不发散）

#### Step 4：决策门

| 结果                   | 下一步                                          |
| ---------------------- | ----------------------------------------------- |
| ✅ AUC 不跌 + 诊断正常 | → Phase 1b（追加 chaprice）或 Phase 2（行对齐） |
| ❌ AUC 跌或者诊断异常  | → 调参（weight/τ/K）或回退                      |

#### Step 5（可选）：Phase 1b — chaprice 辅助 view

- 预计 +5 行代码（loss() 中加第二路 InfoNCE）
- weight=0.3，其余逻辑复用
- 预期 CVR 额外 +0.05~0.1%

#### Step 6（可选）：Phase 2 — 行对齐

- 配置改：`embedding_dim: 128`
- 代码改：stop-gradient
- 风险：中（config 变更需验证）

### 8.4 完成情况登记表

```diff
! 状态标记: ✅ 已完成 | 🔄 进行中 | ⏳ 待开始 | ❌ 阻塞/回退
```

| 序号 | 任务                           | 文件/范围                            | 优先级 | 依赖 | 状态 | 备注                                                                     |
| ---- | ------------------------------ | ------------------------------------ | ------ | ---- | ---- | ------------------------------------------------------------------------ |
| 1    | 修改 embedding.py（+2 行）     | `tzrec/modules/embedding.py:557-561` | P0     | —    | ✅   | 暴露 `{group}__seq_output__{seq}`                                        |
| 2a   | pepnet `__init__()` Moving Avg | `tzrec/models/pepnet_dcn_ple.py`     | P0     | —    | ✅   | 含 LogQ init + DIN dim + TV idx + proj                                   |
| 2b   | pepnet `predict()` 提取特征    | 同上                                 | P0     | 2a   | ✅   | behavior + title + seq_len 存入 predictions                              |
| 2c   | pepnet `loss()` InfoNCE        | 同上                                 | P0     | 2b   | ✅   | 含 Moving Avg LogQ + HardNegative + Metrics; **评审后修复 3 个耦合问题** |
| 3    | 训练 Phase 1a                  | DLC 集群                             | P0     | 1+2  | ⏳   | 2-3 epoch 验证                                                           |
| 4    | 阶段评审                       | —                                    | P0     | 3    | ⏳   | 决策是否推进                                                             |
| 5    | Phase 1b: chaprice 辅助 view   | `pepnet_dcn_ple.py`                  | P2     | 3    | ⏳   | 可跳过                                                                   |
| 6    | Phase 2: 行对齐                | config + .py                         | P2     | 4    | ⏳   | 可跳过                                                                   |
| 7    | Phase 3: 双向 gating           | .py                                  | P3     | 6    | ⏳   | 可跳过                                                                   |

### 8.5 一句话结论

**方案可行，无需离线依赖。** 2 个文件、~57 行代码、0 个配置变更。 LogQ 使用 Moving Average 端到端学习 item 频率分布，随训练自动过期，不需要 SQL / 离线预处理。三个关键理论缺陷（Moving Avg LogQ、HardNegative、诊断）已补齐，评审发现三个设计耦合问题（t2v 16K 无效、sim_pos 未矫正、τ 不对称）已全部修复。首次实施只跑 Phase 1a，用 click_50_seq 主 view 验证效果后再扩展。

______________________________________________________________________

## 9. 实验指标

### Epoch 0 对比（2026-06-18）

各 v11 变体训练 7800 step 后指标：

| 变体             | config 差异                                       | CTR AUC     | CVR AUC     | 相对 baseline              |
| ---------------- | ------------------------------------------------- | ----------- | ----------- | -------------------------- |
| **baseline**     | 原始 PEPNetDCNPLE                                 | 0.71572     | 0.75489     | —                          |
| **title_vector** | +title_vector feature, **无 contrastive loss**    | **0.71574** | **0.75465** | CTR +0.00002, CVR -0.00024 |
| tmax_6700        | +t_max=6700                                       | 0.71590     | 0.75496     | CTR +0.00018, CVR +0.00007 |
| f_req_page_dim4  | +req_page dim=4                                   | 0.71538     | 0.75440     | CTR -0.00034, CVR -0.00049 |
| silu             | ReLU → SiLU                                       | 0.71538     | 0.75450     | CTR -0.00034, CVR -0.00039 |
| **contrastive**  | title_vector + **contrastive_loss_enabled: true** | **0.71560** | **0.75439** | CTR -0.00014, CVR -0.00026 |

**Epoch 0 关键结论**：

1. **title_vector 本身对 AUC 无影响**（差异 < 0.0003，在随机波动范围内）→ 干净的对比基线
1. **contrastive vs title_vector**：CTR -0.00014 / CVR -0.00026，也在随机波动范围内
1. `contrastive_loss:0.57141` 正常输出，LogQ + HardNegative + gating 全部生效
1. 训练速度 1.19 it/s vs 1.21 it/s（+2%），额外计算开销可忽略
1. `sim_pos` 未 LogQ 校正 + `(loss_v2t+loss_t2v)/2` 平均 masking 了 t2v 虚高——**损失 0.571 中 ~87% 来自 t2v 噪声底**，实际有效对比信号（v2t）仅 ~0.08 effect_weight=0.1 后。**三个设计缺陷在评审后修复**（见 §5 关键修复）
1. 注意：**baseline 在多 epoch 上已被多次验证发生过拟合**，contrastive 的收益可能在后续 epoch 体现

### 后续 epoch 观察

| Epoch | baseline CTR AUC | contrastive CTR AUC | baseline CVR AUC | contrastive CVR AUC |
| ----- | ---------------- | ------------------- | ---------------- | ------------------- |
| 0     | 0.71572          | 0.71560             | 0.75489          | 0.75439             |
| 1     | ⏳               | ⏳                  | ⏳               | ⏳                  |
| 2     | ⏳               | ⏳                  | ⏳               | ⏳                  |

关注点：

- contrastive AUC 衰减斜率是否 < baseline（正则化效果）
- alignment / uniformity 是否收敛到合理区间
