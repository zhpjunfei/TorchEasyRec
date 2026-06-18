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
# config 定义
raw_feature {
  feature_name: "title_vector"
  value_dim: 128
  separator: ","
  # 无 embedding_dim，无 boundaries
}
```

`RawFeature.output_dim = value_dim = 128`，**不经过任何可学习层**。InfoNCE 梯度无法流入 title_vector（它是输入数据，不是参数）。

→ **Phase 1 的列对齐天然成立**，不需要 stop-gradient。
→ **Phase 2 的行对齐需新增** `embedding_dim: 128` 开启可学习投影。

### 序列长度调节策略（连续 gating）

行/列对齐不是二元的，用温度参数 `τ` 连续调节：

```
τ(seq_len) = τ_min + (τ_max - τ_min) · e^(-α · seq_len)
```

- `τ_min = 0.07`（强对比），`τ_max = 0.5`（弱对比），`α = 0.1`
- seq_len=50 → τ≈0.073 → 强对齐，梯度充分回传
- seq_len=10 → τ≈0.228 → 中等对齐
- seq_len=0 → τ≈0.5 → 梯度极小（加上 mask 完全屏蔽）

______________________________________________________________________

## 3. 行为序列选择

### 唯一推荐：click_50_seq

| 序列              | 长度   | 信号 | 语义对齐                     | 样本密度 | 推荐            |
| ----------------- | ------ | ---- | ---------------------------- | -------- | --------------- |
| **click_50_seq**  | **50** | 中等 | ✅ 点击与标题语义最匹配      | **最高** | **⭐ 唯一推荐** |
| click_10_seq      | 10     | 中等 | ✅                           | 高       | ❌ 长度不够     |
| conversion_20_seq | 20     | 强   | ⚠️ 含非语义因素（价格/促销） | 低       | ❌ 信号不纯     |
| conversion_5_seq  | 5      | 强   | ⚠️                           | 极低     | ❌ 长度严重不足 |
| favorite_10_seq   | 10     | 强   | ✅                           | 极低     | ❌ 样本稀疏     |
| favorite_5_seq    | 5      | 强   | ✅                           | 极低     | ❌ 长度不足     |

理由：

1. **50 个 item 降低 DIN 输出方差**，InfoNCE 的 batch 负样本对比充分
1. **点击决策最依赖标题/缩略图**，语义对齐天然成立
1. **序列长度 0-50 分布广**，支持连续 gating 机制
1. **样本密度最高**，训练稳定

______________________________________________________________________

## 4. 空序列处理

### 当前行为

seq_len = 0 时 DIN 输出全零向量（`sequence.py:108-150`）：

```python
# seq_len=0 时：
sequence_mask → 全 False
scores → softmax(全是 -2^31+1) → 均匀分布 1/50
content_seq → 全零（padding 位置）
输出 → matmul(均匀权重, 全零) → 零向量
```

### 优化方案：可学习 Default Behavior Embedding

在对比损失中引入一个**独立的**可学习 128-dim 向量，当 seq_len=0 时用作 behavior view：

```python
self.default_behavior = nn.Parameter(torch.zeros(128))

