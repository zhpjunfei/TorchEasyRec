# TorchEasyRec 实验记录 (2026-07)

> 每次关键结论更新在此文件。**冲突时以最新结论为准。**

______________________________________________________________________

## 基线信息

**v15 Baseline:** home_flow_2604_v15_baseline.config · CTR AUC=0.7165 · CVR AUC=0.7473 · CVR稀疏度=0.5
**Loss:** use_ctcvr_loss=true，CVR+CTR logits 权重 4.5 (最优)
**环境:** 31GB GPU, +30% 延迟预算, num_epochs: 1 (多 epoch 过拟合)
**线上经验:** ots=0(最佳) · cvr_add_ctr_logits=false(已推全) · cvr_direct/cvr_shortcut(负向下线) · PLE扩容/CVR塔加深(离线不如基线)

**V17 Production Baseline:** home_flow_2604_v17_baseline.config = expert_normalization: true + Swish（基于 AFP feature_wise 升级）

______________________________________________________________________

## 2026-07-21 | 实验 1: PCGrad Strict vs Approximate 一 Epoch 对比

**Recommendation: ✅ Approximate 优于 Strict**

| 指标       | Approximate | Strict    | Winner    |
| :--------- | :---------- | :-------- | :-------- |
| AUC_ctr    | **0.715**   | 0.694     | **+3.0%** |
| AUC_cvr    | **0.754**   | 0.739     | **+3.4%** |
| total_loss | 3.007       | **2.846** | Strict    |
| BCE_ctr    | 2.687       | **2.579** | Strict    |

- Approx: bs=4096, per-task autograd.grad() + loss-weighting modulation
- Strict: bs=3072, backward hook + true gradient projection (OOM 降 batch)

**核心结论：** Loss 低 ≠ AUC 高。Strict 投影掉的梯度分量包含排序判别信号（如 CTR 单调调高能力），牺牲判别力换优化稳定性，两任务收益不均。Approximate 间接缓解冲突不修改梯度方向，维持分类/排序能力。

**决策：** 继续使用 approx 方案 (pcgrad.config, bs=4096)。

______________________________________________________________________

## 2026-07-22 | 实验 2: HoME Phase 1 — Expert Normalization + Swish

**Recommendation: ⚠️ 方向正确但效应量极小 (ΔAUC=+0.02pp)**

| Metric     | Baseline  | Phase 1   |     Δ     |
| :--------- | :-------- | :-------- | :-------: |
| total_loss | 2.914     | 2.909     | −0.17% ✓  |
| AUC_ctr    | 0.71522   | 0.71533   | +0.02pp ✓ |
| AUC_cvr    | 0.75433   | 0.75450   | +0.02pp ✓ |
| speed      | 1.59 it/s | 1.57 it/s |   −1.3%   |

Config: expert_normalization: true, ReLU → Swish (4处), GroupNorm(num_groups=2)

- **Swish alone 增益本就很小** — 同类微调 ΔAUC 通常在 0~0.5pp，0.02pp 处于下限
- **2-task 场景 Expert Collapse 不严重** — CTR+CVR 只有两个任务时 Gate 天然分配不同方向
- **GroupNorm(2 groups) 硬编码可能约束过强** — expert_dim=128/256 时过度压缩表达能力
- 如 epoch 1~3 AUC 仍 < +0.1pp，回归 ReLU

## 2026-07-23 | 实验 5: Phase 1 (Swish+Norm) vs AFP Baseline 一 Epoch 对比

**Recommendation: ✅ AFP baseline 已推全为最优配置, Phase 1 未提供可测量的增益**

| 指标            | AFP Baseline | Phase 1 (Swish+Norm) |       Δ |
| :-------------- | :----------: | :------------------: | ------: |
| CTR AUC         |   0.70980    |       0.71031        | +0.05pp |
| CVR AUC         |   0.75312    |       0.75364        | +0.05pp |
| BCE_ctr         |   2.66421    |       2.66548        |  +0.05% |
| BCE_ctcvr       |   0.31602    |       0.31457        |  −0.46% |
| Total Loss      |   2.98086    |       2.98060        |  −0.01% |
| afp_entropy_reg |   0.00063    |       0.00055        |  −12.7% |

环境: bs=4096, step=7300, lr=0.0001(全部 optimizer group), same data split

**核心结论：** Phase 1 在 AFP baseline 上只提升了 +0.05pp (CTR/CVR)，此量级处于噪声范围。loss 差异极小 (−0.01%)，entropy_reg 反而降低，说明 Swish 对 expert 的 partition 没有实质性改善。

