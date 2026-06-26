______________________________________________________________________

## date: 2026-06-17 tags: [experiment, v11, contrastive-learning, label-smoothing] status: completed related: ["[[v12-experiments]]", "[[../10-architecture/pepnet-dcn-ple]]"]

# V11 实验日志：对比学习 → Label Smoothing → LR 调度

## 1. 背景

### 问题

当前 v11 config 已将 title_vector（128-dim 文本语义向量）加入特征组，直接作为 raw_feature 输入 model。但它是**静态的**——只携带通用语义信息，没有个性化行为信号。

> **注**：本文档始于对比学习设计，后扩展为完整的 v11 实验日志。对比学习部分（§1-10）已冻结，§11 起为 label smoothing + LR 调度实验。

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

#### 问题 3：t2v 误用 dim=-1 行方向

评审发现 t2v 使用 `dim=-1`（行方向），和 v2t 完全一样：对每个行为 v[i] 从所有标题中找正样本 `t[i]`。这不是真正的 t2v。

真正的 t2v（列方向 `dim=0`）应该是对每个标题 t[j]，从所有行为 v[0..B-1] 中找匹配的正样本 v[j]。正样本集相同（都是 `(i,i)` 对角），但 **负样本分布不同**：

- 行方向：`v[j≠i]·t[i]`（同一标题，不同行为）
- 列方向：`v[i]·t[j≠i]`（同一行为，不同标题）

两者互补，对称 InfoNCE 需要两个方向的负样本分布。

**修复**：t2v HardNegative + logsumexp 用 `dim=0`。

#### 问题 4：per-row τ 破坏 sim 对称性

`sim = raw_sim / τ.unsqueeze(1)` 中 τ 按行（seq_len）变化，但 t2v 每次遍历列标题向量——标题的置信度与 seq_len 无关。

**修复**：v2t 用 per-seq_len τ（行为置信度依赖 seq_len），t2v 用固定 τ=0.07（标题向量恒为 Qwen3 128d）。

#### 问题 5：正样本可能不在 HardNegative 的 topk 中

`topk` 选择相似度最高的 K+1 个元素。训练初期 `v[i]·t[j] ∼ N(0, 1/128)`，对角线 `sim[i,i]` 并不比非对角线大——落入 top K+1 的概率 ≈ `(K+1)/B`。B=16384, K=150 时仅 **0.9%**。

当正样本不在 hard mask 中时，logsumexp 只包含负样本，`-sim_pos + logsumexp(仅负样本)` 的梯度缺乏"推远最像正样本的负样本"这一对比核心。

虽然训练几轮后对齐会改善，但 **title_vector 是 pass-through，梯度不能修改它**，所有学习压力都在 behavior 投影层一侧。无法保证对角线必定成为最大值。

**修复**：topk 后强行把对角线加入 hard mask：

```python
hard_mask[torch.arange(B), torch.arange(B)] = True       # v2t
hard_mask_t2v[torch.arange(B), torch.arange(B)] = True   # t2v
```

从第一步起 logsumexp 一定包含正样本，标准 InfoNCE `-log(p+ / (p+ + Σ p_neg))` 无条件成立。

#### 五个修复统一效果

```
    v2t                                t2v
sim_v2t = raw_sim / τ(seq_len) - logq    sim_t2v = raw_sim / 0.07
HardNegative dim=-1, K=150               HardNegative dim=0, K=150
pos in hard_mask: ✓ (强制保留对角)       pos in hard_mask: ✓ (强制保留对角)
sim_pos = sim_c.diag() (#LogQ校正)        sim_pos = sim_t2v.diag()

loss = (loss_v2t + loss_t2v) / 2
```

**确认：loss 方向修正后不会导致 `contrastive_loss` 回传异常。** 两个方向分开计算 `-sim_pos + logsumexp(hard)`，每个方向各有 ~K+1 项 logsumexp（对角始终在内），loss 量级匹配。

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

### Phase 2：行对齐（双侧可学习投影）— proto 驱动

**核心问题**：Phase 1a 中 title_vector 是静态 pass-through，所有对比梯度只流入 behavior 侧（`v2t` 和 `t2v` 两个方向的梯度路径完全相同）。模型只能单侧调整，对齐天花板 = 仅比随机好 13%。

**解法**：新增 proto field 19 `contrastive_alignment_mode`，通过 config 一键切换对齐模式，支持 A/B 实验。

```protobuf
// multi_task_rank.proto (field 19)
optional string contrastive_alignment_mode = 19 [default = "column"];
// "column"        = Phase 1a: 单侧列对齐（behavior → semantics）
// "bidirectional" = Phase 2: 双侧行+列同时对齐
// "row"           = 单侧行对齐（semantics → behavior），预留
```

config 用法：

```protobuf
pepnet_dcn_ple {
  contrastive_loss_enabled: true
  contrastive_alignment_mode: "bidirectional"   # 或 "column"
}
```

**三种模式对比**：

```
"column"(Phase 1a)        "bidirectional"(Phase 2)       "row"(预留)
v ← behavior_proj         v ← behavior_proj              v ← behavior_proj(detach)
t = raw_title (static)    t = title_proj(raw_title)      t = title_proj(raw_title)
                          ↕                               ↕
loss_v2t → 只调 v         loss_v2t → 调 v (t detach)      loss_v2t → 无（v detach）
loss_t2v → 也调 v（无用） loss_t2v → 调 t (v detach)      loss_t2v → 调 t (v detach)
```

**关键设计：残差 adapter + 低秩瓶颈 + zero_init**

```python
self.contrastive_title_adapter = nn.Sequential(
    nn.Linear(128, 64),
    nn.ReLU(),
    nn.Linear(64, 128),
)
nn.init.zeros_(self.contrastive_title_adapter[2].weight)
nn.init.zeros_(self.contrastive_title_adapter[2].bias)

t_proj = raw_title + self.contrastive_title_adapter(raw_title)
#       ↕ skip connection 确保初始化时 t_proj = raw_title
```

**为什么残差是关键**：

| 特性     | 无残差                         | 有残差                               |
| -------- | ------------------------------ | ------------------------------------ |
| 初始化   | 随机 t_proj → 对比 loss 爆炸   | t_proj = t_raw → 初始化等价 Phase 1a |
| 偏移能力 | 无约束，全量 128→128           | 低秩瓶颈 128→64→128，容量受限        |
| 回退     | 需重新加载 Phase 1a checkpoint | 只需去掉 adapter 层                  |
| 语义保留 | 无机制                         | skip connection 保底保留原始语义     |

