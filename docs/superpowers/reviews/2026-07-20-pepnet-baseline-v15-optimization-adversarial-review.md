# PEPNet Baseline v15 优化方案 — 对抗性审核报告

> **审核视角**：大厂算法专家（10年+推荐系统经验）
> **审核原则**：不假设方案是正确的，假设方案有漏洞，主动寻找漏洞
> **审核日期**：2026-07-20
> **审核对象**：
>
> - `docs/superpowers/plans/2026-07-17-pepnet-baseline-v15-optimization.md`（优化方案）
> - `docs/superpowers/plans/2026-07-20-zch-eviction-differentiation.md`（ZCH差异化方案）
> - `data/pepnet_demo/config/v15/home_flow_2604_v15_baseline.config`（基线配置）

______________________________________________________________________

## 一、事实性错误修正

### ❌ 错误1：CDOT 输入维度计算错误（方案已修正，但影响后续推导）

**方案原文**："CDOT 将 domain 特征（mmb_id 32dim + item_id 32dim = 64dim）压缩到 4dim"

**核实**：`feature_groups` 中 domain group 实际包含 4 个特征：

- `mmb_id` (32 dim)
- `item_id` (32 dim)
- `f_req_page` (32 dim)
- `f_req_domain` (16 dim, pad 到 32)

CDOT 输入 = 4 slots × 32 dim = **128 dim**，压缩率 128→4 = **32x**。

**审核意见**：这个错误在对抗性审核中被发现并已修正。32x 压缩比更加极端，CDOT 扩容优先级应上调。但需注意：`cdot.input_dim: 32` 在配置中只写了 32，这意味着 CDOT 的输入可能是每个 slot 单独处理后再 concat，而非 128 dim 扁平输入。**需要确认 TorchEasyRec 中 CDOT 模块的实际输入维度计算方式。**

### ❌ 错误2：main_group_dim 估算偏差

**方案声称**："main_group_dim ≈ 5728"

**核实**：经逐特征统计，`group_name: "all"` 中包含 179 个 ID + 44 个 combo + 194 个 raw，embedding_dim 之和 = **4064**（非 5728）。

**影响**：

- Deep concat dim = 4064×2 + 32(domain) + 4(cdot) = **8164**
- CDOT output_dim 从 4→8 时，deep_concat_dim 增加 32，占比 8164 的 **0.39%**
- 对延迟的影响确实可忽略

### ❌ 错误3：Combo Feature 中 ZCH 特征数量统计不完整

**方案声称**："14 个 ZCH 特征：1 个 ID + 13 个 combo"

**核实**：配置中实际有 **14 个 combo feature 使用了 ZCH**，加上 `mmb_id` 和 `item_id`（也是 ZCH），总计 **16 个特征使用 ZCH**。

ZCH 特征清单（经逐条核对）：

| 特征名                       | 类型  | ZCH Size   | 有 ZCH           |
| ---------------------------- | ----- | ---------- | ---------------- |
| mmb_id                       | ID    | 2,529,348  | ✅               |
| item_id                      | ID    | -          | ❌ (无 ZCH 配置) |
| login_city_x_cate_id_path_fg | Combo | 981,042    | ✅               |
| login_city_x_brand_fg        | Combo | 1,524,655  | ✅               |
| login_city_x_core_entity_fg  | Combo | 1,338,803  | ✅               |
| login_city_x_publish_user_fg | Combo | 710,140    | ✅               |
| login_city_x_spu_id_fg       | Combo | 13,736,118 | ✅               |
| login_city_x_username_fg     | Combo | 1,724,928  | ✅               |
| gender_x_spu_id_fg           | Combo | 1,098,861  | ✅               |
| dev_brand_x_spu_id_fg        | Combo | 2,103,185  | ✅               |
| dev_brand_x_username_fg      | Combo | 729,560    | ✅               |
| brand_x_price_tag_fg         | Combo | 599,370    | ✅               |
| brand_x_cate_id_path_fg      | Combo | 432,110    | ✅               |
| price_tag_x_cate_id_path_fg  | Combo | 142,530    | ✅               |
| price_tag_x_spu_id_fg        | Combo | 947,151    | ✅               |

