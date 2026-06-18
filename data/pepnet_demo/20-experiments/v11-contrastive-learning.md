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

### 序列长度调节策略（连续 gating）

```
τ(seq_len) = τ_min + (τ_max - τ_min) · e^(-α · seq_len)
```

- `τ_min = 0.07`，`τ_max = 0.5`，`α = 0.1`
- seq_len=50 → τ≈0.073（强对齐），seq_len=10 → τ≈0.228（中等），seq_len=0 → τ≈0.5（弱）

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

### P0：LogQ 修正

**问题**：In-batch negatives 中热门 item 出现频率过高，模型学会"压热门"而非学语义差异。

**解法**：

```python
# v2t 方向校正：s'_ij = s_ij / τ - log(p_j)
# p_j = freq(item_j) in training data
logq = self.item_logfreq[item_ids]  # [B]
sim_corrected = sim_matrix - logq.unsqueeze(0)

loss_v2t = -sim_pos + torch.logsumexp(sim_corrected, dim=-1)
# t2v 方向不做校正（behavior 采样不依赖 item 热度）
loss_t2v = -sim_pos + torch.logsumexp(sim_matrix.t(), dim=-1)
```

**预计算**：训练脚本遍历数据统计 `item_id` 频次，存为 `item_freq.pt`（shape=[hash_bucket_size]）。

### P0：Hard Negative Mining

```python
K = min(self._contrastive_hard_k, batch_size - 1)
_, topk_indices = torch.topk(sim_corrected, K + 1, dim=-1)
hard_mask[arange(batch_size), topk_indices] = True
sim_hard = sim_corrected.masked_fill(~hard_mask, -inf)
loss_v2t = -sim_pos + torch.logsumexp(sim_hard, dim=-1)
```

| 参数                  | 起始值 | 范围 |
| --------------------- | ------ | ---- |
| `_contrastive_hard_k` | 10     | 5-30 |

### P1：Stop-Gradient（Phase 2 必需）

Phase 2 中 title_vector projection 可学习后，用 `t_proj.detach()` 防止列对齐时坍缩。

### P1：对齐度 + 均匀度诊断

```python
with torch.no_grad():
    align = (v * t).sum(dim=-1).mean()
    uniformity = neg_sim.exp().mean().log()
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
self._contrastive_hard_k = 10

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

# item_id embedding 名（用于 LogQ）
self._item_id_emb_key = None
for f in self._features:
    if f.name == "item_id" and f.emb_bag_config:
        self._item_id_emb_key = f.emb_bag_config.name
        break

self.register_buffer("item_logfreq", None)
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

        item_ids = None
        if self._item_id_emb_key:
            kjt = batch.sparse_features.get("__BASE__")
            if kjt is not None and self._item_id_emb_key in kjt.keys():
                item_ids = kjt[self._item_id_emb_key].to_padded_dense(1)[:, 0].long()

        predictions["_ctr_behavior"] = v
        predictions["_ctr_title"] = t
        predictions["_ctr_seq_len"] = seq_len
        predictions["_ctr_item_ids"] = item_ids
```

#### 2c. `loss()`（+25 行）

```python
def loss(self, predictions, batch):
    losses = super().loss(predictions, batch)

    if self._contrastive_loss_enabled and "_ctr_behavior" in predictions:
        v, t, seq_len = predictions["_ctr_behavior"], predictions["_ctr_title"], predictions["_ctr_seq_len"]
        item_ids = predictions.get("_ctr_item_ids")
        B = v.size(0)

        v, t = F.normalize(v, dim=-1), F.normalize(t, dim=-1)
        tau = 0.07 + 0.43 * torch.exp(-0.1 * seq_len.float())

        sim = torch.mm(v, t.t()) / tau.unsqueeze(1)

        # LogQ
        sim_c = sim.clone()
        if item_ids is not None and self.item_logfreq is not None:
            logq = self.item_logfreq[item_ids].to(sim.device)
            sim_c = sim_c - logq.unsqueeze(0)

        sim_pos = sim.diag()

        # Hard negative
        K = min(self._contrastive_hard_k, B - 1)
        _, topk = torch.topk(sim_c, K + 1, dim=-1)
        hard_mask = torch.zeros_like(sim_c, dtype=torch.bool)
        hard_mask[torch.arange(B).unsqueeze(1), topk] = True

        loss_v2t = -sim_pos + torch.logsumexp(sim_c.masked_fill(~hard_mask, -float('inf')), dim=-1)
        loss_t2v = -sim_pos + torch.logsumexp(sim, dim=-1)
        loss = (loss_v2t + loss_t2v) / 2

        mask = (seq_len >= 0).float()
        if mask.sum() > 0:
            losses["contrastive_loss"] = (loss * mask).sum() / mask.sum() * self._contrastive_loss_weight

        with torch.no_grad():
            self._contrastive_metrics.update({
                "ctr_align": (v * t).sum(-1).mean().item(),
                "ctr_uniform": sim_c[
                    ~hard_mask & ~torch.eye(B, dtype=torch.bool, device=v.device)
                ].exp().mean().log().item() if (~hard_mask).sum() > B else 0.0,
            })

    return losses
```

