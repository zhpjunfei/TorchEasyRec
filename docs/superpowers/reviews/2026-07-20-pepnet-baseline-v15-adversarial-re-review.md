# PEPNet Baseline v15 优化方案 — 对抗性重审

> **审核视角**：对上一版审核报告本身进行对抗性质疑
> **审核原则**：假设上一版审核有漏洞、有偏见、有过度自信的判断
> **审核日期**：2026-07-20
> **审核对象**：`docs/superpowers/reviews/2026-07-20-pepnet-baseline-v15-optimization-adversarial-review.md`

______________________________________________________________________

## 一、上一版审核自身的结构性缺陷

### 🔴 缺陷1：审核者过度自信于"CDOT 32x 压缩"叙事，但忽略了 CDOT 的真实作用

**上一版审核的说法**："CDOT 输入 128 dim，输出 16 dim，压缩率 32x，是致命瓶颈。"

**对抗性质疑**：这个说法混淆了两个概念——**压缩率**和**信息损失**。

CDOT 的实际机制（经源码核实）：

```
输入: [B, 4, 32]  (4 slots × 32 dim)
子压缩: sub_compress_weight [4, 32] → [B, 4*32=128, 4] → reshape → [B, 128, 4]
压缩MLP: 128*32=4096 → 512 → 374 → 4*4=16
变换: transposed [B, 32, 4] × compress_wt [B, 4, 4] + bias [1, 32, 4]
输出: allint_out [B, 16] + allint_mid_out [B, 16]
```

关键洞察：**CDOT 的输出 (16 dim) 是作为 ADDITIONAL 信息拼接到 deep feature 中的**，不是替代 domain group 的原始 embedding。domain group 的 4 个特征（mmb_id, item_id, f_req_page, f_req_domain）同时也出现在 "all" main group 中，它们的原始 embedding 也进入了模型。

**所以上一版审核犯了一个系统性错误**：将 CDOT 描述为"信息瓶颈"隐含的意思是"CDOT 输出了太少信息"。但实际上：

1. domain group 的原始 embedding 已经通过 "all" group 进入模型（4 × 32 = 128 dim）
1. CDOT 输出是额外的 16 dim 变换特征
1. 即使 CDOT 的 16 dim 信息量有限，原始 128 dim 仍然可达

**修正**：CDOT 扩容的优先级应**下调**。CDOT 不是瓶颈——domain group 的原始 embedding 已经提供了完整信息。CDOT 的作用是**提供非线性变换后的交叉信号**，扩容的收益可能远小于预期。

### 🔴 缺陷2：上一版审核声称"item_id 无 ZCH 是 P0 问题"，但这个判断缺乏依据

**上一版审核的说法**："item_id 是核心特征，无 ZCH 导致无法在线 adapt，应新增为 P0。"

**对抗性质疑**：

1. **item_id 是否需要 ZCH？** ZCH 的设计目的是缓存**高频访问但组合空间大**的特征，避免全量加载。item_id 的 hash_bucket_size = 3,000,000，embedding_dim = 32，全量加载需要 3M × 32 × 4 bytes = **384 MB**。这在 GPU 上是完全可接受的。
1. **ZCH 的主要价值是"动态淘汰冷启动 embedding"**。但 item_id 的 embedding 代表的是**物品本身的静态属性**（品类、价格区间、品牌等），这些属性变化很慢。相比之下，combo features（如 login_city_x_spu_id）才真正需要动态缓存——因为它们代表的是**用户-物品的交互模式**，变化更快。
1. **如果 item_id 真的需要 ZCH，为什么设计者没有加？** 这很可能是一个深思熟虑的决定：item_id 的 embedding 需要全局一致性（同一个 item 在不同用户面前应该有相同的 embedding），而 ZCH 会导致 embedding 随训练动态变化，破坏一致性。

**修正**：item_id ZCH 化不应是 P0，最多是 **P2（低优先级探索）**。而且如果要做，需要首先回答"为什么要做"——当前的理由（"无法在线 adapt"）站不住脚，因为 item_id 本身就是静态属性。

### 🔴 缺陷3：上一版审核对"Sequence 时间信息丢失"的批评，忽略了 DIN 的设计哲学

**上一版审核的说法**："DIN 丢弃时间信息，是明显信号损失。"