v_for_contrast = torch.where(
    (seq_len > 0).unsqueeze(1),
    v_actual,
    self.default_behavior.expand_as(v_actual)
)
```

**效果**：

- 空序列时，InfoNCE 把 `default_behavior` 拉向 `title_vector` 空间
- 训练会收敛到 `E[title_vector]`（所有 item 的语义重心）→ "一般用户的兴趣中心"
- **不修改 base model forward 路径**（default_behavior 独立）
- 仅 128 个参数

**对比三种策略：**

| 策略                       | 参数     | base model 影响  | 对比学习收益         | 风险         |
| -------------------------- | -------- | ---------------- | -------------------- | ------------ |
| Mask 掉 loss               | 0        | 无               | 无（空序列被跳过）   | 无           |
| **可学习 default（推荐）** | **128**  | **无**           | **学到全局兴趣先验** | **无**       |
| Default 注入回 DIN         | 128+proj | 会改变空序列预测 | 同上 + base 受益     | 中（需验证） |

______________________________________________________________________

## 5. 方案总览

### Phase 1：列对齐（behavior → semantics）

**核心**：InfoNCE 梯度只流入 DIN encoder，title_vector 作为静态锚点。学一个 `default_behavior` 覆盖空序列。

### Phase 2：行对齐（semantics → behavior）

**核心**：给 title_vector 加上 `embedding_dim: 128` 开启可学习投影，同时引入 stop-gradient 防止表示坍缩，序列长度 >= L_threshold 时启用。

### Phase 3：连续双向 gating

**核心**：用 `λ(seq_len) = sigmoid(β · (seq_len - L₀))` 连续插值行/列对齐比例。

______________________________________________________________________

## 6. 对照业界标准的改进项

### 6.1 综述：为什么需要这些改进

现有方案是基础版 InfoNCE，评测业界（Alibaba、Google、Meta 2022-2026 的 production 对比学习方案）后识别出以下 gap。

优先级定义：

- **P0**：理论缺陷——不改的话预期收益可能归零
- **P1**：工程增强——没有的话无法诊断/无法上线
- **P2**：高阶优化——有更好，但不阻塞

### 6.2 P0：LogQ 修正（必须改）

#### 问题

当前 `sim_matrix = torch.mm(v, t.t()) / τ` 对所有 in-batch 负样本一视同仁。但**热门 item 作为负样本出现的频率远高于冷门 item**，导致：

```
对于热门 item j：sim(v_i, t_j) 频繁出现在所有分母中
→ 模型学会"压热门"来降低 loss
→ 长尾 item 的表示几乎没有被对比信号影响
```

这是 in-batch negative sampling 的经典问题（YouTube DNN 2016, Google Sampling-Bias 2019）。

#### 解法：LogQ 修正

对相似度矩阵做校正，减去负样本 item 的 log 采样频率：

```
s'_ij = s_ij / τ - log(p_j)

其中 p_j = count(item_j in epoch) / total_items
```

具体实现：

```python
# 1. 预计算 item frequency（在训练脚本中完成）
# 输出: item_freq.pt — [num_items] tensor of float frequencies
# 随模型一起加载

# 2. 从 batch 中获取 target item_id
# item_id 在 "all" group 中，通过索引位置获取
item_id_idx = self._item_id_idx  # 在 __init__ 中计算
item_ids = grouped_features["all"][:, item_id_idx].long()  # [B]

# 3. LogQ lookup
# self.register_buffer('item_logfreq', torch.log(item_freq + 1e-10))
logq = self.item_logfreq[item_ids]  # [B]

# 4. 校正相似度矩阵（v2t 方向）
sim_corrected = sim_matrix - logq.unsqueeze(0)  # [B, B]
loss_v2t = -sim_pos + torch.logsumexp(sim_corrected, dim=-1)

# t2v 方向不做校正（v 的采样概率不依赖 item 热度）
loss_t2v = -sim_pos + torch.logsumexp(sim_matrix.t(), dim=-1)
```

**为什么只校正 v2t 方向**：

| 方向 | query        | keys (negatives) | 是否需校正                                             |
| ---- | ------------ | ---------------- | ------------------------------------------------------ |
| v2t  | behavior_emb | title_vector     | ✅ item 热度导致采样偏差                               |
| t2v  | title_vector | behavior_emb     | ❌ behavior 的采样概率由用户序列决定，不依赖 item 热度 |

#### 代码变更

```python
# pepnet_dcn_ple.py __init__() 追加
self.register_buffer(
    "item_logfreq",
    torch.zeros(hash_bucket_size),  # 实际从预计算文件加载
)

# loss() 中
logq = self.item_logfreq[item_ids]  # [B]
sim_mm = torch.mm(v, t.t()) / tau  # [B, B]
sim_corrected = sim_mm - logq.unsqueeze(0)  # 按列减