**决策（已更新）：** Phase 1 (Swish+GroupNorm) 在 AFP 推全后不再单独评估——AFP 本身已经通过特征分区解决了专家分化问题。**虽然离线 ΔAUC 仅在噪声区间，但后续线上 AB 中 exp2(phase1) Swish+专家 norm 全面正向（PV_CTR +1.8%、UV_CVR +1.58% 均显著），已作为 V17 baseline 推全，未回退 ReLU。**

## 2026-07-23 | 实验 3: APPNet-AFP Shared (feature_wise) — 线上推全

**Recommendation: ✅ 全部正向，已推全，SOTA 方案**

Config: home_flow_2604_v15_afp.config (shared AFP, feature_wise, hidden=[64,32], temp=1.0→0.1, entropy_reg=0.05)

| 指标         | Δ vs Baseline |
| :----------- | :------------ |
| UV_CTR       | +1.94% ✓      |
| 人均曝光点击 | +5.83% ✓      |
| PV_CTR       | +5.5% ✓       |
| UV_CVR       | +3.4% ✓       |
| PV_CVR       | +4.5% ✓       |
| 2~7 留存     | +0.62% ✓      |
| 折扣下单率   | +1.72% ✓      |

- UV_CTR +1.94% vs 人均曝光点击 +5.83% → 改善了推荐多样性（探索-利用平衡）
- 2~7 留存 +0.62% → 长期指标正向，非短期过拟合
- AF P参数量 ~75K（vs bit_wise 1.17M），轻量且高效

**Bug fix 记录（已修复）：** self.\_afp_module → self.afp_module · entropy.item() FX tracing guard · entropy_reg 多 task 求和

## 2026-07-23 | 实验 4: APPNet-AFP Task-wise (feature_wise) — 线上 AB

**Recommendation: ⚠️ 各指标均低于 shared，不推全**

Config: home_flow_2604_v15_afp_taskwise.config (per-task AFP, feature_wise, hidden=[64,32], exp_temp_decay=true)

| 指标         | Shared AFP       | Task-wise AFP    | Winner    |
| :----------- | :--------------- | :--------------- | :-------- |
| UV_CTR       | +1.94%           | +1.87%           | Shared    |
| UV_CVR       | +3.39%           | +2.78%           | Shared    |
| 折扣下单率   | +1.72% (p=0.325) | +3.36% (p=0.055) | Task-wise |
| 人均曝光点击 | +5.83%           | +6.54%           | Task-wise |
| 均值点击天数 | +0.62% (p=0.48)  | +0.67% (p=0.43)  | —         |
| 应用启动天数 | −0.02% (p=0.97)  | −0.13% (p=0.85)  | —         |

**分析：**

- task_wise 在 UV_CTR 上与 shared 持平（+1.87 vs +1.94），但 UV_CVR 少了 0.6pp（p=0.001 显著）
- 唯一的亮点是折扣下单率接近显著边界（p=0.055），暗示 task-specific partition 可能筛选了更高价值的用户
- 结论：task_wise 不是"负向"而是"有 trade-off 的正向"，但在当前 KPI 下不如 shared

**决策：不推全 task_wise。** 0.6pp UV_CVR 损失无法被折扣下单率的弱信号补偿。

## 2026-07-28 | 实验 6: Home Phase 1 → V17 Baseline（expert_normalization + Swish）— 线上推全

**Recommendation: ✅ 已推全，SOTA 当前生产配置**

Config: home_flow_2604_v17_baseline.config = expert_normalization: true + Swish（v15_afp 基线升级）

**实际推全策略：exp2 (Phase 1) = Swish + expert_normalization**

| 指标类型     | 变化幅度 | 显著性 |
| :----------- | :------- | :----- |
| PV_CTR       | +1.8%    | ✓ 显著 |
| UV_CVR       | +1.58%   | ✓ 显著 |
| UV_CTR       | +0.76%   | —      |
| 人均曝光点击 | +4.48%   | ✓ 显著 |
| 人均曝光次数 | +3.11%   | ✓ 显著 |
| 折扣下单率   | +3.69%   | ✓ 显著 |
| 曝光留存     | +1.48%   | ✓ 显著 |
| 点击留存     | +1.72%   | ✓ 显著 |