**对抗性质疑**：

1. **DIN 的设计本来就是不用时间信息的**。DIN (Deep Interest Network) 的核心思想是：用 target item 作为 query，用户历史行为序列作为 key/value，做 attention 加权。**attention 权重本身就隐含了"相关性"排序**——与 target item 更相关的行为自然获得更高的 attention score，这在功能上等价于某种形式的时间/相关性加权。
1. **加入时间衰减是可选增强，不是缺失**。在学术文献中，DIEN (Deep Interest Evolution Network) 才是引入时间感知的 DIN 扩展版本。但 DIEN 的增益在很多工业场景中并不显著，尤其是当序列长度很短（10/50）时。
1. **8 个 sequence group 中，5 个都有 `click_10_seq__ts` / `click_50_seq__ts` 时间戳特征**。这些时间戳被包含在 sequence group 中，只是没有被 DIN encoder 使用。这可能是刻意为之——DIN 的 attention 机制已经足够捕捉行为的相关性，显式加入时间可能反而引入噪声。

**修正**：Sequence 时间衰减不应是 P1，应该是 **P2（低优先级探索）**。除非有明确的 ablation 证明 DIN 的 attention 无法替代时间建模。

### 🔴 缺陷4：上一版审核对"Search Weight 公平性"的批评，忽略了业务逻辑

**上一版审核的说法**："CVR 用 search_weight 但 CTR 不用，可能导致梯度不平衡。"

**对抗性质疑**：

1. **search_weight 的作用是什么？** 在搜索场景中，search_weight 通常用于校正**样本选择偏差**——搜索流量中的样本可能不代表整体分布。CVR 使用 search_weight 是因为**只有搜索流量才有转化标签**（用户在搜索后点击并转化），而推荐流量可能没有转化标签或标签质量低。
1. **CTR 不使用 search_weight 可能是刻意的**。CTR 的目标是预测"用户是否会点击"，这是一个**全局可观测的标签**（无论搜索还是推荐，都能观察到点击）。因此 CTR 不需要校正搜索偏差。
1. **即使 CTR 和 CVR 的 sample_weight 不同，也不会导致梯度不平衡**。梯度不平衡的根本原因是 CTR loss 和 CVR loss 的**量级不同**，这由 tower weight（4.5 vs 1.0）控制，而非 sample_weight。sample_weight 影响的是每个样本的 loss 贡献，而 tower weight 影响的是整个任务的梯度尺度。

**修正**：Search Weight 全局化不应是 P1，应该是 **P3（不需要做）**。当前的设计（CVR 用 search_weight，CTR 不用）更符合业务逻辑。

### 🔴 缺陷5：上一版审核对"PLE Expert 数量不足"的批评，缺乏定量分析

**上一版审核的说法**："6 个 expert 可能不足以捕捉复杂的特征交互。"

**对抗性质疑**：

1. **PLE 的 expert 数量不是瓶颈**。每一层 PLE 有 `expert_num_per_task: 2` + `share_num: 2` = 4 experts per layer，两层共 8 experts。但每个 expert 的 hidden units 是 [512, 256] 和 [256, 128]，参数量分别是 ~400K 和 ~100K。总参数量约 **1M**，相对于 embedding 的 1.3B 来说微不足道。
1. **Expert 数量的瓶颈不在于容量，而在于路由质量**。如果 EPNet 的 gate 不能正确地将特征路由到合适的 expert，增加 expert 数量只会增加路由的复杂度，而不提升效果。
1. **CGC（Customized Gate Control）的 share expert 设计本身就是为了解决"expert 数量不足"的问题**。share expert 可以被多个任务共享，本质上相当于增加了有效 expert 数量。

**修正**：PLE Expert 扩容不应是 P2，应该是 **P3（不建议做）**。瓶颈不在 expert 数量，而在 gate 的质量。

______________________________________________________________________

## 二、上一版审核遗漏的真正关键问题

### 🔴 新问题1：CDOT 的 compress_hidden_units [512, 374] 设计可疑

**配置**：

```protobuf
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 374]
}
```

**分析**：

