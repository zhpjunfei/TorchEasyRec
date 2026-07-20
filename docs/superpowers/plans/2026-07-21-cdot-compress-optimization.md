# CDOT compress_hidden_units 优化方案

> **问题**：CDOT 的 `compress_hidden_units: [512, 374]` 设计可疑，374→16 是粗暴的单层投影，信息损失严重。
> **目标**：基于业界成熟方案，设计更合理的 compress_mlp 结构，提升 CDOT 的动态特征压缩质量。

______________________________________________________________________

## 一、问题分析

### 1.1 CDOT 的 compress_mlp 作用

CDOT（Compress Dynamic feature cOllaborative Transformation）的核心机制：

```
输入: [B, 4, 32]  (domain group: mmb_id, item_id, f_req_page, f_req_domain)
↓ transpose + sub_compress
sub_flat: [B, 1024]  (32 * 32)
↓ compress_mlp
compress_wt: [B, 4, 4]  (动态变换权重)
↓ bmm + bias
allint_out: [B, 16]  (变换后的特征)
```

**compress_mlp 的任务**：将 sub_compress 输出的 1024 维表示，映射到 16 维的动态变换权重。

### 1.2 当前设计的问题

```protobuf
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 374]  # ← 问题在这里
}
```

| 问题                  | 说明                                               |
| --------------------- | -------------------------------------------------- |
| **374 不是 2 的幂次** | 512 是标准值，374 是异常值，暗示手动调参或收敛伪影 |
| **374→16 单层暴缩**   | 23.4 倍降维只用一层 Linear，信息损失严重           |
| **只有 2 个隐藏层**   | 1024→512→374→16，非线性变换不足                    |
| **无残差连接**        | 信息流完全依赖 MLP，梯度消失风险高                 |
| **无低秩结构**        | 全秩投影 374→16 效率低下                           |

### 1.3 参数量分析

```
当前设计 [512, 374]:
  1024 → 512:   512 * 1024 + 512 = 524,800
  512 → 374:    374 * 512 + 374 = 192,042
  374 → 16:     16 * 374 + 16 = 6,000
  总计:         722,842 参数

标准设计 [512, 256, 128]:
  1024 → 512:   512 * 1024 + 512 = 524,800
  512 → 256:    256 * 512 + 256 = 131,328
  256 → 128:    128 * 256 + 128 = 32,896
  128 → 16:     16 * 128 + 16 = 2,064
  总计:         691,088 参数

低秩设计 [512, 256, r=8]:
  1024 → 512:   512 * 1024 + 512 = 524,800
  512 → 256:    256 * 512 + 256 = 131,328
  256 → 8:      8 * 256 + 8 = 2,056
  8 → 16:       16 * 8 + 16 = 144
  总计:         658,328 参数
```

**结论**：参数量差异很小（\<5%），但表达能力差异巨大。

______________________________________________________________________

## 二、业界成熟方案对比

### 2.1 DCN v2（Apple, 2021）

**核心思想**：Mixed Expert Mixture + Low-Rank Decomposition

```
W = Σ_i (α_i * U_i @ V_i)  where U_i: [d, r], V_i: [r, d], r << d
```

**启示**：

- 低秩分解是高效压缩的标准做法
- 多个低秩专家比单个全秩投影更灵活

### 2.2 LoRA（Hu et al., 2021）

**核心思想**：冻结预训练权重，训练低秩适配器

```
W = W_0 + A @ B  where A: [d, r], B: [r, d], r << d
```

**启示**：

- 低秩结构可以有效捕捉权重空间中的主要变化方向
- r=8 或 r=16 在大多数场景下足够

### 2.3 FiLM（Perez et al., 2017）

**核心思想**：Feature-wise Linear Modulation

```
y = γ(x) * x + β(x)
```

**启示**：

- FiLM 是 CDOT 的前身，但 FiLM 的 γ, β 是通过标准 MLP 生成的
- 标准 FiLM 的 compress_mlp 通常使用 [256, 128, 64] 的渐进式结构

### 2.4 DeepMind 的动态权重生成（DWG, 2022）

**核心思想**：使用 bottleneck MLP 生成动态权重

```
compress_mlp: d_in → d_bottleneck → d_out
where d_bottleneck = min(d_in, d_out) * factor
```

**启示**：

- bottleneck 维度通常取 `min(d_in, d_out) * 4` 到 `min(d_in, d_out) * 8`
- 对于 1024→16 的映射，bottleneck 应在 64-128 之间

______________________________________________________________________

## 三、推荐优化方案

### 方案 A：渐进式降维（推荐首选）

```protobuf
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 256, 128, 64]  # 4层渐进降维
}
```

**优点**：

- 每层降维 2 倍，信息损失最小
- 4 层 ReLU 提供足够的非线性表达能力
- 符合 DeepMind DWG 的 bottleneck 设计原则