**注意**：`item_id` 虽然是一个关键特征，但配置中**没有 ZCH**。这意味着 `item_id` 的 embedding 是静态的、全量加载的。对于一个可能有数百万商品的平台，这是一个值得关注的点。

______________________________________________________________________

## 二、方案中未被充分质疑的关键假设

### ⚠️ 假设1："95%+ 参数在 embedding 层 → 所以架构优化是边际的"

**对抗性质疑**：这个推理在**参数数量**上正确，但在**信息流动**上犯了范畴错误。

- Embedding 层参数大但梯度稀疏（大部分 embedding 在单个 batch 中不会被访问）
- Dense 层（CDOT + EPNet + PLE + PPNet + Tower）参数小但是**信息瓶颈的必经之路**
- 如果 CDOT 的 4 维瓶颈导致信息截断，那么无论 embedding 多好、特征工程多精妙，信息在 bottleneck 处就已经丢失了

**类比**：一条 128 车道的高速公路，在入口处只有一个 4 车道的收费站。不管前面路多宽，通行能力就是 4 车道。

**修正**：架构优化（CDOT 扩容）的优先级应**上调至 P0**，与特征工程并列。

### ⚠️ 假设2："eviction_interval=2 一刀切 → 应该差异化"

**对抗性质疑**：`eviction_interval=2` 可能不是"太激进"，而是**有意为之的设计选择**。

ZCH（Zero Collision Hash）在线缓存的核心设计哲学是：**只缓存当前活跃的 item，不缓存过时的 item**。

- eviction_interval=2 意味着每 2 个 mini-batch 就评估一次淘汰
- 在 batch_size=4096 的情况下，2 个 step = 8192 条样本
- 如果某个组合在最近 8192 条样本中没有出现，它的 embedding 就会被淘汰

这在**非平稳数据分布**下是有意义的：用户兴趣在变化，旧 embedding 会过时。

**但是**，差异化策略（ZCH 方案）的方向是正确的——只是论证需要修正：

- 不是"2 太激进，应该调大"
- 而是"不同类型特征的稳定性不同，应该用不同 policy + interval"

**修正**：ZCH 差异化方案的方向正确，但论据应从"eviction_interval=2 太高频"改为"不同特征类型的稳定性不同，需要匹配的 eviction policy"。

### ⚠️ 假设3："CTR weight=4.5 可能不是最优值 → 应该 grid search"

**对抗性质疑**：CTR weight=4.5 很可能**不是随意设的**，而是经过大量实验确定的经验值。

在推荐系统中：

- CTR 是浅层漏斗（曝光→点击），样本充足，loss 信号强
- CVR 是深层漏斗（曝光→点击→转化），样本稀疏（只有点击后才有转化标签），loss 信号弱
- 4.5:1 的权重比是为了让 CVR 的梯度信号不被 CTR 淹没

**更关键的质疑**：

1. **CVR 使用了 `sample_weight_name: "search_weight"`** — 这意味着 CVR 的 loss 不仅受 weight=1.0 控制，还受到 search_weight 的动态缩放。grid search 应该搜索的是 `weight × search_weight` 的联合效果，而非单独搜索 weight。
1. **`use_ctcvr_loss: true`** — CTCVR loss 引入了 CTR→CVR 的辅助连接，这会进一步改变 CTR/CVR 之间的梯度关系。单独调整 tower weight 可能不会达到预期效果。
1. **`cvr_add_ctr_logits: false`** — CVR 不直接使用 CTR 的 logits，这意味着 CTR 和 CVR 的梯度冲突可能比预期更严重。

**修正**：