### 变更汇总

| 变更                                | 文件                | 行      | 风险   |
| ----------------------------------- | ------------------- | ------- | ------ |
| 暴露单序列 DIN 输出                 | `embedding.py`      | 2       | **低** |
| InfoNCE + gating + default_behavior | `pepnet_dcn_ple.py` | 20      | **低** |
| LogQ correction                     | `pepnet_dcn_ple.py` | 10      | **低** |
| Hard negative mining                | `pepnet_dcn_ple.py` | 8       | **低** |
| 诊断指标                            | `pepnet_dcn_ple.py` | 10      | **低** |
| 预计算 item_freq                    | 训练脚本            | 10      | **低** |
| **合计**                            | **3 files**         | **~60** | -      |
| Phase 1b: chaprice 辅助 view        | `.py`               | +5      | **低** |
| Phase 2: 行对齐                     | config + .py        | +5      | **中** |
| Phase 3: 连续 gating                | .py                 | +5      | **低** |

### 不需要改

- data pipeline / SQL ✅
- 推理 / 导出配置 ✅
- 基础模型结构 ✅

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

| 风险                                 | 概率     | 影响                    | 应对                                 | 残余风险 |
| ------------------------------------ | -------- | ----------------------- | ------------------------------------ | -------- |
| LogQ item_freq 与 hash 空间不一致    | **低**   | 查表越界                | `item_ids.clamp(0, N-1)`             | **极低** |
| batch 中 item 高度重复 → hard neg 少 | **低**   | 退化到全量 softmax      | fallback: 无 hard neg 时用 full      | **低**   |
| 温度 τ 对短序列压制过度              | **中**   | 对比学习在短序上 ≈ 无效 | 调 α / τ_min；短序本来信号弱，可接受 | **低**   |
| Phase 2 表示坍缩                     | **低**   | 对比失效                | stop-gradient（已设计）+ 诊断监控    | **低**   |
| `torch.fx` trace 新增 key            | **中**   | 导出失败                | export config 显式保留 key           | **中**   |
| chaprice + title_vector 粒度不匹配   | **确定** | 预期增益有限            | 权重设为 0.3，不阻塞主 view          | **低**   |
| DIN output_dim 变化                  | **极低** | 投影层维度不匹配        | `__init__` 预获取，建完不可变        | **无**   |

### 8.3 详细 Roadmap

#### 前置条件

- [ ] 训练环境确认：PEPNet 训练管道 1.2.16+，`tzrec.models.pepnet_dcn_ple` 可单机 debug
- [ ] config 确认：确认远端部署路径 `/mnt/data/deploy/home_flow_2604_ctrcvr_sorter_v1/` 有对应 v11 config

#### Step 1：预计算 item_freq

| 文件                                             | 改动               | 预期耗时       |
| ------------------------------------------------ | ------------------ | -------------- |
| 训练脚本 `*_pepnet_sorter_train_export_nsmpl.py` | +10 行数据遍历统计 | 1-2h（单次跑） |

需输出：`item_freq.pt`（tensor, shape=[hash_bucket_size]）

检查点：`torch.load("item_freq.pt").sum()` ≈ 1.0 ✅

#### Step 2：修改 embedding.py

| 文件                         | 改动                                       | 行数 | 风险 |
| ---------------------------- | ------------------------------------------ | ---- | ---- |
| `tzrec/modules/embedding.py` | `forward()` 中加 2 行，暴露单序列 DIN 输出 | +2   | 低   |

验证：`grouped_features["all__seq_output__click_50_seq"]` 返回 `[B, din_dim]` tensor