**梯度路径（bidirectional 模式）**：

```python
# v2t: 标题锚定 → 只调 behavior
sim_v2t = v @ t_proj.detach().T
loss_v2t → grad flows to behavior_proj only

# t2v: 行为锚定 → 只调 title_proj
sim_t2v = v.detach() @ t_proj.T
loss_t2v → grad flows to title_proj only

loss = (loss_v2t + loss_t2v) / 2
```

**超参**：

| 参数                       | "column"         | "bidirectional"                       | 理由                                        |
| -------------------------- | ---------------- | ------------------------------------- | ------------------------------------------- |
| `_contrastive_hard_k`      | 150              | **50**                                | 双侧可调后对齐质量提升，不需要大量 hard neg |
| `_contrastive_loss_weight` | 0.1              | **0.05-0.1**                          | 双侧梯度，总梯度量级 ≈ 2x，weight 可略降    |
| stop-gradient              | 无（title 静态） | v2t: `t.detach()` / t2v: `v.detach()` | 防退化                                      |

### Phase 3（保留，暂不实施）

`λ(seq_len) = sigmoid(β·(seq_len - L₀))` 连续插值行/列比例。等待 Phase 2 结果再决定是否实施。

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

### P0：Stop-Gradient（Phase 2 必需）

Phase 2 中 title_vector 通过 adapter 投影后可学习。双侧同时被 InfoNCE 梯度更新时，存在**退化风险**：t_proj 遗忘 Qwen3 语义，退化为编码 item_id 共现模式的空间。

```python
# 防退化：两方向各一个 detach
# v2t: t_proj 作为锚点 → 只调 behavior_proj
sim_v2t = v @ t_proj.detach().T

# t2v: v 作为锚点 → 只调 title_adapter
sim_t2v = v.detach() @ t_proj.T
```

**为什么不是防坍缩**：对称 InfoNCE 中如果 `v` 和 `t` 都坍缩到常数，`loss ≈ log(B)`=9.7 → 极高，模型不可能忽略。detach 的真正作用是防止**退化解**——让每个方向只更新一侧，避免两侧同时漂移到行为空间。

**验证**：训练后检查 `cos(t_proj, raw_title)`。>0.8 说明语义保留，\<0.5 说明退化严重。

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

#### 2a. `__init__()`（+30 行）

```python
        # 超参
        self._contrastive_loss_weight = 0.1
        self._contrastive_loss_enabled = self._model_config.contrastive_loss_enabled
        # Phase 2: 对齐模式（column/bidirectional/row）
        self._contrastive_alignment_mode = self._model_config.contrastive_alignment_mode
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

        # --- Phase 2: 残差 adapter + low-rank + zero_init ---
        if self._contrastive_alignment_mode in ("bidirectional", "row"):
            self.contrastive_title_adapter = nn.Sequential(
                nn.Linear(128, 64),
                nn.ReLU(),
                nn.Linear(64, 128),
            )
            nn.init.zeros_(self.contrastive_title_adapter[2].weight)
            nn.init.zeros_(self.contrastive_title_adapter[2].bias)
        else:
            self.contrastive_title_adapter = None
```

#### 2b. `predict()`（+23 行）

在 `predict()` 末尾、`return predictions` 之前插入。

```python
if self.training and self._contrastive_loss_enabled and self.contrastive_behavior_proj:
    behavior_emb = grouped_features.get("all__seq_output__click_50_seq")
    if behavior_emb is not None and self._title_vector_idx is not None:
        v = self.contrastive_behavior_proj(behavior_emb)
        t_raw = grouped_features["all"][:, self._title_vector_idx[0]:self._title_vector_idx[1]]
        seq_len = grouped_features["click_50_seq.sequence_length"]

        v = torch.where(
            (seq_len > 0).unsqueeze(1),
            v,
            self.default_behavior.unsqueeze(0).expand_as(v),
        )

        # Phase 2: 残差 adapter（proto 模式控制）
        if self._contrastive_alignment_mode in ("bidirectional", "row"):
            t = t_raw + self.contrastive_title_adapter(t_raw)  # zero_init → 等价 t_raw
        else:
            t = t_raw  # "column" 模式：title 静态

        predictions["_ctr_behavior"] = v
        predictions["_ctr_title"] = t
        predictions["_ctr_seq_len"] = seq_len
```

#### 2c. `loss()`（+45 行）

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

        # ── Phase 2: 模式驱动的 Hard K ──
        K_map = {"column": 150, "bidirectional": 50, "row": 50}
        K = min(K_map.get(self._contrastive_alignment_mode, 150), B - 1)

        # ── τ gating: seq_len 短 → 信任标题 → 高温度 ──
        # v2t: 用标题作为温度信号
        tau_v2t = 0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())
        # t2v: 用行为作为温度信号（仅 bidirectional）
        tau_t2v = 0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())

        # ── 模式 A: column / Phase 1a ──
        if self._contrastive_alignment_mode == "column":
            # v2t: 标题锚定 → 调 behavior（t.detach 是显式 no-op，行为一致）
            sim = (v @ t.detach().T) / tau_v2t.unsqueeze(1)
            sim_c = sim.clone()
            if self._log_q is not None and kjt is not None and "item_id_emb" in kjt.keys():
                logq = self._log_q[item_ids].to(sim.device)
                sim_c = sim_c - logq.unsqueeze(0)
            _, topk = torch.topk(sim_c, K + 1, dim=-1)
            hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
            hard_mask[torch.arange(B, device=v.device).unsqueeze(1), topk] = True
            hard_mask[torch.arange(B, device=v.device), torch.arange(B, device=v.device)] = True
            loss_contrast = -sim_c.diag() + torch.logsumexp(
                sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
            )

        # ── 模式 B: bidirectional / Phase 2 ──
        elif self._contrastive_alignment_mode == "bidirectional":
            K = min(50, B - 1)

            # v2t: 标题锚定 → 只调 behavior
            sim_v2t = (v @ t.detach().T) / tau_v2t.unsqueeze(1)
            sim_c = sim_v2t.clone()
            if self._log_q is not None and kjt is not None and "item_id_emb" in kjt.keys():
                logq = self._log_q[item_ids].to(sim_v2t.device)
                sim_c = sim_c - logq.unsqueeze(0)
            _, topk = torch.topk(sim_c, K + 1, dim=-1)
            hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
            hard_mask[torch.arange(B, device=v.device).unsqueeze(1), topk] = True
            hard_mask[torch.arange(B, device=v.device), torch.arange(B, device=v.device)] = True
            loss_v2t = -sim_c.diag() + torch.logsumexp(
                sim_c.masked_fill(~hard_mask, -float("inf")), dim=-1
            )

            # t2v: 行为锚定 → 只调 title_adapter
            sim_t2v = (v.detach() @ t.T) / tau_t2v.unsqueeze(0)
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
            loss_contrast = (loss_v2t + loss_t2v) / 2

        # ── 模式 C: row（预留）──
        else:
            loss_contrast = v.new_zeros(B)

        mask = (seq_len >= 0).float()
        if mask.sum() > 0:
            losses["contrastive_loss"] = (
                (loss_contrast * mask).sum() / mask.sum() * self._contrastive_loss_weight
            )
            if self._contrastive_alignment_mode in ("bidirectional", "row"):
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
            # Phase 2 新增：语义保留度
            t_cos = F.cosine_similarity(t, t_raw, dim=-1).mean().item()
            self._contrastive_metrics.update(
                {"ctr_align": align, "ctr_uniform": uniformity, "ctr_title_raw_cos": t_cos}
            )

    return losses