- 不要做粗粒度的 grid search（1:1, 2:1, ..., 15:1）
- 应该做**联合搜索**：CTR weight ∈ [3.0, 4.5, 6.0, 8.0] × CVR weight ∈ [0.5, 1.0, 2.0]
- 同时监测 CTCVR loss 的温度参数（如果有的话）
- **最重要的是**：在验证集上早停，避免过拟合训练集

### ⚠️ 假设4："8 个 DIN encoder 共享相同结构 → 存在冗余"

**对抗性质疑**：DIN encoder 结构相同**不一定是冗余**，可能是**刻意设计**。

8 个 DIN encoder 分别对应 8 个 sequence group：

1. `click_10_seq` — 近 10 次点击行为
1. `click_50_seq` — 近 50 次点击行为
1. `conversion_5_seq` — 近 5 次转化行为
1. `conversion_20_seq` — 近 20 次转化行为
1. `favorite_5_seq` — 近 5 次收藏行为
1. `favorite_10_seq` — 近 10 次收藏行为
1. `like_50_seq` — 近 50 次点赞行为
1. `chaprice_click_50_seq` — 近 50 次价格区间相关的点击行为

**关键洞察**：

- 不同行为类型（click/conversion/favorite/like）的 attention 模式**天然不同**
- 同一行为类型不同窗口长度（5/10/20/50）捕捉的**时间粒度不同**
- `chaprice_click_50_seq` 是一个**价格感知的点击序列**，它的 attention 模式可能与其他 click sequence 完全不同

**结论**：共享 DIN encoder 结构是合理的（符合 DIN 的设计哲学），但**可以考虑为不同类型的行为使用不同的 attention MLP 结构**。例如：

- Conversion 行为的 attention 可能更需要深度建模（更深的 MLP）
- Click 行为的 attention 可能更浅（用户点击意图更直接）

### ⚠️ 假设5："Combo Feature 覆盖率极低 → 需要 hash embedding"

**对抗性质疑**：方案中提到"对覆盖率 < 5% 的特征，考虑 hash embedding"，但这可能**适得其反**。

Hash embedding 的本质是**用碰撞换容量**——将高维稀疏特征映射到低维稠密空间。但对于 combo features：

- 低覆盖率意味着大部分组合**从未在训练集中出现过**
- Hash embedding 会让这些"未出现过的组合"在 embedding 空间中**互相碰撞**，产生不可控的梯度干扰
- 更重要的是：ZCH 的存在就是为了**动态管理 combo 特征的在线缓存**，hash embedding 会削弱 ZCH 的效果

**修正**：

- 对于覆盖率 < 1% 的 combo features，优先考虑**增大 ZCH size** 而非 hash embedding
- 或者，考虑**特征过滤**：在特征工程中直接去掉覆盖率 < 0.1% 的 combo feature

### ⚠️ 假设6："ZCH eviction policy 不影响线上推理延迟"

**方案声称**："eviction 在 training 时评估，不影响 inference"

**核实**：这个说法**不完全正确**。

- ZCH 的 eviction policy 影响的是**训练过程中的 embedding 更新频率**
- 但 ZCH 缓存的 embedding 会**同时用于线上推理**（online serving）
- 如果 eviction policy 导致缓存命中率下降，线上推理的 cache miss 会增加，进而增加**线上 embedding 查询的延迟**

**修正**：ZCH 差异化方案需要同时评估：

1. 训练效果（AUC、loss 稳定性）
1. 线上推理延迟（cache hit rate → query latency）

______________________________________________________________________

## 三、方案中完全遗漏的关键问题

### 🔴 遗漏1：`item_id` 没有 ZCH 配置

**事实**：`item_id` 是模型中最核心的特征之一（所有推荐都是围绕 item 展开的），但配置中**没有为 item_id 配置 ZCH**。

**影响**：