核心策略：在 AFP shared feature_wise（v15_afp）基础上 **开启 expert_normalization + PLE Swish 激活**（exp2/Phase 1 组合），形成 v17 baseline。All metric 线上全面正向，正式推全。

**决策：v17 baseline 为当前生产最优配置**，进入下一轮实验（GradClip + PCGrad Approx 组合）。

______________________________________________________________________

## 线上 AB 决策速查表

| 改动                      | CTR     | CVR     | 折扣下单 | 最终决策                   |
| :------------------------ | :------ | :------ | :------- | :------------------------- |
| cvr_add_ctr_logits=false  | 正向    | 正向    | —        | ✅ 已推全                  |
| cvr_direct                | 负向    | 负向    | —        | ❌ 下线                    |
| cvr_shortcut              | 负向    | 负向    | —        | ❌ 下线                    |
| PCGrad Strict             | −3.0%   | −1.1%   | —        | ❌ 不采用                  |
| PCGrad Approximate        | 持平    | +0.9%   | —        | ✅ 生产                    |
| HoME Phase 1 (Swish+Norm) | +0.02pp | +0.02pp | —        | ✅ 线上推全为 v17 baseline |
| APPNet-AFP Shared         | +1.94   | +3.4%   | +1.72%   | ✅ **已推全 → V17**        |
| APPNet-AFP Task-wise      | +1.87   | +2.78\* | +3.36%†  | ⚠️ **不推全**              |

\* p=0.001 显著降低 · † p=0.055 边缘显著

______________________________________________________________________

## 增量实验 (TODO)

- [x] HoME Phase 1 Swish+Norm — 线上确认为 v17 baseline，expert_normalization: true + Swish 正式投产
- [ ] GradClip + PCGrad Approx 组合探索
- [x] 温度校准 (CaliCausalRank) — offline CTCVR +15.4%，线上打分崩塌 2 个数量级（TemperatureScaler shift 失控），方向关闭
- [x] ots (out_task_space_weight) — 线上效果不如 ots=0，方向已放弃
- [x] chajia_click_seq 序列扩展 — 线上效果微幅
- [x] KV 特征剪枝 (VariationalDropout cluster top-2) — 容量非瓶颈，不能提升 UV 指标
- [ ] 延迟反馈修正 (Delayed Feedback) — 数据侧改动，唯一有空间的方向

*注: bit_wise AFP、per-task AFP、gradient balancing (MultiBalance/GradCraft/FDN) 经数据分析均已否决，理由见下方。*

______________________________________________________________________

## 决策记录：为什么不做更多 AFP variant

### bit_wise AFP — 否决

bit_wise 需要 136 个 bit-level classifiers（1.17M params），是 feature_wise (17 classifiers, ~75K) 的 16 倍参数量。Feature_wise 已在 17 个 domain features 上学到足够好的 partition 方向（UV_CTR +1.94%/CVR +3.4%），把单个 feature 拆成 136 个 bit 来分类在只有 2 个任务时是**精度过剩、效率不足**。

### Gradient balancing (MultiBalance/GradCraft/FDN) — 不建议在当前阶段引入

AFP 已经解决了特征层面的 partition 问题。Gradient balancing 解决的是更底层的优化冲突，但 Meta MultiBalance 和快手 GradCraft 都只提供了离线指标，**没有线上 AB 数据**。在没有线上证据前引入新方案是过度工程化。

### 当前状态

Shared AFP feature_wise 是全维度赢家（CTR/CVR/长期指标全部正向）。v17 baseline 在此基础上加入 expert_normalization: true + Swish，成为当前生产最优配置。不再增加复杂度。

______________________________________________________________________

______________________________________________________________________

## 2026-08-01 | 实验 7: V17 优化方向汇总与关闭

### 7.1 温度校准 (CaliCausalRank) — ❌ 关闭

**Config:** home_flow_2604_v17_calibration_d_fusion.config (T=1.5 + progressive ECE + cvr_only)

| 指标             | Baseline | Calib D | Δ          |
| ---------------- | -------- | ------- | ---------- |
| AUC_ctr          | 0.70792  | 0.70568 | **-0.32%** |
| AUC_cvr          | 0.75470  | 0.75977 | +0.67%     |
| BCE_ctcvr        | 0.31719  | 0.36618 | **+15.4%** |
| calibration_loss | —        | 0.12009 | bug 已修复 |