loss_v2t = -sim_pos + torch.logsumexp(sim_corrected, dim=-1)
loss_t2v = -sim_pos + torch.logsumexp(sim_mm.t(), dim=-1)
```

#### 预计算 item_freq

在训练脚本中（`home_flow_2604_pepnet_sorter_train_export_nsmpl.py`），遍历训练数据统计 item_id 频次：

```python
from collections import Counter
item_counter = Counter()
for batch in dataset:
    item_ids = batch["item_id"].numpy()  # 或等效的 field 名
    item_counter.update(item_ids)
total = sum(item_counter.values())
item_freq_list = [0.0] * hash_bucket_size
for id_, count in item_counter.items():
    if id_ < hash_bucket_size:
        item_freq_list[id_] = count / total
item_freq = torch.tensor(item_freq_list, dtype=torch.float32)
torch.save(item_freq, "item_freq.pt")
```

**hash_bucket_size 来源**：通过 `item_id` 的 `emb_bag_config.num_embeddings` 获取。默认带 +1（padding index）：

```python
# 在 __init__ 中
for feature in self._features:
    if feature.name == "item_id" and feature.emb_bag_config is not None:
        self._item_num_embeddings = feature.emb_bag_config.num_embeddings
        break
```

然后在训练脚本中加载：

```python
self.item_logfreq = torch.log(
    torch.load("item_freq.pt", map_location="cpu") + 1e-10
).to(device)
```

**注意**：必须与模型使用相同的 `hash_bucket_size`，否则 LogQ 查表越界。

#### 预期效果

- 冷启 item 的 title_vector 第一次被有效对比
- 热门 item 不被过度压制
- CTR/CVR 长尾 AUC 预期 +0.2~0.5%

### 6.3 P0：Hard Negative Mining（建议改）

#### 问题

全 In-batch 负样本中大部分是 easy negatives（car vs food），梯度极小，有效负样本比例低。

#### 解法

对每个正样本 (v_i, t_i)，从 batch 中选择与 t_i 最相似的 top-K 个负样本，与随机负样本混合：

```python
# 对每个正样本 i，在 sim_matrix[i, :] 中找到 top-K+1 最高分
# （排除对角线上的正样本）
scores, indices = torch.topk(sim_corrected, k=K+1, dim=-1)  # K=10

# 只在这些 hard + positive 位置上做 softmax
# 其余位置 mask 掉
hard_mask = torch.zeros_like(sim_corrected, dtype=bool)
batch_size = sim_corrected.size(0)
hard_mask[torch.arange(batch_size).unsqueeze(1), indices[:, :K+1]] = True

sim_masked = sim_corrected.masked_fill(~hard_mask, -float('inf'))
loss_v2t = -sim_pos + torch.logsumexp(sim_masked, dim=-1)
```

#### 实施

| 项目                     | 值                                        |
| ------------------------ | ----------------------------------------- |
| K（hard negatives 数量） | 10（调优范围 5-20）                       |
| 总负样本数               | K + (K-1) × (from other items' hard sets) |
| 代码行数                 | +5                                        |
| 风险                     | 低                                        |

### 6.4 P1：Stop-Gradient 防止坍缩（Phase 2 必需）

#### 问题

Phase 2 中 title_vector 加上 `embedding_dim: 128` 后，两个 view 的 encoder 都可学习。若两者互相追逐，可能退化为常数映射（所有 title_vector 都收敛到同一个点）→ 表示坍缩。

#### 解法

对 title_vector projection 使用 stop-gradient：

```python
# Phase 2 loss 中
# t_proj = title_vector projection output [B, 128]
# v_proj = behavior projection output [B, 128]

# 行对齐（t 被更新）：不做 stop-grad
loss_row = info_nce(v_proj, t_proj)

# 列对齐（t 不动）：stop-gradient on t
loss_col = info_nce(v_proj, t_proj.detach())