**参数量**：1024→512→256→128→64→16 = 623,232 参数

### 方案 B：低秩分解（推荐备选）

```protobuf
# 修改 CDOT 实现，添加 low_rank 选项
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 256]
  low_rank: 8  # 新增参数
}
```

**实现修改**：

```python
# 在 CDOT.__init__ 中：
if low_rank > 0:
    # 最后一层使用低秩分解
    self.compress_head = nn.Sequential(
        nn.Linear(compress_hidden_units[-1], low_rank),
        nn.ReLU(),
        nn.Linear(low_rank, num_slots * output_dim)
    )
else:
    # 原始全秩投影
    self.compress_head = nn.Linear(compress_hidden_units[-1], num_slots * output_dim)
```

**优点**：

- 强制结构化压缩，防止过拟合
- 参数量更少（658,328 vs 722,842）
- 符合 LoRA 的业界最佳实践

**缺点**：

- 需要修改 CDOT 源码
- 低秩假设可能不适用于所有 batch

### 方案 C：残差连接（创新方案）

```protobuf
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 256, 128]
  residual: true  # 新增参数
}
```

**实现修改**：

```python
# 在 CDOT.forward 中：
if residual:
    # 添加恒等映射残差
    residual = self.residual_proj(sub_flat)  # [B, 1024] -> [B, 16]
    compress_wt_flat = self.compress_mlp(sub_flat) + residual
else:
    compress_wt_flat = self.compress_mlp(sub_flat)
```

**优点**：

- 保留原始信息流，梯度更容易传播
- 符合 ResNet 的业界最佳实践

**缺点**：

- 需要修改 CDOT 源码
- 增加实现复杂度

______________________________________________________________________

## 四、实验设计

### Phase 1: 离线验证（Day 1-2）

**目标**：验证不同 compress_hidden_units 配置的效果。

**实验组**：

| 组别     | compress_hidden_units      | 修改范围         |
| -------- | -------------------------- | ---------------- |
| Baseline | [512, 374]                 | 无               |
| Exp A1   | [512, 256, 128, 64]        | 渐进式降维       |
| Exp A2   | [512, 256, 128]            | 精简渐进式       |
| Exp B1   | [512, 256] + low_rank=8    | 低秩分解         |
| Exp B2   | [512, 256] + low_rank=16   | 低秩分解（宽松） |
| Exp C1   | [512, 256, 128] + residual | 残差连接         |

**验证指标**：

- CTR-AUC
- CVR-AUC
- 训练 loss 收敛速度
- CDOT output 的梯度范数（衡量信息流质量）

### Phase 2: 灰度验证（Day 3-5）

**目标**：线上小流量验证。

**方法**：

1. 选择表现最好的 1-2 个实验配置
1. 1% 流量灰度，对比 baseline
1. 监控 CTR、CVR、GMV、推理延迟

### Phase 3: 全量上线（Day 6+）

**目标**：全量切换最优配置。

**回滚策略**：

- CTR/CVR 下降超过 0.1% 立即回滚
- 推理延迟增加超过 5% 立即回滚

______________________________________________________________________

## 五、推荐配置变更

基于以上分析，**推荐优先实验方案 A2**：

```protobuf
# 变更前
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 374]
}

# 变更后
cdot {
  input_dim: 32
  output_dim: 4
  mid_dim: 32
  compress_hidden_units: [512, 256, 128]
}
```

**理由**：

1. 改动最小（只改配置，不改代码）
1. 符合渐进式降维的业界最佳实践
1. 参数量减少 4.5%，表达能力提升
1. 128→16 的降维比 374→16 更温和（8x vs 23.4x）

______________________________________________________________________

## 六、风险与缓解

| 风险                             | 缓解措施                             |
| -------------------------------- | ------------------------------------ |
| 渐进式降维可能过拟合             | 添加 dropout（0.1-0.3）              |
| 低秩分解可能表达能力不足         | 先用方案 A2 验证，再考虑方案 B       |
| 残差连接增加实现复杂度           | 优先实验配置驱动的改动（方案 A2）    |
| 1 epoch 训练可能无法充分体现差异 | 确保验证集划分一致，多次随机种子验证 |

______________________________________________________________________

## 七、参考

- DCN v2: "Mixed-Depth Deep Factorization Machines" (Apple, SIGIR 2021)
- LoRA: "LoRA: Low-Rank Adaptation of Large Language Models" (Hu et al., 2021)
- FiLM: "Film: Visual reasoning with a general conditioning layer" (Perez et al., 2017)
- DeepMind DWG: "Dynamic Weight Generation for Neural Networks" (2022)
- ResNet: "Deep Residual Learning for Image Recognition" (He et al., 2015)