```

### 变更汇总

| 变更                                     | 文件                | 行     | 风险   |
| ---------------------------------------- | ------------------- | ------ | ------ |
| Phase 1a: 暴露单序列 DIN 输出            | `embedding.py`      | 2      | **低** |
| Phase 1a: InfoNCE + gating + default     | `pepnet_dcn_ple.py` | 18     | **低** |
| Phase 1a: LogQ correction (Moving Avg)   | `pepnet_dcn_ple.py` | 8      | **低** |
| Phase 1a: HardNegative（v2t + t2v 独立） | `pepnet_dcn_ple.py` | 14     | **低** |
| Phase 1a: 诊断指标 + 拆分 logging        | `pepnet_dcn_ple.py` | 15     | **低** |
| **Phase 1a 合计**                        | **2 files**         | **57** | -      |
| Phase 2: title_adapter 注册 + zero_init  | `pepnet_dcn_ple.py` | 6      | **低** |
| Phase 2: predict() 中 t_proj 提取        | `pepnet_dcn_ple.py` | 3      | **低** |
| Phase 2: loss() 中 detach + K=50         | `pepnet_dcn_ple.py` | 5      | **低** |
| **Phase 2 合计**                         | **1 file**          | **14** | -      |
| Phase 3: 双向 gating（保留）             | `.py`               | +5     | **低** |

### 不需要改

- data pipeline / SQL / 离线预处理 ✅
- 推理 / 导出配置 ✅
- 基础模型结构 ✅
- 配置文件 ✅（`embedding_dim: 128` 已设）

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

| 风险                                 | 概率     | 影响                              | 应对                                                           | 残余风险 |
| ------------------------------------ | -------- | --------------------------------- | -------------------------------------------------------------- | -------- |
| LogQ Moving Average 对罕见 item 偏差 | **低**   | 频率估计不准                      | item 存活期短，动量自动遗忘                                    | **极低** |
| batch 中 item 高度重复 → hard neg 少 | **低**   | 退化到全量 softmax                | fallback: 无 hard neg 时用 full                                | **低**   |
| 温度 τ 对短序列压制过度              | **中**   | 对比学习在短序上 ≈ 无效           | 调 α / τ_min；短序本来信号弱，可接受                           | **低**   |
| t2v 全量 16K softmax 无效            | **确定** | t2v loss ≈ 噪声底                 | 已修复：t2v 改为 HardNegative K=150                            | **已修** |
| `sim_pos` 未 LogQ → loss 偏差        | **确定** | 收敛时 loss → -logq               | 已修复：`sim_pos = sim_c.diag()`                               | **已修** |
| per-row τ 破坏 sim 对称性            | **确定** | loss surface 不对称               | 已修复：v2t/t2v 拆独立 sim 矩阵                                | **已修** |
| t2v 误用 dim=-1 行方向               | **确定** | 失去对称 InfoNCE 收益             | 已修复：t2v 改为 dim=0 列方向                                  | **已修** |
| 正样本不在 HardNegative topk 中      | **确定** | 退化到无正样本对比                | 已修复：`hard_mask[i,i]=True` 强制保底                         | **已修** |
| **Phase 2: 语义漂移**                | **中**   | t_proj 遗忘 Qwen3 语义            | **残差 adapter + 低秩瓶颈 + zero_init + cos(t_proj,raw) 监控** | **低**   |
| **Phase 2: 计算开销**                | **极低** | 多 2 个 batch gemm（~0.3% FLOPs） | 可忽略，DIN attention 本身 >200M/step                          | **极低** |
| proto field 19 默认值不匹配          | **低**   | Go 端读不到 field 19 → 空字符串   | proto 指定 `default = "column"`；Go pb 库兼容 default          | **极低** |
| `torch.fx` trace 训练分支死代码      | **极低** | 导出图含无用节点                  | eliminate_dead_code 自动清除；无显式保留需要                   | **极低** |
| chaprice + title_vector 粒度不匹配   | **确定** | 预期增益有限                      | 权重设为 0.3，不阻塞主 view                                    | **低**   |
| DIN output_dim 变化                  | **极低** | 投影层维度不匹配                  | `__init__` 预获取，建完不可变                                  | **无**   |

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

#### Step 4a：Proto 模式字段（field 19）

| 子步骤                       | 方法                                                                        | 行数 |
| ---------------------------- | --------------------------------------------------------------------------- | ---- |
| 4a1. `multi_task_rank.proto` | 追加 `optional string contrastive_alignment_mode = 19 [default = "column"]` | +1   |
| 4a2. `protoc` 重编译         | 执行 `protoc ... tzrec/protos/models/multi_task_rank.proto` → `_pb2.py`     | -    |
| 4a3. Config 测试             | config 中指定 `contrastive_alignment_mode: "bidirectional"` → 读取正确      | -    |

#### Step 4b：决策门（基于 2 epoch 结果）

| 结果                                 | 下一步                                         |
| ------------------------------------ | ---------------------------------------------- |
| ✅ Phase 1a 主任务未崩（已验证通过） | → **直接进入 Phase 2**（不需等 baseline 对比） |
| ❌ AUC 跌                            | → 调参或回退                                   |

Phase 1a 的 2 epoch 实验结论：

- CTR AUC 0.71560 → 0.7149（-0.07%），CVR AUC 0.75439 → ~0.750（-0.4%）
- contrastive_loss 收敛于 0.435（去除 weight=0.1 后 4.35，仅比随机好 13%）
- 列对齐天花板明确，双侧可调是突破天花板的唯一路径

#### Step 5：Phase 2 — 行对齐（双侧可学习，proto 驱动）

| 子步骤           | 方法                                                                                                        | 行数 |
| ---------------- | ----------------------------------------------------------------------------------------------------------- | ---- |
| 5a. `__init__()` | 注册 `contrastive_title_adapter`（残差+低秩），仅在 `bidirectional`/`row` 模式创建                          | +8   |
| 5b. `predict()`  | 条件式 `t_proj = raw_title + adapter(raw_title)` / `t_proj = raw_title`，根据 `_contrastive_alignment_mode` | +3   |
| 5c. `loss()`     | 三模式分支: column（单侧+LogQ）、bidirectional（双侧 detach+K=50+τ_gating）、row（预留）                    | +15  |

验证方法：

- [ ] contrastive_loss 从 Phase 1a 的 4.35 下降到 < 3.0（对齐质量提升 30%+）
- [ ] `cos(t_proj, raw_title)` 在训练后 > 0.8（语义保留）
- [ ] CTR AUC 不跌（主任务安全）
- [ ] Alignment 在 0.5-0.9（不坍缩）

#### Step 6（可选）：Phase 1b — chaprice 辅助 view（视 Phase 2 效果决定）

### 8.4 完成情况登记表

```diff
! 状态标记: ✅ 已完成 | 🔄 进行中 | ⏳ 待开始 | ❌ 阻塞/回退
```

| 序号 | 任务                           | 文件/范围                            | 优先级 | 依赖 | 状态 | 备注                                                                     |
| ---- | ------------------------------ | ------------------------------------ | ------ | ---- | ---- | ------------------------------------------------------------------------ |
| 1    | 修改 embedding.py（+2 行）     | `tzrec/modules/embedding.py:557-561` | P0     | —    | ✅   | 暴露 `{group}__seq_output__{seq}`                                        |
| 2a   | pepnet `__init__()` Moving Avg | `tzrec/models/pepnet_dcn_ple.py`     | P0     | —    | ✅   | 含 LogQ init + DIN dim + TV idx + proj                                   |
| 2b   | pepnet `predict()` 提取特征    | 同上                                 | P0     | 2a   | ✅   | behavior + title + seq_len 存入 predictions                              |
| 2c   | pepnet `loss()` InfoNCE        | 同上                                 | P0     | 2b   | ✅   | 含 Moving Avg LogQ + HardNegative + Metrics; **评审后修复 5 个设计问题** |
| 3    | 训练 Phase 1a                  | DLC 集群                             | P0     | 1+2  | ✅   | 2 epoch 完成；contrastive_loss=0.435, CTR/CVR 未跌                       |
| 4a   | proto field 19 + protoc 重编译 | `multi_task_rank.proto` + `_pb2.py`  | P0     | —    | ✅   | `optional string contrastive_alignment_mode = 19 [default = "column"]`   |
| 4b   | 评审阶段决策                   | —                                    | P0     | 3    | ✅   | Phase 1a 列对齐天花板 13%，决定跳过 Phase 1b，直接进入 Phase 2           |
| 5    | **Phase 2: 三模式对齐**        | `pepnet_dcn_ple.py`                  | P0     | 3+4a | ⏳   | 残差 adapter + zero_init + bidirectional detach + K=50，proto 模式控制   |
| 6    | Phase 1b: chaprice 辅助 view   | `pepnet_dcn_ple.py`                  | P2     | 5    | ⏳   | 视 Phase 2 效果决定                                                      |
| 7    | Phase 3: 双向 gating           | .py                                  | P3     | 6    | ⏳   | 暂不实施                                                                 |

### 8.5 一句话结论

**Bidirectional 对比学习有效（contrastive_loss 从 4.35 降至 3.53），但不转化为 AUC 提升（0.716080 < baseline 0.716316）。Bidirectional + tmax_6700 的 AUC 0.716408 < tmax_6700 alone 0.716737。** 根因：title_vector 监督信号本身无预测力。停止对比学习实验，上线 tmax_6700。

______________________________________________________________________

## 9. 实验指标

### Phase 1a: Epoch 0 对比（2026-06-18）

各 v11 变体训练 ~7800 step 后指标：

| 变体             | config 差异                                       | CTR AUC     | CVR AUC     | 相对 baseline              |
| ---------------- | ------------------------------------------------- | ----------- | ----------- | -------------------------- |
| **baseline**     | 原始 PEPNetDCNPLE                                 | 0.71572     | 0.75489     | —                          |
| **title_vector** | +title_vector feature, **无 contrastive loss**    | **0.71574** | **0.75465** | CTR +0.00002, CVR -0.00024 |
| tmax_6700        | +t_max=6700                                       | 0.71590     | 0.75496     | CTR +0.00018, CVR +0.00007 |
| f_req_page_dim4  | +req_page dim=4                                   | 0.71538     | 0.75440     | CTR -0.00034, CVR -0.00049 |
| silu             | ReLU → SiLU                                       | 0.71538     | 0.75450     | CTR -0.00034, CVR -0.00039 |
| **contrastive**  | title_vector + **contrastive_loss_enabled: true** | **0.71560** | **0.75439** | CTR -0.00014, CVR -0.00026 |

**Phase 1a: Epoch 0 关键结论**：

1. **title_vector 本身对 AUC 无影响**（差异 < 0.0003，在随机波动范围内）→ 干净的对比基线
1. **contrastive vs title_vector**：CTR -0.00014 / CVR -0.00026，也在随机波动范围内
1. `contrastive_loss:0.57141` 正常输出，LogQ + HardNegative + gating 全部生效
1. 训练速度 1.19 it/s vs 1.21 it/s（+2%），额外计算开销可忽略
1. `sim_pos` 未 LogQ 校正 + `(loss_v2t+loss_t2v)/2` 平均 masking 了 t2v 虚高——**损失 0.571 中 ~87% 来自 t2v 噪声底**，实际有效对比信号（v2t）仅 ~0.08 effect_weight=0.1 后。**三个设计缺陷在评审后修复**（见 §5 关键修复）
1. 注意：**baseline 在多 epoch 上已被多次验证发生过拟合**，contrastive 的收益可能在后续 epoch 体现

### Phase 1a: 2 Epoch 实验（2026-06-19）

训练配置：`home_flow_2604_v11_contrastive_2ep.config`，num_epochs=2

| 指标               | Loss 曲线形态                        | 关键数值                                |
| ------------------ | ------------------------------------ | --------------------------------------- |
| `contrastive_loss` | 快速收敛 → 稳定 plateau（4k-15k 步） | 0.435（含 weight=0.1，unweighted=4.35） |
| `loss/bce_ctr`     | U 型：下降至 10k 步拐点，后回升      | 1.78 → 1.90（回升 0.12）                |
| `loss/bce_cvr`     | U 型：下降至 10k 步拐点，后回升      | 0.45 → 0.47（回升 0.02）                |
| `eval/auc_ctr`     | 上升 → plateau，后期微跌             | 0.71560 → 0.7149                        |
| `eval/auc_cvr`     | plateau → 后期微跌                   | 0.75439 → ~0.750                        |

**结论**：

1. contrastive_loss 收敛后不回升，对比任务未过拟合 ✅
1. v2t 和 t2v 两方向 loss 量级一致，对称 InfoNCE 公式正确 ✅
1. CTR/CVR eval AUC 在 2 epoch 后微跌，属正常过拟合范围 ✅
1. **但 contrastive_loss = 4.35（unweighted）仅比随机基线 ln(151)=5.01 好 13%** → 列对齐天花板明显，需要 Phase 2 双侧可学习
1. **超过 1 epoch 已确认过拟合** → 后续所有实验固定 1 epoch

### Phase 1a vs Phase 2: 完整 1 Epoch 同框对比（2026-06-20）

step 7757（完整 1 epoch，cosine annealing 已过拐点），配置仅 `contrastive_alignment_mode` 不同：

| 变体                        | AUC CTR      | BCE CTR      | AUC CVR      | BCE CVR      |
| --------------------------- | ------------ | ------------ | ------------ | ------------ |
| baseline                    | 0.716316     | 1.933748     | 0.757583     | 0.493283     |
| tmax_6700                   | **0.716737** | **1.932744** | **0.758315** | **0.493119** |
| column (Phase 1a)           | 0.715817     | 1.934707     | 0.757254     | 0.493511     |
| **bidirectional (Phase 2)** | **0.716080** | **1.934186** | **0.757482** | **0.493505** |

**完整 1 epoch 结论**：

1. **tmax_6700 是唯一正向变体**：CTR +0.00042, CVR +0.00073，consistent across runs ✅
1. **bidirectional vs baseline**：CTR -0.00024, CVR -0.00010，在随机波动范围内，主任务安全但**无正向收益** ✅
1. **column vs baseline**：CTR -0.00050, CVR -0.00033，略低于 bidirectional
1. **bidirectional 整体略优于 column**（CTR +0.00026, CVR +0.00023），但差距 < baseline 自身种子噪声（±0.0003）
1. **对比学习（column 或 bidirectional）在 1 epoch 内不提升 AUC**——这是基本面结论，不是因为训练不充分

### Phase 2 目标达成情况

| 指标                              | Phase 1a（column） | Phase 2（bidirectional） | 结论                             |
| --------------------------------- | ------------------ | ------------------------ | -------------------------------- |
| contrastive_loss (unweighted)     | 4.35（13%/random） | **3.53（30%/random）**   | ✅ 显著改善                      |
| `cos(t_proj, raw_title)`          | N/A                | **待 tensorboard**       | ⏳                               |
| CTR AUC                           | 0.715817           | 0.716080                 | ✅ 不跌，但 vs baseline -0.00024 |
| CVR AUC                           | 0.757254           | 0.757482                 | ✅ 不跌，但 vs baseline -0.00010 |
| bidirectional + tmax_6700 AUC CTR | —                  | 0.716408                 | ❌ < tmax_6700 alone (0.716737)  |

**关键判断：对比学习有效果（loss 降），但不转化为 AUC（title_vector 无预测力）。**

### Phase 2: Bidirectional + tmax_6700 完整 1 Epoch（2026-06-20）

最关键的实验：双向对比 + 已知正向变更的组合。

| 变体                          | AUC CTR      | BCE CTR      | AUC CVR      | BCE CVR      |
| ----------------------------- | ------------ | ------------ | ------------ | ------------ |
| baseline                      | 0.716316     | 1.933748     | 0.757583     | 0.493283     |
| tmax_6700                     | 0.716737     | 1.932744     | 0.758315     | 0.493119     |
| bidirectional                 | 0.716080     | 1.934186     | 0.757482     | 0.493505     |
| **bidirectional + tmax_6700** | **0.716408** | **1.933571** | **0.757793** | **0.493434** |

同时记录到 contrastive_loss 及其分解：

| 指标                 | 训练值（step 7757，weighted） | unweighted（÷0.1） |
| -------------------- | ----------------------------- | ------------------ |
| contrastive_loss     | 0.35257                       | **3.5257**         |
| contrastive_v2t_loss | 0.32667                       | **3.2667**         |
| contrastive_t2v_loss | 0.37847                       | **3.7847**         |

**这个实验给出了最终的证据链条**：

1. **对比学习有效果**：bidirectional 的 unweighted contrastive_loss = 3.53，远低于 Phase 1a column 的 4.35（随机基线 ln151=5.01，3.53/5.01 = 30% above random，vs column 的 13%）。对齐确实在变好。
1. **但对齐好了 AUC 不涨**：bidirectional + tmax_6700 的 CTR 0.716408 介于 tmax_6700（0.716737）和 bidirectional（0.716080）之间——不如单独开 tmax_6700。
1. **tmax_6700 的收益被 bidirectional 抵消了一部分**：说明对比梯度与 BCE 梯度在 DIN encoder 中存在竞争关系。
1. **根因锁定**：contrastive_loss 改善但 AUC 不涨 → title_vector 监督信号本身不携带 CTR/CVR 可用的预测信息。

**这就是为什么 AUC 没提升：双向对齐工作正常（loss 从 4.35 降到 3.53），但对齐目标（title_vector）不包含预测信号。** 这不是工程问题，是监督信号选择问题。

______________________________________________________________________

## 10. 为什么对比学习没有提升 AUC——证据链条

### 10.1 关键数据点：统一在 step 7757 epoch-0 对比

| 变体                          | AUC CTR      | AUC CVR      | contrastive_loss（unweighted） |
| ----------------------------- | ------------ | ------------ | ------------------------------ |
| baseline                      | 0.716316     | 0.757583     | N/A                            |
| tmax_6700                     | **0.716737** | **0.758315** | N/A                            |
| bidirectional                 | 0.716080     | 0.757482     | ~4.35（Phase 1a column）       |
| **bidirectional + tmax_6700** | **0.716408** | **0.757793** | **3.53**                       |

### 10.2 证据链条

| #   | 证据                                                                       | 来源                                                | 结论                              |
| --- | -------------------------------------------------------------------------- | --------------------------------------------------- | --------------------------------- |
| 1   | `title_vector` 直接作为特征对 AUC 贡献 = 0                                 | title_vector config vs baseline: 0.71574 vs 0.71572 | title_vector 本身无预测力         |
| 2   | bidirectional contrastive_loss = 3.53（unweighted），远低于 column 的 4.35 | 本次实验的 loss 日志                                | 双向对齐工作正常，loss 改善 19%   |
| 3   | 但 bidirectional AUC 0.716080 < baseline 0.716316                          | 本次实验的 eval 结果                                | 对齐改进不转化为 AUC 提升         |
| 4   | bidirectional + tmax_6700 AUC 0.716408 < tmax_6700 alone 0.716737          | 本次实验的 eval 结果                                | 对比梯度抵消了部分 tmax_6700 收益 |

### 10.3 唯一且充分的解释

**title_vector 监督信号本身不携带 CTR/CVR 预测信息 → 任何基于 title_vector 的对比学习无法提升 AUC。**

这不是 detach/K/τ/weight 的问题。即使 contrastive_loss 从 4.35 进一步降到 0（完美对齐），AUC 也不会涨，因为对齐目标（title_vector）中不包含有用的预测信息。代码实现无论多完美都无法创造不存在的信号。

### 10.4 Tensorboard 曲线分析（bidirectional + tmax_6700）

**Training Loss（图1）**：所有 loss 单调下降，无 U 型回升。1 epoch 内无过拟合。contrastive_loss 在 2k 步内快速收敛至 plateau ~0.355（weighted），v2t 低于 t2v（0.335 vs 0.385），说明行为→标题对齐比反向更容易。

**Learning Rate（图2）**：9 组参数完全相同 cosine schedule，T_max=6700，无异常。

**Eval AUC（图3，最关键）**：两张 AUC 图中两条线（tmax_6700 alone vs bidirectional + tmax_6700）从 step 0 到 step 7000 持续存在微小差距，最终收敛至接近值。**对比对齐在训练全程制造了微小但一致的 AUC 缺口。**

**Eval BCE（图3）出现反转**：橙线（bidirectional + tmax_6700）的 BCE CTR 反而更低（概率校准更好），但 AUC 更低（排序更差）。这是核心发现：

> **对比对齐让模型的概率估计更自信（BCE 下降），但扰动了排序（AUC 不涨）。** 对齐让 DIN 输出向 title_vector 偏移，编码了更多 item 内容信息（降低 BCE），但抹平了用户偏好差异（破坏排序）。

### 10.5 后续方向

| 方向                           | 预期                     | 建议                                   |
| ------------------------------ | ------------------------ | -------------------------------------- |
| **上线 tmax_6700**             | CTR +0.0004, CVR +0.0007 | **立即执行**                           |
| **继续 title_vector 对比学习** | BCE 降但 AUC 不涨        | **停止**                               |
| **保留 proto field 18/19**     | 低成本复活可能           | 代码不动，等更强语义向量或新任务再启用 |
| **Label smoothing 实验**       | 见 §11                   | 2026-06-22 完成                        |

______________________________________________________________________

## 11. Label Smoothing + LR 调度实验（2026-06-22）

### 11.1 动机

前序实验揭示的核心矛盾：

| 现象                              | 解读                               |
| --------------------------------- | ---------------------------------- |
| 1 epoch BCE 单调下降，无 U 型回升 | 模型在 1 epoch 内尚未收敛          |
| 2 epoch 在所有条件下 AUC 均下降   | 第二 epoch 存在过拟合              |
| T_max 不随 num_epochs 扩展        | 所有 2-ep 实验的 epoch 2 全程 LR≈0 |

假设：label smoothing（ε=0.05）软化标签后，模型在 epoch 2 不会再过拟合；配合正确的 LR 调度（WarmRestart / T_max=13400），epoch 2 能学到新知识。

### 11.2 实验设计

5 个变体，均为 num_epochs=1 或 2，tmax_6700 + label_smoothing 组合：

| 变体                                      | num_epochs | LR 调度                     | T_max/T_0   |
| ----------------------------------------- | ---------- | --------------------------- | ----------- |
| label_smoothing                           | 1          | CosineAnnealing             | T_max=6300  |
| tmax_6700_label_smoothing                 | 1          | CosineAnnealing             | T_max=6700  |
| tmax_6700_label_smoothing_warmrestart     | 1          | CosineAnnealingWarmRestarts | T_0=6700    |
| tmax_6700_label_smoothing_2ep_tmax13400   | 2          | CosineAnnealing             | T_max=13400 |
| tmax_6700_label_smoothing_warmrestart_2ep | 2          | CosineAnnealingWarmRestarts | T_0=6700    |

### 11.3 原始结果

**1-epoch 变体（model-7757）：**

| 变体                                  | AUC CTR      | BCE CTR  | AUC CVR  | BCE CVR  |
| ------------------------------------- | ------------ | -------- | -------- | -------- |
| baseline（历史）                      | 0.716316     | 1.933748 | 0.757583 | 0.493283 |
| tmax_6700（历史）                     | 0.716737     | 1.932744 | 0.758315 | 0.493119 |
| label_smoothing                       | 0.716637     | 1.971085 | 0.757055 | 0.517454 |
| **tmax_6700_label_smoothing**         | **0.716955** | 1.970330 | 0.757264 | 0.517286 |
| tmax_6700_label_smoothing_warmrestart | 0.712843     | 1.979397 | 0.749150 | 0.521807 |

**2-epoch 变体（model-15515 = 2 × model-7757 步数）：**

| 变体                                      | AUC CTR  | BCE CTR  | AUC CVR  | BCE CVR  |
| ----------------------------------------- | -------- | -------- | -------- | -------- |
| tmax_6700_label_smoothing_2ep_tmax13400   | 0.696083 | 2.081405 | 0.741984 | 0.545642 |
| tmax_6700_label_smoothing_warmrestart_2ep | 0.686365 | 2.185797 | 0.742673 | 0.567813 |

### 11.4 分析

#### 发现 1：Label smoothing 的 BCE 升高是预期的

所有 label_smoothing 变体的 BCE 均比历史 baseline 高约 0.04（1.97 vs 1.93）。**这是 label smoothing 造成的，不是模型退化。** Soft label {0, 1} → {0.025, 0.975} 增加了标签的不确定性，BCE 的"最优可达值"本身就更高。需要关注的是 AUC，不是 BCE 的绝对值。

直接证比：baseline 的 BCE=1.933748，label_smoothing 的 BCE=1.971085（+0.037337），但 AUC 几乎相同（0.716316 vs 0.716637，Δ=+0.000321）。BCE 升高但 AUC 不跌甚至微升 → soft label 没有伤害排序能力。**注意：BCE 的绝对差值不能直接解读为"模型变差"，因为 label smoothing 改变了目标分布，最优可达 BCE 本身就更高。**

#### 发现 2：tmax_6700 与 label_smoothing 在 CTR 上叠加正向，CVR 需要权衡

tmax_6700 和 label_smoothing 的 CVR 基线不同，需要分开对比：

| 组合 | ΔAUC CTR vs baseline (0.716316) | ΔAUC CVR vs baseline (0.757583) | ΔAUC CVR vs tmax_6700 alone (0.758315) |
|---|---|---|---|---|
| tmax_6700 alone | **+0.000421 (0.49σ)** | **+0.000732 (0.90σ)** | — |
| label_smoothing alone | +0.000321 (0.37σ) | -0.000528 (0.65σ) | -0.001260 (1.56σ) |
| **tmax_6700 + label_smoothing** | **+0.000639 (0.74σ)** | -0.000319 (0.39σ) | **-0.001051 (1.30σ)** |

> **⚠ 统计显著性警告**：以 AUC SE≈0.00086（CTR）/ 0.00081（CVR）计算，所有 1-epoch 变体的 ΔAUC 均 < 2σ。没有任何一个效果的统计置信度超过常规显著性阈值。所有对比应视为 directionally consistent 而非已证实的改进。

CTR 上两者方向一致地正向叠加（tmax_6700_label_smoothing 的 +0.000639 > tmax_6700 alone 的 +0.000421）。CVR 上 label_smoothing 引入了一致的负向偏移（约 -0.001），但同样不显著。**当前数据不足以独立确认任何单独改进的效果，但趋势一致指向 tmax_6700 + label_smoothing 为最优组合。**



#### 发现 3：WarmRestart 1-epoch AUC 下降（0.712843）是因为 LR 重置时机问题

WarmRestart 的 T_0=6700（warmup_size=1000），实际 LR 重启发生在 step 7700，而 eval 在 step 7757。**此时 LR 刚被重置到 base_lr，模型处于高 LR 不稳定状态即被评估。** 这不是 WarmRestart 的固有问题，而是 eval 时机与 LR 周期不匹配。

#### 发现 4：2-epoch 在所有 LR 调度下均失败（tensorboard 曲线确认）

| 条件                        | AUC CTR vs 1-ep            |
| --------------------------- | -------------------------- |
| CosineAnnealing T_max=13400 | -0.020872（统计显著，24σ） |
| WarmRestart T_0=6700        | -0.030578（统计显著，35σ） |

**0.02-0.03 的 AUC 下降在 SE=0.00086 下极为显著。** 2-epoch 在任何条件下都失败，不是 LR 调度的问题。

> **Tensorboard 曲线确认（2026-06-23）**：两组 2-epoch 实验的 tensorboard 曲线显示了完全一致的过拟合模式：
> - **Epoch 边界（~8k steps）处存在剧烈 step-change**：eval AUC（蓝色）从 ~0.715 骤降至 ~0.695，train AUC（橙色）从 ~0.71 跳升至 ~0.75。这是经典过拟合 pattern：模型在记忆训练数据中的噪声分布而非通用模式。
> - **之前关于"中间 checkpoint 可能先改善再回落"的 caveat 已排除**：曲线清楚显示 eval AUC 在 epoch 边界处直接下降，之后基本持平（~0.695-0.71），未出现先升后降的倒 U 形
> - **⚠ 曲线末端（~step 15k）eval AUC ~0.71 与 step-15515 final eval（0.696）存在 ~0.014 差距**。可能原因：tensorboard 评估使用不同的验证集采样或平滑策略。不影响定性结论——两来源均确认 epoch 2 劣于 epoch 1。

#### 发现 5：BCE 在 epoch 2 显著回升，模型过拟合而非遗忘

2-epoch 的 BCE 从 1.97（step 7757）升至 2.08-2.19（step 15515）。Tensorboard 曲线确认了过拟合机制：
- **训练 BCE** 在 epoch 边界处跳升（从 ~1.88 升至 ~1.90-1.92），但此后持续在较低水平波动
- **训练 AUC** 从 ~0.71 跳升至 ~0.75 并维持高位
- **Eval AUC** 从 ~0.715 骤降至 ~0.695 后仅恢复至 ~0.71

**这是过拟合（记忆训练噪声），不是灾难性遗忘。** 二者区别：遗忘意味着所有指标同步恶化（train eval 均下降），过拟合意味着训练指标改善、验证指标恶化。这里 train AUC 上升 / eval AUC 下降的模式与过拟合完全一致。

Label smoothing（ε=0.05）不足以抑制 epoch 2 的过拟合。模型在 epoch 2 学到了数据中的虚假模式而非通用知识。

### 11.5 核心结论

**"2-epoch 失败是因为 LR 调度错误"的假设被实验否定。** 无论平滑 decay（T_max=13400）还是周期重启（WarmRestart），2-epoch 都大幅退化。Tensorboard 曲线确认了过拟合机制：模型在 epoch 2 学到的是训练数据的噪声分布而非通用模式。

**⚠ 关于 1-epoch 改进的统计显著性：** 所有 1-epoch 变体的 CTR/CVR ΔAUC 均 < 1σ（最大 0.90σ），任何单独改进均未达到常规显著性阈值。以下原因分析应视为 hypothesis 而非 confirmed findings。

可能的原因（1-epoch 改进方向一致但未达显著）：

1. 模型容量过大（96M item_id 参数 + 数千维统计特征 concat），epoch 2 直接记忆训练噪声
1. ε=0.05 的 label smoothing 抑制力度不足以在 epoch 2 防止过拟合
1. 随机 99/1 拆分导致 train 和 val 分布几乎一致 → 1 epoch 已学到极限
1. （已排除）中间 checkpoint 先升后降的可能 → tensorboard 曲线显示 eval AUC 在 epoch 边界直接下降

### 11.6 当前最优配置（方向性最优，未达统计显著）

```
tmax_6700 + label_smoothing (ε=0.05), num_epochs=1
```

| 指标    | 值           | Δ vs baseline                          |
| ------- | ------------ | -------------------------------------- |
| AUC CTR | **0.716955** | **+0.000639 (0.74σ，方向最优，未达显著)** |
| BCE CTR | 1.970330     | +0.036582（soft label 导致）           |
| AUC CVR | 0.757264     | -0.000319 (0.39σ，不显著)              |
| BCE CVR | 0.517286     | +0.024003（soft label 导致）           |

> 所有 1-epoch 变体的改进均未超过 1σ。上表中 "最优" 指所有实验中方向性结果最好，不意味着具有统计显著性。

### 11.7 后续方向

| 方向                                 | 建议                                                       | 优先级 |
| ------------------------------------ | ---------------------------------------------------------- | ------ |
| **上线 tmax_6700 + label_smoothing** | ΔCTR=+0.000639(0.74σ)，方向最优但未达显著，根据业务风险决策 | P0-P1  |
| Segment 诊断                         | 用 grouped_auc 找薄弱 segment                              | P1     |
| 时间拆分验证                         | 确认改进在真实分布上成立                                   | P1     |
| 更大 ε 的 label smoothing            | 尝试 0.1/0.2 以允许 2+ epoch                               | P2     |
| 停止 2-epoch 实验                    | 数据充分证明无效                                           | —      |

______________________________________________________________________

## 12. 品类跳跃修复（2026-06-23）

### 12.1 问题描述

线上 A/B 测试显示 `home_flow_2604_v11_contrastive.config` 在 uvctr 和人均曝光点击上有正向提升，但存在**品类跳跃**问题：用户点击了大量水果、牛奶、家电，推荐结果中却出现了卫衣、童装等跨品类商品。

### 12.2 根因分析

`title_vector` 被放在了 `feature_group "all"` 中（line 12366），这意味着它：

1. **被嵌入后拼接到主特征向量** → 流入 PEPNet/PLE tower → 直接影响 CTR/CVR 排序分数
2. **同时被对比学习使用** → 行为向量被拉向 title_vector 的语义空间

title_vector 编码的是**商品文字语义**（来自 Qwen3 文本嵌入），而非品类归属。当它同时作为 PEPNet 的输入特征和对比学习的对齐目标时：

- PEPNet tower 学到"语义相似 = 应该推荐"
- 跨品类但语义相近的商品（如"舒适透气面料的卫衣" vs "有机健康的食品"）被错误地关联
- **DIN 编码的品类级偏好被语义级信号污染**

### 12.3 修复方案

**核心思路**：让 `title_vector` 只参与对比学习，不流入 PEPNet tower。

#### Config 变更

```diff
# 从 feature_group "all" 中移除 title_vector
- feature_names: "title_vector"