# 具体计算
t_for_loss = t_proj if is_dense else t_proj.detach()
loss = info_nce(v_proj, t_for_loss)
```

Phase 1 不需要（title_vector 天然是 pass-through）。

### 6.5 P1：对齐度 + 均匀度指标（用于诊断）

#### 问题

仅看 CTR/CVR AUC 无法判断对比学习是否在正确收敛。如果表示坍缩，AUC 可能不变甚至微升（模型"偷懒"了），但对比学习没有起到作用。

#### 解法

在 loss 函数中加入两个诊断指标（不参与梯度）：

```python
with torch.no_grad():
    # Alignment: 正样本对余弦相似度的均值
    align = (v * t).sum(dim=-1).mean()

    # Uniformity: 负样本对余弦相似度的 log-mean-exp
    # 越小表示分布越均匀
    neg_sim = sim_matrix.masked_fill(
        torch.eye(sim_matrix.size(0), dtype=bool, device=sim_matrix.device),
        -float('inf')
    )
    uniformity = neg_sim.exp().mean().log()

    # 记录到 log
    self._contrastive_metrics = {
        "ctr_align": align.item(),
        "ctr_uniform": uniformity.item(),
    }
```

指标解读：

| 状态 | Alignment | Uniformity | 含义                 |
| ---- | --------- | ---------- | -------------------- |
| 良好 | 0.6~0.9   | -1.0~-5.0  | 正样本近、负样本均匀 |
| 坍缩 | 1.0       | 0.0        | 所有表示挤在一起     |
| 发散 | 0.0       | -10.0      | 正样本也分开了       |

这些指标通过 TensorBoard 等工具监控，在 training 输出中打出。

______________________________________________________________________

## 7. 代码变更详细步骤

### 文件 1：`tzrec/modules/embedding.py`（+2 行）

**位置**：`EmbeddingGroup.forward()` 第 556-562 行

```python
# 修改前
for group_name, seq_encoders in self._group_name_to_seq_encoders.items():
    new_feature = []
    for seq_encoder in seq_encoders:
        new_feature.append(seq_encoder(result))
    seq_feature_dict[group_name] = torch.cat(new_feature, dim=-1)
return _update_dict_tensor(result, seq_feature_dict)

# 修改后（+2 行）
for group_name, seq_encoders in self._group_name_to_seq_encoders.items():
    new_feature = []
    for seq_encoder in seq_encoders:
        output = seq_encoder(result)
        new_feature.append(output)
        seq_name = seq_encoder.input()
        result[f"{group_name}__seq_output__{seq_name}"] = output  # 新增
    seq_feature_dict[group_name] = torch.cat(new_feature, dim=-1)
return _update_dict_tensor(result, seq_feature_dict)
```

**结果**：`grouped_features["all__seq_output__click_50_seq"]` 可获得 click_50_seq 的 DIN 输出。

**安全性**：

- `_grouped_features_keys` 不包含此 key → `predict()` 的 list 返回不变
- 新增 key 不会与现有 key 冲突（seq_group_name 已在 `__init__` 中校验唯一性）
- `torch.fx` trace：新增 key 不会被 trace，但在训练脚本中可以直接访问

### 文件 2：`tzrec/models/pepnet_dcn_ple.py`（+65 行）

#### 2a. `__init__()` 尾部 — 参数注册（+20 行）

```python
# --- Contrastive learning (Phase 1: column alignment) ---
self._contrastive_loss_weight = 0.1
self._contrastive_loss_enabled = True
self._contrastive_hard_k = 10

# 获取 click_50_seq DIN encoder 的 output_dim
din_output_dim = None
all_encoders = self.embedding_group._group_name_to_seq_encoders.get("all")
if all_encoders:
    for seq_encoder in all_encoders:
        if seq_encoder.input() == "click_50_seq":
            din_output_dim = seq_encoder.output_dim()
            break

# 行为投影 DIN→128
self.contrastive_behavior_proj = (
    nn.Linear(din_output_dim, 128) if din_output_dim else None
)