- `item_id` 的 embedding 是全量加载的静态表
- 如果 item 池很大（数百万级），这会占用大量 GPU memory
- 更重要的是：`item_id` 的 embedding 无法在线 adapt，无法捕捉 item 的**动态属性变化**（如价格变化、库存变化、季节性变化）

**建议**：

- 考虑为 `item_id` 添加 ZCH 配置
- 或者，将 `item_id` 的 embedding 更新频率提高到每个 epoch

### 🔴 遗漏2：Raw Feature 的分桶边界质量未知

**事实**：194 个 raw features 中，一部分有 `boundaries`（如 `current_price` 有 22 个分桶边界），但大量 raw features（特别是 ratio 特征和 kv 特征）**没有 boundaries**。

**影响**：

- 没有 boundaries 的 raw features 会使用**默认的线性分桶**或**直接作为 continuous feature** 处理
- 对于 ratio 特征（如 `gender__ratio_click_exposure_15d`），默认分桶可能不是最优的
- 对于 kv 特征（如 `user__kv_cate_id_path_click_15d`），它们本质上是**统计量**，应该有专门的分桶策略

**建议**：

- 对没有 boundaries 的 raw features，统计其值域分布，重新设计分桶策略
- 特别关注 ratio 特征的**偏态分布**（通常是长尾分布），使用 quantile-based binning 而非 uniform binning

### 🔴 遗漏3：Sequence Feature 的时间信息丢失

**事实**：8 个 sequence group 中，有 timestamp 特征（`click_10_seq__ts`、`click_50_seq__ts`），但在 DIN encoder 中**没有使用时间衰减**。

**影响**：

- DIN 的 attention 机制对所有历史行为赋予**平等的权重**（除了 target item 的 attention）
- 但用户**昨天的点击**和**30 天前的点击**对当前行为的预测能力完全不同
- 时间信息被丢弃了，这是一个明显的信号损失

**建议**：

- 在 DIN attention 中加入**时间衰减因子**：`attention_score *= exp(-delta_t / tau)`
- 或者，将 timestamp 作为一个额外的 raw feature 输入到 attention MLP 中

### 🔴 遗漏4：Search Weight 的公平性问题

**事实**：CVR tower 使用 `sample_weight_name: "search_weight"`，但 CTR tower **没有使用 search_weight**。

**影响**：

- search_weight 只在 CVR 的 loss 中被应用，CTR 的 loss 不受影响
- 这可能导致 CTR 和 CVR 的梯度尺度不一致，影响多任务学习的稳定性
- 更重要的是：search_weight 的目的是**校正搜索流量的样本偏差**，如果只对 CVR 校正而不对 CTR 校正，可能导致 CTR 模型学到**有偏的表示**

**建议**：

- 考虑对 CTR tower 也使用 search_weight
- 或者，在 EPNet 中加入 traffic_type 调制（搜索 vs 推荐）

### 🔴 遗漏5：PLE Expert 数量可能不足

**事实**：两层 PLE 中，每层只有 `expert_num_per_task: 2` + `share_num: 2`，即每层总共 6 个 expert（2 task-specific + 2 shared）。

**影响**：

- 对于 417 个特征、8164 dim 的 deep concat 输入，6 个 expert 可能不足以捕捉复杂的特征交互
- 特别是 CTR 和 CVR 两个任务的 expert 只有 2 个，容量有限

**建议**：

- 实验 `expert_num_per_task: 4` + `share_num: 4`（每层 12 个 expert）
- 或者，使用 **IPLE（Improved PLE）** 的 cascading architecture，让低层的 expert 输出作为高层的输入

______________________________________________________________________

## 四、ZCH 差异化方案的专项审核

### ✅ 方案优点

1. **分类逻辑合理**：按特征类型（ID/Combo）和行为模式（稳定/中稳/不稳定）分类，符合业务直觉
1. **Policy 选择有据**：LRU for 用户画像、DistanceLFU for combo features，理论支撑充分
1. **Decay exponent 设计**：C 类 combo features 用 decay_exponent=2.0（二次衰减），符合低覆盖率特征的快速淘汰需求