- CDOT 的 compress_mlp 输入维度 = input_dim × mid_dim = 32 × 32 = **1024**
- 但 compress_hidden_units 的第一层是 512，这意味着 MLP 是：1024 → 512 → 374 → 16 (4 slots × 4 output_dim)
- **512 和 374 这两个数字是怎么来的？** 它们不是标准的 2 的幂次，也不符合常见的 MLP 设计模式（如 1024→512→256→128→64）。
- 更可疑的是：374 × 4 = 1496，而输出是 16。从 374 维压缩到 16 维，中间只有一层线性变换，**这几乎是一个恒等映射**——374 维的信息被粗暴地投影到 16 维，几乎没有非线性变换。

**建议**：

- 检查 compress_hidden_units 是否经过了超参数搜索
- 考虑尝试 [512, 256, 128] 或 [512, 256] 的更标准设计
- 或者，直接将 compress_hidden_units 设为空（只用 sub_compress_weight），让 CDOT 退化为简化的矩阵乘法

### 🔴 新问题2：PPNet 的隐藏层 [512, 256, 128] 与 Tower 的隐藏层 [512, 256, 128] 完全相同

**配置**：

```protobuf
ppnet_hidden_units: [512, 256, 128]
...
task_towers {
  tower_name: "ctr"
  mlp {
    hidden_units: [512, 256, 128]
  }
}
task_towers {
  tower_name: "cvr"
  mlp {
    hidden_units: [512, 256, 128]
  }
}
```

**分析**：

- PPNet（LHUC 个性化调制网络）负责将 PLE 的输出调制为 task-specific 表示
- Tower 负责最终的 CTR/CVR 预测
- 两者使用完全相同的隐藏层结构 [512, 256, 128]，这意味着 PPNet 的输出维度 = 128，Tower 的输入维度 = 128
- **这是一个巧合还是刻意为之？** 如果刻意为之，说明设计者认为 PPNet 的调制输出 128 dim 正好适合 Tower 的输入。但如果 PPNet 的调制不够充分，128 dim 可能不足以区分 CTR 和 CVR 的不同需求。

**建议**：

- 实验 PPNet 输出维度 ≠ Tower 输入维度的情况（如 PPNet [512, 256, 128] → Tower [256, 128]）
- 或者，让 CTR 和 CVR 使用不同深度的 Tower（CTR [512, 256] vs CVR [512, 256, 128, 64]）

### 🔴 新问题3：`fg_mode: FG_BUCKETIZE` 与 pre-encoded pipeline 的兼容性风险

**配置**：

```protobuf
data_config {
  fg_mode: FG_BUCKETIZE
}
```

**分析**：

- `FG_BUCKETIZE` 表示特征分桶是在**训练时动态进行的**
- 但方案声称"保持 pre-encoded pipeline 不变"
- 这两者是**矛盾的**：pre-encoded pipeline 意味着特征已经在 ODPS 阶段完成了分桶和编码，训练时不应该再做 bucketize
- 如果 `fg_mode: FG_BUCKETIZE` 在 pre-encoded pipeline 中生效，可能会导致**训练时和推理时的特征编码不一致**——训练时重新分桶，推理时使用预编码的特征

**建议**：

- 确认 `fg_mode: FG_BUCKETIZE` 在 pre-encoded pipeline 中的实际行为
- 如果特征是 pre-encoded 的，应该使用 `fg_mode: FG_NONE` 或 `FG_LOOKUP`
- 否则，需要确保线上推理时也使用相同的分桶策略

### 🔴 新问题4：Combo Feature 的 ZCH 配置覆盖了 13/44 个 combo features，但其余 31 个 combo features 没有 ZCH

**分析**：

- 有 ZCH 的 13 个 combo features 全部是**高价值组合**（login_city、gender、dev_brand 与 spu_id、username 等的组合）
- 没有 ZCH 的 31 个 combo features 中，很多也是**有价值的组合**（如 gender_x_brand、dev_brand_x_cate_id_path 等）
- 为什么设计者只给 13 个 combo features 加了 ZCH？可能是因为这 13 个的**理论组合数最大**，需要 ZCH 来控制内存
- 但这也意味着**其余 31 个 combo features 的 embedding 是全量加载的**，如果它们的理论组合数也很大，可能会占用大量内存

**建议**：

- 统计 31 个无 ZCH combo features 的理论组合数
- 如果某个 combo feature 的理论组合数 > 1M，考虑为其添加 ZCH
- 或者，使用 hash embedding 替代 lookup table

