# TorchEasyRec 实验记录 (2026-07)

> 每次关键结论更新在此文件。**冲突时以最新结论为准。**

______________________________________________________________________

## 基线信息

**v15 Baseline:** `home_flow_2604_v15_baseline.config` · CTR AUC=0.7165 · CVR AUC=0.7473 · CVR稀疏度=0.5
**Loss:** `use_ctcvr_loss=true`，CVR+CTR logits 权重 4.5 (最优)
**环境:** 31GB GPU, +30% 延迟预算, `num_epochs: 1` (多 epoch 过拟合)
**线上经验:** `ots=0`(最佳) · `cvr_add_ctr_logits=false`(已推全) · `cvr_direct/cvr_shortcut`(负向下线) · PLE扩容/CVR塔加深(离线不如基线)

______________________________________________________________________

## 2026-07-21 | 实验 1: PCGrad Strict vs Approximate 一 Epoch 对比

**Recommendation: ✅ Approximate 优于 Strict**

| 指标       | Approximate | Strict    | Winner    |
| :--------- | :---------- | :-------- | :-------- |
| AUC_ctr    | **0.715**   | 0.694     | **+3.0%** |
| AUC_cvr    | **0.754**   | 0.739     | **+3.4%** |
| total_loss | 3.007       | **2.846** | Strict    |
| BCE_ctr    | 2.687       | **2.579** | Strict    |

- Approx: bs=4096, per-task `autograd.grad()` + loss-weighting modulation
- Strict: bs=3072, backward hook + true gradient projection (OOM 降 batch)

**核心结论：** Loss 低 ≠ AUC 高。Strict 投影掉的梯度分量包含排序判别信号（如 CTR 单调调高能力），牺牲判别力换优化稳定性，两任务收益不均。Approximate 间接缓解冲突不修改梯度方向，维持分类/排序能力。

**决策：** 继续使用 approx 方案 (`pcgrad.config`, bs=4096)。

______________________________________________________________________

## 2026-07-22 | 实验 2: HoME Phase 1 — Expert Normalization + Swish

**Recommendation: ⚠️ 方向正确但效应量极小，需评估 ROI**

| Metric       | Baseline    | Phase 1     |       Δ       |
| :----------- | :---------- | :---------- | :-----------: |
| `total_loss` | 2.914       | 2.909       | **−0.17%** ✓  |
| **AUC_ctr**  | **0.71522** | **0.71533** | **+0.02pp** ✓ |
| **AUC_cvr**  | **0.75433** | **0.75450** | **+0.02pp** ✓ |
| speed        | 1.59 it/s   | 1.57 it/s   |     −1.3%     |

Config: `expert_normalization: true`, ReLU → Swish (4处), GroupNorm(num_groups=2)

- **Swish alone 增益本就很小** — 同类微调 ΔAUC 通常在 0~0.5pp，0.02pp 处于下限
- **2-task 场景 Expert Collapse 不严重** — CTR+CVR 只有两个任务时 Gate 天然分配不同方向
- **GroupNorm(2 groups) 硬编码可能约束过强** — expert_dim=128/256 时过度压缩表达能力，后续可尝试 `num_groups=expert_num`
- 如 epoch 1~3 AUC 仍 < +0.1pp，回归 ReLU

______________________________________________________________________

## 2026-07-23 | 实验 3: APPNet-AFP — 自动特征分区 (bit_wise 模式)

**Recommendation: ✅ 已推全，全部线上正向**

Config: `home_flow_2604_v15_afp.config` (shared AFP, bit_wise, hidden=[128,64], temp=1.0→0.1, entropy_reg=0.05)

| 指标         | Δ vs Baseline |
| :----------- | :------------ |
| UV_CTR       | **+1.94%** ✓  |
| 人均曝光点击 | **+5.83%** ✓  |
| PV_CTR       | **+5.5%** ✓   |
| UV_CVR       | **+3.4%** ✓   |
| PV_CVR       | **+4.5%** ✓   |
| 2~7 留存     | **+0.62%** ✓  |
| 折扣下单率   | **+1.72%** ✓  |

- **UV_CTR +1.94% vs 人均曝光点击 +5.83%** → AFP 改善了推荐多样性，用户发现更多可点击内容
- **2~7 留存 +0.62%** → 长期指标正向，非短期过拟合
- **UV_CVR +3.4%** → 在 0.5 稀疏度下稳健提升
- AFP 参数量 1.17M（vs feature_wise 72K，16x 差异），仍在 +30% 延迟预算内

**Bug fix 记录（已修复，不再复现）：**

- `self._afp_module` 拼写错误 → `self.afp_module`（shared AFP 模式崩溃）
- `entropy.item()` 在 FX tracing 时触发 Proxy TraceError → 加 `_is_fx_proxy` guard
- entropy_reg 只取第一个 task → 改为对所有 task AFP 求和

______________________________________________________________________

## 线上 AB 经验总结

| 改动                       | CTR        | CVR       | 长期       | 结论          |
| :------------------------- | :--------- | :-------- | :--------- | :------------ |
| `cvr_add_ctr_logits=false` | 正向       | 正向      | —          | ✅ 已推全     |
| `cvr_direct`               | 负向       | 负向      | —          | ❌ 下线       |
| `cvr_shortcut`             | 负向       | 负向      | —          | ❌ 下线       |
| PCGrad Strict              | −3.0%      | −1.1%     | —          | ❌ 不采用     |
| PCGrad Approximate         | 持平       | +0.9%     | —          | ✅ 生产       |
| HoME Phase 1 (Swish+Norm)  | +0.02pp    | +0.02pp   | —          | ⚠️ 待验证     |
| **APPNet-AFP (bit_wise)**  | **+1.94%** | **+3.4%** | **+0.62%** | ✅ **已推全** |

______________________________________________________________________

## 增量实验 (TODO)

- [ ] Per-task AFP vs Shared AFP 对比实验（离线 AUC + 线上 AB）
- [ ] HoME Phase 1: `num_groups=expert_num` 替代硬编码 `num_groups=2`
- [ ] GradClip + PCGrad Approx 组合探索

______________________________________________________________________

*最后更新: 2026-07-23*