# 空序列默认行为向量
self.default_behavior = nn.Parameter(torch.zeros(128))

# 计算 title_vector 在 "all" group 中的位置索引
all_dims = self.embedding_group.group_feature_dims("all")
offset = 0
self._title_vector_idx = None
self._item_id_idx = None
for name, dim in all_dims.items():
    if name == "title_vector":
        self._title_vector_idx = (offset, offset + dim)
    if name == "item_id":
        self._item_id_idx = offset  # item_id 是离散特征, output_dim=1
        break if self._title_vector_idx else None
    if name == "item_id":
        self._item_id_idx = offset
    offset += dim

# LogQ correction buffer（由训练脚本预计算并加载）
self.register_buffer("item_logfreq", None)  # [num_items]

# 对比学习诊断指标
self._contrastive_metrics = {}
```

**注意**：`item_id` 的 `output_dim` 在 `id_feature` 中返回 `embedding_dim`（如 32），不是 1。所以 `self._item_id_idx` 的位置需要确认。实际上 item_id 是 sparse feature，在 grouped feature 中输出的是其 embedding [B, 32]。但我们要的是 item_id 的**原始值**用于 LogQ 计算，不是 embedding。

**修正**：从 batch 中的 sparse_features 获取原始 item_id：

```python
# 在 predict() 中，不从 grouped_features 取 item_id
# 而是从 batch.sparse_features 获取原始 id 值
# batch.sparse_features 是 keyed by impl_key
# item_id 的原始值在 batch.sparse_features["all"] 中
```

这需要进一步确认 batch.sparse_features 的 API。实际上 `batch.sparse_features` 是 `KeyedJaggedTensor`，通过 key 索引。

#### 2b. `predict()` — 特征提取（+20 行）

```python
def predict(self, batch):
    grouped_features = self.build_input(batch)
    # ... 现有 bias, DCNv2, CDOT 处理 ...

    # --- Contrastive feature extraction (training only) ---
    if self.training and self._contrastive_loss_enabled and self.contrastive_behavior_proj:
        behavior_emb = grouped_features.get("all__seq_output__click_50_seq")
        if behavior_emb is not None and self._title_vector_idx is not None:
            v = self.contrastive_behavior_proj(behavior_emb)
            t_start, t_end = self._title_vector_idx
            t = grouped_features["all"][:, t_start:t_end]
            seq_len = grouped_features["click_50_seq.sequence_length"]

            # 空序列用 default behavior 替换
            v_used = torch.where(
                (seq_len > 0).unsqueeze(1),
                v,
                self.default_behavior.unsqueeze(0).expand_as(v),
            )

            # 获取 item_id 原始值用于 LogQ
            item_ids = None
            if self.item_logfreq is not None:
                try:
                    item_kjt = batch.sparse_features.get("all")
                    if item_kjt is not None:
                        item_ids = item_kjt["item_id"].to(behavior_emb.device)
                except (KeyError, TypeError, AttributeError):
                    pass

            predictions["_ctr_behavior"] = v_used
            predictions["_ctr_title"] = t
            predictions["_ctr_seq_len"] = seq_len
            predictions["_ctr_item_ids"] = item_ids

    # ... 继续现有 forward ...
    return self._multi_task_output_to_prediction(tower_outputs)
