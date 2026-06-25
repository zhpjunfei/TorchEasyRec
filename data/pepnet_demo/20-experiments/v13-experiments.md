______________________________________________________________________

## date: 2026-06-25 tags: [experiment, v13, pcgrad, gradient-surgery] related: ["[v12-experiments]"]

# v13 实验 — PCGrad 梯度手术

> 基于 v12 结论（CTR=4.5 为最优静态权重），验证 PCGrad 梯度手术能否进一步提升。思路：CVR 梯度与 CTR 冲突时移除冲突分量，保护共享表示。配置：PCGrad + CTR=4.5。

## 实验

| 实验 | Config | 变化 |
| :--- | :----- | :--- |
| pcgrad_ctr45 | `v13/home_flow_2604_v13_pcgrad_ctr45.config` | CTR=4.5, `use_pcgrad: true` |

## 实验结果

| 实验 | auc_ctr | Δauc_ctr | bce_ctr | auc_cvr | Δauc_cvr | bce_cvr |
| :--- | :------ | :------- | :------ | :------ | :------- | :------ |
| baseline (v12, CTR=3.3) | 0.716316 | — | 1.933748 | 0.757583 | — | 0.493283 |
| ctr45 (v12, CTR=4.5) | 0.717057 | **+0.10%** | 2.634723 | 0.757881 | **+0.04%** | 0.493627 |
| pcgrad_ctr45 | 0.716778 | +0.06% | 2.635201 | 0.757290 | −0.04% | 0.493876 |

## 分析

### PCGrad 未带来额外收益

pcgrad_ctr45 双方 AUC 均低于纯 ctr45：
- Δauc_ctr: +0.06% vs +0.10%（差 0.04%）
- Δauc_cvr: −0.04% vs +0.04%（差 0.08%）

差异处于评估噪声水平（SE≈0.00086），但方向一致偏负，不构成正向信号。

### 为什么不 Work

PCGrad 设计用于梯度量级接近的多任务场景。在 CTR=4.5 的权重下：

```
||g_ctr||  ≈ 4.5 × ||g_cvr||₀
```

其中 `||g_cvr||₀` 为 CVR 的原始梯度范数。PCGrad 的投影操作：

```
proj_{g_cvr}(g_ctr) = (g_ctr · g_cvr) / ||g_cvr||² · g_cvr
proj_{g_ctr}(g_cvr) = (g_ctr · g_cvr) / ||g_ctr||² · g_ctr
```

- 大梯度 g_ctr 投影到小梯度 g_cvr 上：系数 `(g_ctr · g_cvr) / ||g_cvr||²` 很大 → 但作用在 g_cvr 上，g_cvr 本来就小，修改量也小。
- 小梯度 g_cvr 投影到大梯度 g_ctr 上：系数 `(g_ctr · g_cvr) / ||g_ctr||²` 很小 → 对 g_ctr 的修改微乎其微。

结果：PCGrad 在 4.5x 不平衡下几乎失能，偶尔触发反而可能移除 CVR 中有用的非冲突信号。

### 与早期 step 1000 的矛盾

step 1000 时 PCGrad 显示 BCE_ctr 显著更低（−0.18），但 step 7757 最终无收益。说明：
- 在训练极早期（LR 刚升到峰值），参数随机初始化，梯度冲突比例高 → PCGrad 清理冲突有短期好处
- 但随着训练进行，模型趋于稳定，冲突比例下降 → PCGrad 的干预从"有益"变为"无影响"

## 结论

1. **PCGrad 未提升 ctr45** — 在 4.5x 梯度不平衡下 PCGrad 基本失能。

2. **CTR=4.5 仍是 v12~v13 最优配置** — PCGrad、PE-MTL、UncertaintyWeight 三种自适应方案均未超过简单静态权重调优。

3. **Loss/梯度层面的优化到此为止** — 已验证 12+ 个实验（权重扫描、UW、PE-MTL、PCGrad），唯一正向信号来自 CTR 静态提权至 4.5。CVR 提升的根本瓶颈不在梯度/损失层面的精细调整，在训练信号量本身。