### ⚠️ 方案问题

#### 问题1：A 类特征分类不完整

方案将 `mmb_id` 归为 A 类（用户画像特征），但忽略了其他可能属于"稳定型"的特征：

- `login_city`、`province`、`gender`、`os_type` 等用户属性特征虽然不在 ZCH 中，但它们与 ZCH 特征的交互（如 `login_city_x_*`）的稳定性也值得考虑
- 如果 `login_city` 不变，那么 `login_city_x_spu_id` 的变化主要来自 `spu_id` 侧

**建议**：考虑将 combo features 进一步细分为：

- **User-side stable combos**：user 端特征稳定（如 `login_city`），combo 变化主要由 item 端驱动
- **Item-side stable combos**：item 端特征稳定（如 `brand`），combo 变化主要由 user 端驱动
- **Both-unstable combos**：两端都不稳定（如 `price_tag_x_spu_id`）

#### 问题2：DistanceLFU 的实现依赖

方案假设 TorchEasyRec 支持 `distance_lfu {}` eviction policy。需要确认：

- TorchRec 的 `MCHManagedCollisionModule` 是否实现了 DistanceLFU？
- 如果没实现，`distance_lfu {}` 配置会被忽略还是报错？

**建议**：在实验前，先验证配置的可解析性和运行时行为。

#### 问题3：不同 ZCH 特征的 memory footprint 差异

方案提到 `login_city_x_spu_id_fg` 的 zch_size=13,736,118，是最大的 ZCH 特征。

如果 DistanceLFU 需要维护 `last_access_iter`，那么每个 slot 需要额外 4 bytes（int32）。对于 13.7M 的 zch_size，额外内存 = 13.7M × 4 bytes ≈ **55MB**。

14 个 ZCH 特征的总 zch_size ≈ 50M，额外内存 ≈ **200MB**。

**影响**：200MB 的额外内存对于 GPU training 来说是可接受的，但如果 GPU memory 已经紧张，可能需要评估。

#### 问题4：Eviction Interval 的计算开销

方案提到"eviction_interval=2 意味着每秒评估数百次"，但没有量化计算开销。

对于 zch_size=13.7M 的特征，每次 eviction 评估需要遍历 13.7M 个 slot。如果 interval=2，batch_size=4096，每个 epoch 有 N 个 step：

- 每个 epoch 的 eviction 评估次数 = N × (1/2)
- 每次评估的计算量 = 13.7M × O(1)

如果 N=1500（约 1 epoch），则 eviction 评估次数 ≈ 750 次，总计算量 ≈ 750 × 13.7M ≈ **10B 次操作**。

**影响**：这个计算量在 CPU 上大约需要几秒到几十秒，相对于训练时间（分钟级）是可接受的。但如果多个大 zch_size 特征同时评估，可能会有累积效应。

______________________________________________________________________

## 五、修正后的优化优先级

| 原优先级 | 优化项                   | 修正后优先级 | 修正理由                                                      |
| -------- | ------------------------ | ------------ | ------------------------------------------------------------- |
| P0       | 1. CDOT 瓶颈扩容         | **P0↑**      | 压缩率 32x，且 `item_id` 无 ZCH 导致 embedding 无法在线 adapt |
| P0       | 2. ZCH Eviction 调优     | **P0→P1**    | 方向正确但实现细节需验证（DistanceLFU 可用性）                |
| P0       | 6. CTCVR 权重搜索        | **P1**       | 4.5:1 可能已是经验最优值，需联合搜索 search_weight            |
| P1       | 3. 特征消融实验          | **P0↑**      | 16 个 ZCH 特征 + 417 个 main features 中必有冗余              |
| P1       | 4. DIN Encoder 共享      | **P2**       | 共享结构合理，但可为不同类型行为设计不同 attention            |
| P1       | 5. 梯度冲突监控          | **P1→P2**    | 锦上添花，不影响核心效果                                      |
| P2       | 7. 分桶策略优化          | **P1↑**      | 大量 raw features 无 boundaries，需排查                       |
| NEW      | 8. item_id ZCH 化        | **P0**       | 核心特征无 ZCH，无法在线 adapt                                |
| NEW      | 9. Sequence 时间衰减     | **P1**       | DIN 丢弃时间信息，是明显信号损失                              |
| NEW      | 10. Search Weight 全局化 | **P1**       | CVR 用 search_weight 但 CTR 不用，可能导致梯度不平衡          |
| NEW      | 11. PLE Expert 扩容      | **P2**       | 6 个 expert 可能不足，但需要实验验证                          |