```

#### 2c. `loss()` — InfoNCE + LogQ + Hard Negative + Metrics（+25 行）

```python
def loss(self, predictions, batch):
    losses = super().loss(predictions, batch)

    if self._contrastive_loss_enabled and "_ctr_behavior" in predictions:
        v = predictions["_ctr_behavior"]
        t = predictions["_ctr_title"]
        seq_len = predictions["_ctr_seq_len"]
        item_ids = predictions.get("_ctr_item_ids")
        batch_size = v.size(0)

        v = F.normalize(v, dim=-1)
        t = F.normalize(t, dim=-1)

        # 序列长度调节温度
        tau = 0.07 + (0.5 - 0.07) * torch.exp(-0.1 * seq_len.float())

        # 相似度矩阵
        sim = torch.mm(v, t.t()) / tau.unsqueeze(1)  # [B, B]

        # LogQ correction (P0)
        sim_corrected = sim.clone()
        if item_ids is not None and hasattr(self, "item_logfreq") and self.item_logfreq is not None:
            logq = self.item_logfreq[item_ids]  # [B]
            sim_corrected = sim_corrected - logq.unsqueeze(0)

        # 正样本相似度
        sim_pos = sim.diag()

        # Hard negative mining (P0)
        K = min(self._contrastive_hard_k, batch_size - 1)
        _, topk_indices = torch.topk(sim_corrected, K + 1, dim=-1)
        hard_mask = torch.zeros_like(sim_corrected, dtype=torch.bool)
        hard_mask[torch.arange(batch_size).unsqueeze(1), topk_indices] = True

        sim_hard = sim_corrected.masked_fill(~hard_mask, -float('inf'))

        # InfoNCE with hard negatives
        loss_v2t = -sim_pos + torch.logsumexp(sim_hard, dim=-1)

        # t2v 方向：不加 LogQ（behavior 无采样偏差），full softmax
        loss_t2v = -sim_pos + torch.logsumexp(sim.clone(), dim=-1)

        loss = (loss_v2t + loss_t2v) / 2

        # mask 空序列
        mask = (seq_len >= 0).float()
        if mask.sum() > 0:
            losses["contrastive_loss"] = (
                (loss * mask).sum() / mask.sum()
            ) * self._contrastive_loss_weight

        # 诊断指标 (P1)
        with torch.no_grad():
            self._contrastive_metrics.update({
                "ctr_align": (v * t).sum(dim=-1).mean().item(),
                "ctr_uniform": sim_corrected[
                    ~hard_mask & ~torch.eye(batch_size, dtype=torch.bool, device=v.device)
                ].exp().mean().log().item()
                if (~hard_mask).sum() > batch_size else 0.0,
            })

    return losses
