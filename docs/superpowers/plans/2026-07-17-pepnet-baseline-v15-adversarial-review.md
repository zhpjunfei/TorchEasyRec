# PEPNet Baseline v15 优化方案 — 对抗性审核

> 审核视角：大厂算法专家（10年+推荐系统经验）
> 审核原则：不假设方案是正确的，假设方案有漏洞，主动寻找漏洞

______________________________________________________________________

## 一、方案中的事实性错误（必须修正）

### ❌ 错误1：CDOT 输入维度计算错误

**方案声称**："CDOT 将 domain 特征（mmb_id 32dim + item_id 32dim = 64dim）压缩到 4dim"

**事实**：domain group 实际包含 **4 个特征**：

- `mmb_id` (32 dim)
- `item_id` (32 dim)
- `f_req_page` (32 dim)
- `f_req_domain` (16 dim, pad 到 32)

CDOT 输入 = 4 slots × 32 dim = **128 dim**，不是 64 dim。
压缩率 = 128 → 4，压缩率 **32x**，不是 8x。

**影响**：这个错误不影响优化方向（4 维仍然是瓶颈），但影响了我们对"瓶颈严重程度"的判断。128→4 的压缩比 64→4 更极端，CDOT 扩容的优先级应该**更高**而非更低。

### ❌ 错误2：main_group_dim 估算偏差

**方案声称**："main_group_dim ≈ 5728"

**事实**：经精确计算，main_group_dim = **4064**（179 ID + 44 combo + 194 raw 的 embedding_dim 之和）。

**影响**：

- Deep concat dim = 4064 + 4064 + 32 + 4 = **8164**（不是 11492）
- CDOT output_dim 从 4 变 8 时，deep_concat_dim 增加 32，占比 8164 的 **0.4%**（不是之前估算的更小比例）
- 延迟影响确实可以忽略，但参数量增加的计算需要修正

### ❌ 错误3：特征总数统计错误

**方案声称**："425 个特征"

**事实**：

- ID features: 179
- Combo features: 44
- Raw features: 194
- Sequence features: 8（在 sequence_groups 中，不计入 main_group）
- **main_group 中实际使用的特征: 179 + 44 + 194 = 417**

差异不大（425 vs 417），但"425"这个数字没有明确的来源定义。

______________________________________________________________________

## 二、方案中未被充分质疑的关键假设

### ⚠️ 假设1："95%+ 参数在 embedding 层" → 所以架构优化是边际的

**对抗性质疑**：这个假设在**参数数量**上是对的，但在**信息流动**上是错的。

- Embedding 层参数量大，但它们是**静态查找表**，梯度更新稀疏
- Dense 层（PLE + PPNet + EPNet）参数量小，但它们是**信息瓶颈的必经之路**
- 如果 CDOT 的 4 维瓶颈导致 PLE 接收的信息质量下降，那么无论 embedding 多好，信息在 bottleneck 处就被截断了

**类比**：一条高速公路，收费站（bottleneck）只有 4 个车道，不管前面路有多宽，通行能力就是 4 车道。

**修正**：架构优化的优先级应该**上调**，特别是 CDOT 扩容。

### ⚠️ 假设2："ZCH eviction_interval=2 太高频" → 应该调大

**对抗性质疑**：eviction_interval=2 可能不是"太激进"，而是**有意为之**。

- ZCH（Online Embedding Cache）的设计目标是**只缓存活跃 item**
- eviction_interval=2 意味着每 2 个 mini-batch 就评估一次淘汰
- 如果某个 item 在最近 2 个 batch 中没有出现，它的 embedding 就会被 evict
- 这在**非平稳数据分布**下是有意义的：用户的兴趣在变化，旧 embedding 会过时

**反例**：如果 eviction_interval 太大（如 100），ZCH 会变成全量 offline embedding，失去在线 adapt 的意义。

**修正**：不应该简单地调大 eviction_interval，而应该**按特征分别调优**：

- 对于 `mmb_id`（用户 ID）：eviction_interval 应该大（用户画像相对稳定）
- 对于 `item_id`（商品 ID）：eviction_interval 可以小（热点商品变化快）
- 当前所有 14 个 ZCH 特征都用 eviction_interval=2，可能是一刀切