### 🔴 新问题5：模型使用了 1 epoch 训练，但 ZCH 需要足够的训练轮次才能稳定

**配置**：

```protobuf
train_config {
  num_epochs: 1
}
```

**分析**：

- ZCH 的核心机制是：在训练过程中动态更新 embedding，通过 eviction policy 淘汰冷启动 embedding
- 如果只训练 1 epoch，ZCH embedding 的更新次数非常有限
- 对于一个 zch_size=13.7M 的特征，在 1 epoch 内可能只能覆盖一小部分 slot
- 这意味着**大部分 ZCH embedding 始终是随机初始化的**，eviction policy 的差异对这部分的收益微乎其微

**建议**：

- 如果只做 1 epoch 实验，ZCH 差异化策略的效果可能不明显
- 考虑增加训练 epoch 数（如 3-5 epochs），让 ZCH embedding 有更充分的更新机会
- 或者，在 1 epoch 内使用更大的 batch_size，增加 ZCH 的覆盖范围

______________________________________________________________________

## 三、修正后的优化优先级（重审版）

| 优化项                          | 上一版优先级 | 重审后优先级 | 修正理由                                                          |
| ------------------------------- | ------------ | ------------ | ----------------------------------------------------------------- |
| CDOT 扩容                       | P0↑          | **P2**       | CDOT 不是瓶颈，domain group 原始 embedding 已完整传入             |
| ZCH 差异化                      | P1           | **P1**       | 方向正确，但 1 epoch 训练可能无法体现效果                         |
| item_id ZCH 化                  | P0           | **P3**       | item_id 全量加载 384MB 可接受，且需要全局一致性                   |
| Sequence 时间衰减               | P1           | **P3**       | DIN attention 已隐含相关性加权，时间衰减是可选增强                |
| Search Weight 全局化            | P1           | **P3**       | 当前设计符合业务逻辑，CVR 需要 search_weight 校正偏差             |
| PLE Expert 扩容                 | P2           | **P3**       | 瓶颈在 gate 质量而非 expert 数量                                  |
| CDOT compress_hidden_units 审查 | **NEW**      | **P1**       | [512, 374] 设计可疑，需要验证是否经过超参搜索                     |
| PPNet/Tower 结构一致性          | **NEW**      | **P2**       | PPNet 和 Tower 使用相同结构，可能限制 task-specific 表达          |
| FG_BUCKETIZE 兼容性             | **NEW**      | **P0**       | pre-encoded pipeline 与 FG_BUCKETIZE 矛盾，可能导致线上推理不一致 |
| 无 ZCH combo features 审查      | **NEW**      | **P2**       | 31 个 combo features 无 ZCH，需要评估内存影响                     |
| 1 epoch 训练与 ZCH 兼容性       | **NEW**      | **P1**       | 1 epoch 可能不足以让 ZCH 差异化策略生效                           |

______________________________________________________________________

## 四、重审结论

**上一版审核评分**：4/10

**上一版审核的主要问题**：

1. **过度自信于"CDOT 瓶颈"叙事**，忽略了 CDOT 的 additional 信息特性
1. **提出了多个看似合理但实际站不住脚的"新问题"**（item_id ZCH、时间衰减、search weight 公平性）
1. **缺乏定量分析**（如 PLE expert 数量、ZCH 内存占用）
1. **发现了真正重要的新问题**（FG_BUCKETIZE 兼容性、CDOT compress_hidden_units 设计），但这些被大量噪音掩盖

**核心修正**：

1. **CDOT 扩容的优先级从 P0 下调到 P2**——它不是瓶颈
1. **FG_BUCKETIZE 兼容性从"未发现"提升到 P0**——这是最可能引起线上事故的问题
1. **新增"CDOT compress_hidden_units [512, 374] 设计可疑"**——需要验证超参搜索过程
1. **新增"1 epoch 训练与 ZCH 差异化策略的兼容性"**——1 epoch 可能不足以体现 ZCH 差异化的效果

**一句话总结**：上一版审核提出了大量看似深刻但实际站不住脚的"优化建议"，掩盖了真正关键的问题（FG_BUCKETIZE 兼容性、CDOT 超参设计）。建议优先解决 P0 级别的配置一致性问题，再考虑 P1/P2 的优化实验。