**线上事故：** 上线后打分下降 2 个数量级。根因：TemperatureScaler 的 `shift` 参数无上限 clamp，ECE loss 驱动 T 从 1.5 漂移失控，推理时 pCVR 方差塌缩 → CVR 塔失声 → 排序退化为 CTR 单目标。

**决策：** 关闭温度校准方向。卸载相关代码和 config。

### 7.2 ots (out_task_space_weight) — ❌ 放弃

线上 AB 效果不如 ots=0（ESMM），方向已放弃。

### 7.3 chajia_click_seq 序列扩展 — ⚠️ 微幅

线上效果微幅，不足以作为独立优化方向。

### 7.4 KV 特征剪枝 (VariationalDropout cluster top-2) — ⚠️ 不可行

基于 `home_flow_2604_v17_chajia_click_seq_importance.config` 的 VariationalDropout 特征重要性（`mean_drop_p` = dropout 概率，高=冗余）。按基础特征簇保留 top-2 最低 p 窗口，KV 特征 438 → 189（-57%）。

**Config:** home_flow_2604_v17_feature_prune.config

**结论：** 多轮实验已证模型容量不是瓶颈（PLE 扩容/塔加深/DCNv2/CDOT 全部证否）。特征剪枝只能持平或下降，不能提升 UV 指标。config 保留用于验证递补假设，但不应作为效果提升方向。

### 7.5 减法方向共识

优化 UV CTR/UV CVR 不能靠做减法（模型容量不瓶颈），也不能靠做加法（所有加法方向已证否）。当前架构和特征集合已接近天花板。

### 7.6 唯一有空间的方向：延迟反馈修正

**理论：** CVR 标签存在延迟（用户点击后 1-7 天才转化），训练时近期"未转化"样本中 5-15% 实际为正样本。模型学到的是"即时转化"而非"最终转化"，系统性低估 CVR。

**业界证据：** Criteo DFM (KDD 2019) CVR AUC +2-3%；阿里 ESDF 线上 GMV +3-5%。

**实现：** 数据管道改动（近期负样本不参与 CVR 训练或权重衰减），无需改模型/架构/config。

______________________________________________________________________

\*最后更新: 2026-08-01

### 7.7 辅助任务实验 — pending

**问题：** chajia_click_seq 序列扩展线上微幅，可能因为序列特征缺乏配套 label 的直接监督。

**新样本：** 2606 样本新增 5 个 label：is_favorite、is_like、is_search_click、is_search_conversion、is_chajia_click。

**标签语义澄清：**

- is_favorite / is_like：点击进入详情页后产生，在点击后空间定义，保留 task_space=is_click
- is_chajia_click：跨场景行为（查价场景），与 is_click 无嵌套关系，不加 task_space

**Config:** home_flow_2604_v17_aux_tasks.config

| 任务         | label           | weight | task_space | 对应序列                | tower MLP     |
| ------------ | --------------- | ------ | ---------- | ----------------------- | ------------- |
| ctr          | is_click        | 4.5    | —          | click_10/50_seq         | [512,256,128] |
| cvr          | is_conversion   | 1.0    | is_click   | conversion_5/20_seq     | [512,256,128] |
| favorite     | is_favorite     | 0.1    | is_click   | favorite_5/10_seq       | [256,128]     |
| like         | is_like         | 0.1    | is_click   | like_100/10_seq         | [256,128]     |
| chajia_click | is_chajia_click | 0.1    | — (全样本) | chajia_click_100/10_seq | [256,128]     |

PLE 从 2 任务→5 任务，gate 从 4 维→7 维 softmax。辅助 tower 用 [256,128] 小塔 + dropout 0.2 防过拟合。

**Loss 融合审查：**

- 初版 weight=0.3 批评性审查发现辅助任务 loss 贡献 21% 太高（走 v12 翻车路径），降为 0.1
- chajia_click 去掉 task_space_indicator（跨场景行为，不在点击空间内）
- favorite/like 保留 task_space=is_click（点击后行为）

**样本监控：** 训练循环中每个 log_step 输出 `[LABEL_DIST]` 日志 + TensorBoard `label_pos_rate/{name}` 标量。

**待验证：**

1. label 分布日志确认新 label 数据正常加载
1. 辅助任务 AUC 是否有效学习（favorite/like/chajia_click AUC > 0.5）
1. 主任务 AUC_ctr / AUC_cvr 是否回退（þv12 教训）
1. PLE gate entropy 是否退化（5 任务 gate 是否 collapse）

______________________________________________________________________

\*最后更新: 2026-08-02