### ⚠️ 假设3："4.5:1 的 CTR:CVR 权重比可能是经验值，未充分搜索"

**对抗性质疑**：CTR weight=4.5 很可能**不是随意设的**，而是经过大量实验确定的。

- 在推荐系统中，CTR 和 CVR 的 loss scale 天然不同
- CTR 是浅层漏斗，样本多，loss 信号强
- CVR 是深层漏斗，样本少（只有点击后才有机会转化），loss 信号弱
- 4.5:1 的权重比很可能是为了让 CVR 的梯度信号不被 CTR 淹没

**更关键的质疑**：权重搜索应该在**同一个验证集**上做，而不是 grid search 每个权重组合。因为：

- 权重变化会影响训练动态（learning rate schedule 不变的情况下）
- 不同权重下，模型的收敛速度和最终性能的关系是非线性的

**修正**：不要做粗粒度的 grid search（1:1, 2:1, ..., 15:1），而应该：

1. 固定 CTR weight=4.5，搜索 CVR weight ∈ [0.1, 0.5, 1.0, 2.0, 5.0]
1. 同时搜索 CTCVR loss 的 temperature 参数
1. 在**验证集上早停**，避免过拟合训练集

### ⚠️ 假设4："8 个 DIN encoder 结构相同，存在冗余"

**对抗性质疑**：DIN encoder 结构相同**不一定是冗余**，可能是**刻意设计**。

- DIN (Deep Interest Network) 的核心思想是：用 target item 作为 attention query，用户行为序列作为 key/value
- 不同行为类型（click vs conversion vs favorite）的序列长度不同（10 vs 50 vs 5）
- 如果让它们共享同一个 DIN encoder，需要通过 sequence_type embedding 来区分
- 但这样做的问题是：**不同类型的行为可能有完全不同的注意力模式**
  - click 序列：用户可能快速点击大量商品，attention 应该更分散
  - conversion 序列：用户可能只转化少数商品，attention 应该更集中

**修正**：不应该简单地去共享 DIN encoder，而应该：

1. 先分析 8 个序列的 attention weight 分布
1. 如果分布相似，再考虑共享
1. 如果分布差异大，说明差异化设计是必要的

______________________________________________________________________

## 三、方案中遗漏的关键优化方向

### 🔴 遗漏1：Raw Feature 的 Bucketize 策略

**发现**：194 个 raw features 中，176 个有 boundaries 配置（FG_BUCKETIZE），18 个没有。

**问题**：

- 160 个 raw features 的 embedding_dim=8，34 个 embedding_dim=4
- 这些 dim=4/8 的 raw features 是通过 bucketize 后的 one-hot embedding 得到的
- 但 18 个没有 boundaries 的 raw features 是怎么处理的？是直接作为 continuous feature 输入 MLP？

**优化方向**：

1. 检查 18 个没有 boundaries 的 raw features 是什么，确认处理逻辑
1. 对 dim=4 的 raw features，考虑是否应该增大 embedding_dim（4 维的表达能力有限）
1. 对 dim=8 的 raw features，检查 boundaries 的分布是否合理（current_price 有 18 个边界，是否过多/过少？）

### 🔴 遗漏2：Combo Features 的组合爆炸问题

**发现**：44 个 combo features 中，`login_city_x_*` 系列有 15 个，`gender_x_*` 系列有 15 个，`dev_brand_x_*` 系列有 15 个。

**问题**：

- 这些 combo features 的 embedding_dim=24（大部分）或 20/12
- 它们的 zch_size 在 98 万到 252 万之间
- 但 `login_city`(4360) × `cate_id_path`(200K) = 8.7 亿组合，zch_size 只有 98 万
- 覆盖率 = 98万 / 8.7亿 = **1.1%**

**优化方向**：

1. 1.1% 的覆盖率意味着绝大多数 combo feature 的 embedding 是随机初始化的
1. 这会导致推理时的 embedding lookup 不稳定（冷启动问题）
1. 考虑对低覆盖率的 combo features 使用 hash embedding 代替 lookup table

### 🔴 遗漏3：Sequence 特征的 max_len 配置