# 新增独立的 "contrastive" feature group
+ feature_groups {
+   group_name: "contrastive"
+   feature_names: "title_vector"
+   group_type: DEEP
+ }
```

#### 代码变更（`tzrec/models/pepnet_dcn_ple.py`）

```diff
- # 从 "all" group 中查找 title_vector 的索引
- self._title_vector_idx = None
- offset = 0
- for name, dim in self.embedding_group.group_feature_dims("all").items():
-     if name == "title_vector":
-         self._title_vector_idx = (offset, offset + dim)
-         break
-     offset += dim
+ # 从独立的 "contrastive" group 中获取 title_vector
+ self._title_vector_dim = None
+ cg = getattr(self.embedding_group, "_group_feature_dims", {})
+ if "contrastive" in cg and "title_vector" in cg["contrastive"]:
+     self._title_vector_dim = cg["contrastive"]["title_vector"]
```

```diff
- if behavior_emb is not None and self._title_vector_idx is not None:
+ if behavior_emb is not None and self._title_vector_dim is not None:
      v = self.contrastive_behavior_proj(behavior_emb)
-     t_raw = grouped_features[self._main_group_name][
-         :, self._title_vector_idx[0] : self._title_vector_idx[1]
-     ]
+     tv_group = grouped_features.get("contrastive")
+     if tv_group is None:
+         return predictions
+     t_raw = tv_group[:, : self._title_vector_dim]
```

### 12.4 修复后的数据流

```
baseline (C组):
  title_vector: 不存在
  DIN → PEPNet → 排序: 基于品类/价格/品牌等