#### Step 3：修改 pepnet_dcn_ple.py

| 子步骤                | 方法                             | 行数 |
| --------------------- | -------------------------------- | ---- |
| 3a. `__init__()` 尾部 | 注册 parameters + 计算索引       | +20  |
| 3b. `predict()`       | 提取特征 + LogQ                  | +20  |
| 3c. `loss()`          | InfoNCE + HardNegative + Metrics | +25  |

验证：单步 forward + backward 不报错，loss 输出含 `"contrastive_loss"`

#### Step 4：训练 Phase 1a（click_50_seq 主 view）

| 实验          | 配置                                   | 预期                           |
| ------------- | -------------------------------------- | ------------------------------ |
| Phase 1a      | baseline config + 改后的 pepnet        | train loss 含 contrastive_loss |
|               | contrastive_loss_weight=0.1, hard_k=10 | alignment ≈ 0.2~0.8 之间波动   |
|               |                                        | uniformity ≈ -1~-5 之间        |
| baseline 对比 | 原始 v11_title_vector config           | 纯 CTR/CVR loss                |

训练 2-3 epoch 后观察：

- [ ] CTR AUC 不低于 baseline ± 0.1%
- [ ] 长尾 item AUC +0.2%+
- [ ] Alignment 在 0.4-0.8（不坍缩）
- [ ] Uniformity < -1.0（不发散）

#### Step 5：决策门

| 结果                   | 下一步                                          |
| ---------------------- | ----------------------------------------------- |
| ✅ AUC 不跌 + 诊断正常 | → Phase 1b（追加 chaprice）或 Phase 2（行对齐） |
| ❌ AUC 跌或者诊断异常  | → 调参（weight/τ/K）或回退                      |

#### Step 6（可选）：Phase 1b — chaprice 辅助 view

- 预计 +5 行代码（loss() 中加第二路 InfoNCE）
- weight=0.3，其余逻辑复用
- 预期 CVR 额外 +0.05~0.1%

#### Step 7（可选）：Phase 2 — 行对齐

- 配置改：`embedding_dim: 128`
- 代码改：stop-gradient
- 风险：中（config 变更需验证）

### 8.4 完成情况登记表

```diff
! 状态标记: ✅ 已完成 | 🔄 进行中 | ⏳ 待开始 | ❌ 阻塞/回退
```

| 序号 | 任务                         | 文件/范围                            | 优先级 | 依赖  | 状态 | 备注                                  |
| ---- | ---------------------------- | ------------------------------------ | ------ | ----- | ---- | ------------------------------------- |
| 1    | 预计算 item_freq             | 训练脚本                             | P0     | —     | ⏳   | 需确认 hash_bucket_size               |
| 2    | 修改 embedding.py（+2 行）   | `tzrec/modules/embedding.py:556-562` | P0     | —     | ⏳   |                                       |
| 3a   | pepnet `__init__()` 注册参数 | `tzrec/models/pepnet_dcn_ple.py`     | P0     | —     | ⏳   | 需获取 DIN dim + TV idx + item_id key |
| 3b   | pepnet `predict()` 提取特征  | 同上                                 | P0     | 3a    | ⏳   |                                       |
| 3c   | pepnet `loss()` InfoNCE      | 同上                                 | P0     | 3b    | ⏳   | 含 LogQ + HardNegative + Metrics      |
| 4    | 训练 Phase 1a                | 全部                                 | P0     | 1+2+3 | ⏳   | 2-3 epoch 验证                        |
| 5    | 阶段评审                     | —                                    | P0     | 4     | ⏳   | 决策是否推进                          |
| 6    | Phase 1b: chaprice 辅助 view | `pepnet_dcn_ple.py`                  | P2     | 4     | ⏳   | 可跳过                                |
| 7    | Phase 2: 行对齐              | config + .py                         | P2     | 5     | ⏳   | 可跳过                                |
| 8    | Phase 3: 双向 gating         | .py                                  | P3     | 7     | ⏳   | 可跳过                                |

### 8.5 一句话结论

**方案可行，风险可控。** 2 个文件、~60 行代码、0 个配置变更。三个关键理论缺陷（LogQ、HardNegative、诊断）已补齐，参考了 YouTube DNN / Google / Alibaba 的 production 实践。首次实施建议只跑 Phase 1a，用 click_50_seq 主 view 验证效果后再扩展。