**发现**：8 个 sequence features 中，`click_10_seq` 的 max_len=10，`click_50_seq` 的 max_len=50，等等。

**问题**：

- 不同序列的 max_len 不同，但 DIN encoder 的结构相同（[128, 64]）
- 对于 max_len=5 的 `conversion_5_seq`，DIN 的 attention 机制可能过度设计
- 对于 max_len=50 的 `click_50_seq`，DIN 的 attention 可能不够

**优化方向**：

1. 对短序列（max_len ≤ 10），考虑用简单的 pooling 代替 attention
1. 对长序列（max_len ≥ 50），考虑用 hierarchical attention 或 sampling

### 🔴 遗漏4：Sample Weight 的使用方式

**发现**：`sample_weight_fields: "search_weight"` 在 data_config 中全局设置，`sample_weight_name: "search_weight"` 在 CVR tower 中单独设置。

**问题**：

- search_weight 是什么？是搜索曝光的权重？还是搜索 vs 推荐的权重？
- 如果 search_weight 是用来校正搜索曝光偏差的，那么它对 CTR 和 CVR 的影响应该不同
- 当前配置中，search_weight 只用于 CVR tower，CTR tower 没有用

**优化方向**：

1. 确认 search_weight 的业务含义
1. 如果 search_weight 影响的是整体曝光分布，应该同时用于 CTR 和 CVR
1. 考虑对 CTR tower 也使用 search_weight

______________________________________________________________________

## 四、业务洞见（方案未覆盖的）

### 洞见1：这是一个"搜索+推荐"混合场景

**证据**：

- `f_req_page` 和 `f_req_domain` 是请求上下文特征
- `search_weight` sample_weight 暗示搜索和推荐流量混合
- `chaprice_click_50_seq` 是按价格区间分桶的点击序列 — 这是搜索场景特有的

**业务含义**：

- 搜索流量和推荐流量的用户行为模式完全不同
- 搜索用户有明确的 query，行为更目标导向
- 推荐用户没有明确目标，行为更探索性
- **当前模型没有区分搜索/推荐流量**，这是一个巨大的机会

**优化建议**：

- 添加 `traffic_type` 特征（search vs recommend）
- 在 EPNet 中用 traffic_type 做额外的调制
- 或者，直接拆成两个子模型（搜索模型 + 推荐模型），各自独立训练

### 洞见2：CVR 的 task_space_indicator 可能导致信息损失

**证据**：

- `task_space_indicator_label: "is_click"` — CVR 只在点击空间内预测
- `in_task_space_weight: 1, out_task_space_weight: 0` — 非点击样本的 CVR 损失为 0

**业务含义**：

- 这个设计的假设是：只有点击了的样本才有转化的可能
- 但这个假设在搜索场景下可能不成立 — 用户可能看到商品但不点击（因为价格太高、图片不好看等），但仍然会转化（通过其他方式）
- 更重要的是：**CVR 模型无法学习到"为什么不点击"的信号**

**优化建议**：

- 考虑放宽 task_space_indicator 的限制
- 或者，添加一个"曝光→点击"的独立模型，和一个"点击→转化"的独立模型
- 最终 CVR = P(click|exposure) × P(conversion|click)

### 洞见3：ZCH 的 LFU 淘汰策略可能不是最优的

**证据**：

- 所有 14 个 ZCH 特征都用 `lfu {}`（Least Frequently Used）淘汰策略
- 配合 `threshold_filtering_func: "lambda x: dynamic_threshold_filter(x, 3.0)"`

**业务含义**：

- LFU 只考虑访问频率，不考虑访问时间
- 一个一个月前的热门 item，现在可能已经不热门了
- 但 LFU 不会区分"一个月前访问 100 次"和"昨天访问 100 次"

**优化建议**：

- 考虑改用 LRU（Least Recently Used）或 LFU+时间衰减
- 或者，对不同特征使用不同的淘汰策略：
  - `mmb_id`（用户 ID）：LRU（用户行为在变化）
  - `item_id`（商品 ID）：LFU（商品热度相对稳定）
  - `login_city_x_spu_id`（交叉特征）：LFU+时间衰减