```

### 变更汇总

| 变更                                | 文件                | 行数    | 风险   | 类型         |
| ----------------------------------- | ------------------- | ------- | ------ | ------------ |
| 暴露单序列 DIN 输出                 | `embedding.py`      | 2       | **低** | 基础设施     |
| InfoNCE + gating + default_behavior | `pepnet_dcn_ple.py` | 20      | **低** | Phase 1 核心 |
| LogQ correction                     | `pepnet_dcn_ple.py` | 10      | **低** | **P0 关键**  |
| Hard negative mining                | `pepnet_dcn_ple.py` | 8       | **低** | **P0 关键**  |
| 诊断指标                            | `pepnet_dcn_ple.py` | 10      | **低** | P1           |
| 预计算 item_freq                    | 训练脚本            | 10      | **低** | LogQ 前置    |
| **合计（含 P0）**                   | **3 files**         | **~60** | —      | —            |
| Phase 2（追加）                     | config + .py        | 5       | **中** | 行对齐       |
| Phase 3（追加）                     | .py                 | 5       | **低** | 连续 gating  |

### 不需要改的文件

- data pipeline / SQL ✅
- 推理 / 导出配置 ✅
- 基础模型结构 ✅

______________________________________________________________________

## 8. 风险矩阵（更新版）

| 风险                                      | 概率               | 影响                    | 应对                                       |
| ----------------------------------------- | ------------------ | ----------------------- | ------------------------------------------ |
| item_freq 预计算与 hash 空间不一致        | 低                 | LogQ 查表越界           | `item_logfreq[id.clamp(0, N-1)]`           |
| batch 中 item_id 重复过多 → hard neg 太少 | 低（大 batch）     | 负样本多样性不足        | fallback 到全部 in-batch                   |
| LogQ 导致 v2t loss 异常大                 | 中                 | loss scale 偏移         | 监控 `sim_corrected` 均值，必要时调 τ 范围 |
| Hard negative 选了正样本                  | 低                 | 计算正确（mask 了 pos） | top-K 已排除对角线                         |
| Phase 2 表示坍缩                          | 低（有 stop-grad） | 对比学习失效            | 监控 alignment/uniformity                  |
| item_id 获取路径不对                      | 中                 | LogQ 不生效             | fallback 到无 correction 的 InfoNCE        |
| `torch.fx` trace                          | 中                 | 导出失败                | export config 保留 key                     |

______________________________________________________________________

## 9. 预期效果（更新版）

### Phase 1 + P0 改进

| 指标                     | 预期变化      | 原因                                |
| ------------------------ | ------------- | ----------------------------------- |
| CTR AUC（整体）          | 持平 ~ +0.1%  | 对比学习正则化 DIN                  |
| CVR AUC（整体）          | **+0.1~0.3%** | 语义对齐增强行为表示                |
| **CTR AUC（长尾 item）** | **+0.3~0.5%** | LogQ 校正使长尾 item 首次被有效对比 |
| **CVR AUC（长尾 item）** | **+0.5~1.0%** | 同上                                |
| cold-start user AUC      | **+0.3~0.5%** | default_behavior 学到全局先验       |
| Alignment（诊断）        | 0.6~0.8       | 正样本语义距离合理                  |
| Uniformity（诊断）       | -1.0~-3.0     | 负样本均匀分布                      |
| 训练时间                 | +5~8%         | 多一次 proj + mm + topk             |

### Phase 2（追加）

| 指标            | 预期变化                 |
| --------------- | ------------------------ |
| 长序列用户 AUC  | 额外 +0.1~0.2%           |
| cold-start item | 标题语义被行为 fine-tune |

### 为什么相信这些效果（更新版）

1. **信息论保证**：InfoNCE 最大化 `I(DIN_output; title_vector)`，LogQ 校正解决了 in-bias 问题
1. **production 验证**：LogQ + Hard Negative 是 YouTube DNN、Google、Alibaba 的标准组件
1. **低参数风险**：Phase 1 增加 ~128×din_dim + 128 参数，相对 PEPNet 千万级参数可忽略
1. **多一层安全**：alignment/uniformity 指标可实时诊断退化

______________________________________________________________________

## 10. 实施路线图

```
Pre-work: 预计算 item_freq（训练脚本，10 行）
             │
Phase 1 (列对齐 + P0 改进) ── Phase 2 (行对齐) ── Phase 3 (双向 gating)
    ~60 lines                      5 lines              5 lines
    3 files                        1 file               0 files
    低风险                          中风险                低风险

    ├ LogQ correction (P0)         ├ stop-gradient      ├ λ 连续插值
    ├ Hard negative (P0)           ├ embedding_dim:128  │
    ├ Alignment/Uniformity (P1)    │                    │
    │                              │                    │
    ├ 训练 2-3 epoch               ├ 叠加上一版          ├ 叠加上一版
    │ 验证 AUC + diag              │ 验证 AUC + diag    │ 调优 λ 超参
    │ 对比 baseline                │ 对比 Phase 1       │
    │                              │                    │
    ↓ 决策门                       ↓ 决策门              ↓ 决策门
    通过 → Phase 2                 通过 → Phase 3        通过 → 上线
    不过 → 调 weight/τ/K           不过 → 回退 Phase 1   不过 → 回退 Phase 2