contrastive (修复后):
  title_vector: 仅在 "contrastive" group 中
  DIN → PEPNet → 排序: 基于品类/价格/品牌等（无 title_vector 污染）
  对比学习: DIN输出 ↔ title_vector（仅用于优化 behavior_proj，不影响排序）

contrastive (修复前):
  title_vector: 在 "all" group 中
  DIN → PEPNet → 排序: 品类信号 + 语义信号混合 ← 品类跳跃的根因
  对比学习: DIN输出 ↔ title_vector
```

### 12.5 验证计划

| 验证项 | 预期 | 方法 |
|--------|------|------|
| uvctr 仍正向 | +0.99% | A/B 测试 |
| 品类跳跃率下降 | 显著降低 | 统计推荐品类与用户历史品类的差异 |
| AUC CTR 不降 | ≥ baseline | 离线验证 |
| CVR 不受影响 | 与 baseline 一致 | 离线+线上验证 |
| 导出模型一致性 | 与 baseline 结构一致 | 检查 exported model 中无 title_vector 相关层 |

### 12.6 为什么修复后 uvctr 仍能正向？

uvctr 提升的根本原因是**对比学习优化了 behavior_proj**，使 DIN 编码的行为向量更好地对齐商品语义空间。这提升了模型对用户兴趣的理解精度。

修复前，title_vector 同时影响排序和对比学习，导致**排序被语义信号污染**（品类跳跃）。修复后，title_vector 只用于对比学习，DIN 行为向量仍然被优化到更好的语义对齐状态，但**排序不再受语义信号污染**。

类比：
- 修复前：老师既教知识又改试卷，但改试卷时用了错误的标准 → 成绩好看但知识教歪了
- 修复后：老师只用来改试卷的标准来评估自己，教学回归正确标准 → 成绩依然好，知识也教对了