______________________________________________________________________

## 五、修正后的优化优先级

| 原优先级 | 优化项                      | 修正后优先级 | 修正理由                                                    |
| -------- | --------------------------- | ------------ | ----------------------------------------------------------- |
| P0       | 1. CDOT 瓶颈扩容            | **P0↑**      | 压缩率 32x 比 8x 更极端，瓶颈更严重                         |
| P0       | 2. ZCH Eviction 调优        | **P1↓**      | eviction_interval=2 可能是有意设计，不应一刀切调大          |
| P0       | 6. CTCVR 权重搜索           | **P0→P1**    | 4.5:1 可能已是经验最优值，需更精细的搜索策略                |
| P1       | 3. 特征消融实验             | **P0↑**      | 417 个特征中可能有大量冗余，且 combo features 覆盖率仅 1.1% |
| P1       | 4. DIN Encoder 共享         | **P2↓**      | 不同行为类型的 attention 模式可能不同，不应盲目共享         |
| P1       | 5. 梯度冲突监控             | **P1→P2**    | 已有 hooks 但未使用，属于锦上添花                           |
| P2       | 7. 分桶策略优化             | **P1↑**      | 18 个 raw features 没有 boundaries，需要排查                |
| NEW      | 8. 搜索/推荐流量拆分        | **P0**       | 方案完全遗漏，但业务影响巨大                                |
| NEW      | 9. Combo Feature 覆盖率优化 | **P0**       | 1.1% 覆盖率是严重的冷启动问题                               |
| NEW      | 10. Search Weight 全局化    | **P1**       | 可能影响 CTR 和 CVR 的公平性                                |

______________________________________________________________________

## 六、最终建议

### 立即执行（本周）

1. **CDOT 扩容实验**（output_dim: 4→8→16）

   - 改动最小（只改一个配置参数）
   - 预期收益最大（32x 压缩率的瓶颈）
   - 验证方法：对比 CTR-AUC 和 CVR-AUC

1. **Combo Feature 覆盖率分析**

   - 统计每个 combo feature 的 zch_size / 理论组合数
   - 对覆盖率 < 5% 的特征，考虑 hash embedding
   - 验证方法：对比推理稳定性和 AUC

1. **Search Weight 全局化实验**

   - 对 CTR tower 也使用 search_weight
   - 验证方法：对比 CTR-AUC 和 CVR-AUC

### 短期迭代（本月）

4. **特征消融实验**（系统性的，不是简单的 bottom 30%）

   - 按特征组别消融：先消融 combo features，再消融 raw features
   - 验证方法：AUC 变化 vs 延迟变化

1. **ZCH 淘汰策略差异化**

   - 对不同特征使用不同的 eviction 策略
   - 验证方法：训练稳定性、长尾 item AUC

### 中长期优化

6. **搜索/推荐流量拆分**

   - 添加 traffic_type 特征，或在 EPNet 中做流量调制
   - 验证方法：A/B test

1. **CVR 漏斗建模优化**

   - 考虑 P(click) × P(convert|click) 的两阶段建模
   - 验证方法：Business Metrics（GMV/Revenue）

______________________________________________________________________

## 七、审核结论

**方案评分**：6/10

**优点**：

- 发现了 CDOT 瓶颈、ZCH eviction、CTCVR 权重等关键问题
- 实验设计有层次，优先级矩阵清晰
- Karpathy 视角的"特征工程 > 架构"认知是正确的

**缺点**：

- 事实性错误（CDOT 输入维度、main_group_dim）
- 遗漏了搜索/推荐流量拆分、Combo Feature 覆盖率等关键问题
- 对 ZCH eviction 和 DIN encoder 共享的分析过于表面
- CTCVR 权重搜索的策略不够精细

**核心修正**：

1. CDOT 扩容的优先级应该**上调**（压缩率 32x，不是 8x）
1. 搜索/推荐流量拆分应该**新增为 P0**（业务影响巨大）
1. Combo Feature 覆盖率问题应该**新增为 P0**（1.1% 覆盖率是严重的冷启动问题）
1. ZCH eviction 调优应该**下调**（一刀切调大可能破坏设计意图）