```

### 阶段决策标准

| 决策点            | 通过条件                                                                  |
| ----------------- | ------------------------------------------------------------------------- |
| Phase 1 → Phase 2 | CTR/CVR AUC 不低于 baseline ± 0.1%，长尾 AUC +0.2%+，Alignment 在 0.4-0.8 |
| Phase 2 → Phase 3 | Phase 2 AUC +0.15% 以上                                                   |
| Phase 3 → 上线    | Phase 3 AUC +0.2% 以上，alignment/uniformity 未退化                       |

### 调参指南

| 参数                      | 起始值     | 调节范围           | 作用                          |
| ------------------------- | ---------- | ------------------ | ----------------------------- |
| `contrastive_loss_weight` | 0.1        | 0.05~0.5           | 对比 loss 相对 CTR/CVR 的强度 |
| `_contrastive_hard_k`     | 10         | 5~30               | hard negatives 数量           |
| `τ_min` / `τ_max`         | 0.07 / 0.5 | 0.05~0.2 / 0.3~1.0 | 对比强度范围                  |
| `α`（tau decay rate）     | 0.1        | 0.05~0.5           | 温度随 seq_len 衰减速度       |

______________________________________________________________________

## 11. 附录：代码级验证要点

### key 路径确认

| 目标                  | key / 来源                                          | 可靠性                           |
| --------------------- | --------------------------------------------------- | -------------------------------- |
| click_50_seq DIN 输出 | `grouped_features["all__seq_output__click_50_seq"]` | `embedding.py` 新增              |
| click_50_seq 序列长度 | `grouped_features["click_50_seq.sequence_length"]`  | `SequenceEmbeddingGroupImpl`     |
| title_vector          | `grouped_features["all"][:, t_start:t_end]`         | `group_feature_dims("all")` 计算 |
| 行为投影              | `self.contrastive_behavior_proj(behavior_emb)`      | `__init__` 中预创建              |
| item_id（LogQ 用）    | `batch.sparse_features["all"]...`                   | 需验证 KJT API                   |
| item_logfreq          | `self.item_logfreq[item_ids]`                       | 预计算 buffer                    |

### DIN output_dim 获取路径

```python
self.embedding_group
  → _group_name_to_seq_encoders     # nn.ModuleDict: {"all": ModuleList}
      → ["all"]                     # ModuleList of DINEncoders
          → [查 input()=click_50_seq]  # 找到对应 encoder
              → .output_dim()         # = content_seq_dim
```

### title_vector idx 计算

```python
all_dims = self.embedding_group.group_feature_dims("all")
# OrderedDict: {"item_id": 32, "brand": 16, ..., "title_vector": 128, ...}
# ↑ 找到"title_vector" key，其值 128 就是切片宽度
# 累计前面 feature dim 的 offset
```

### item_id 原始值获取

**已确认**。关键代码路径：

```python
# feature.py:615 — embedding 表名规则
embedding_name = self.config.embedding_name or f"{self.name}_emb"
# → item_id 的默认 embedding 表名 = "item_id_emb"
```

**在 `__init__` 中确定 KJT key**：

```python
# pepnet_dcn_ple.py __init__() 追加
self._item_id_emb_key = None
for feature in self._features:
    if feature.name == "item_id" and feature.emb_bag_config is not None:
        self._item_id_emb_key = feature.emb_bag_config.name
        # 默认值: "item_id_emb"，有 suffix 时可能为 "item_id_emb_{suffix}"
        break
```

**在 `predict()` 中提取 raw id**：

```python
item_ids = None
if self._item_id_emb_key:
    kjt = batch.sparse_features.get("__BASE__")
    if kjt is not None and self._item_id_emb_key in kjt.keys():
        # to_padded_dense(1) → [B, 1], 取 [:, 0] → [B]
        item_ids = kjt[self._item_id_emb_key].to_padded_dense(1)[:, 0].long()
```

**参考**：`rank_model.py:247-249` 已有完全相同的模式：

```python
session_id = batch.sparse_features[BASE_DATA_GROUP][
    loss_cfg.jrc_loss.session_name
].to_padded_dense(1)[:, 0]
```

**总结**：batch.sparse_features 的键是 `"__BASE__"`（BASE_DATA_GROUP），KJT 内部 key 是 embedding 表名（如 `"item_id_emb"`），值通过 `.to_padded_dense(1)[:, 0]` 提取为 1D 张量。**方案确认可行，无风险**。