______________________________________________________________________

## 六、最终建议

### 立即执行（本周）

1. **CDOT 扩容实验**（output_dim: 4→8→16）

   - 改动最小（只改一个配置参数）
   - 预期收益最大（32x 压缩率的瓶颈）
   - **验证方法**：对比 CTR-AUC 和 CVR-AUC

1. **Combo Feature 覆盖率分析 + item_id ZCH 化**

   - 统计每个 combo feature 的 zch_size / 理论组合数
   - 为 `item_id` 添加 ZCH 配置，使其能够在线 adapt
   - **验证方法**：对比推理稳定性和 AUC

1. **特征消融实验**（系统性的）

   - 按特征组别消融：先消融 combo features，再消融 raw features
   - **验证方法**：AUC 变化 vs 延迟变化

### 短期迭代（本月）

4. **ZCH 淘汰策略差异化**

   - 对不同特征使用不同的 eviction policy
   - **前提**：先验证 DistanceLFU 在 TorchRec 中的可用性
   - **验证方法**：训练稳定性、长尾 item AUC

1. **Search Weight 全局化实验**

   - 对 CTR tower 也使用 search_weight
   - **验证方法**：对比 CTR-AUC 和 CVR-AUC

1. **Sequence 时间衰减实验**

   - 在 DIN attention 中加入时间衰减因子
   - **验证方法**：对比 AUC 和推理延迟

### 中长期优化

7. **PLE Expert 扩容实验**

   - 从 6 个 expert 增加到 12 个
   - **验证方法**：对比 AUC 和训练时间

1. **Raw Feature 分桶优化**

   - 对没有 boundaries 的 raw features 重新设计分桶策略
   - **验证方法**：对比各特征对 AUC 的边际贡献

______________________________________________________________________

## 七、审核结论

**方案评分**：6.5/10（较初版有所提升）

**优点**：

- 发现了 CDOT 瓶颈、ZCH eviction、CTCVR 权重等关键问题
- ZCH 差异化方案的分类逻辑合理，policy 选择有据
- 实验设计有层次，优先级矩阵清晰
- Karpathy 视角的"特征工程 > 架构"认知是正确的

**缺点**：

- 事实性错误（CDOT 输入维度、main_group_dim、ZCH 特征数量）
- 遗漏了 `item_id` 无 ZCH、Sequence 时间信息丢失、Search Weight 公平性等关键问题
- 对 ZCH eviction 和 DIN encoder 共享的分析仍需深化
- CTCVR 权重搜索的策略不够精细（未考虑 search_weight 的联合影响）

**核心修正**：

1. CDOT 扩容的优先级应**上调至 P0**（压缩率 32x）
1. `item_id` 无 ZCH 应**新增为 P0**（核心特征无法在线 adapt）
1. Sequence 时间衰减应**新增为 P1**（明显信号损失）
1. Search Weight 全局化应**新增为 P1**（可能导致梯度不平衡）
1. ZCH eviction 调优应**下调至 P1**（需先验证 DistanceLFU 可用性）

**一句话总结**：方案方向正确，但遗漏了几个关键的结构性问题（item_id ZCH、时间衰减、search weight 公平性）。建议在执行方案之前，先补充这些问题的小型实验。
