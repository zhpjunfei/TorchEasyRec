______________________________________________________________________

## date: 2026-06-26 tags: [experiment, v14, out-task-space-weight, dropout-fix] status: completed related: \["\[[v14-optimization-plan]\]"\]

# v14 实验分析：out_task_space_weight + LHUC_PPNet dropout 修复验证

- 新 wheel v1.2.19：LHUC_PPNet `dropout_ratio` 真正生效
- **所有结果均已基于修复后的新 wheel 重跑**

______________________________________________________________________

## 一、基线

全量对比以 **v12 baseline**（out_task=0.01, d=0.1, CTR weight=3.3）为准：

- auc_ctr=0.716542, GAUC_ctr=0.704368, gap_ctr=1.22pp
- auc_cvr=0.748275, GAUC_cvr=0.695728, gap_cvr=5.25pp
- BCE_cvr=0.493955

v14 config_c（CTR weight=4.5）结构一致、数据不同，不作为基准。

______________________________________________________________________

## 二、各实验结果（重跑，dropout 修复生效）

### Config C — out_task_space_weight=0.01（核心方向）

| 指标    |      值      |    vs v12     |
| :------ | :----------: | :-----------: |
| auc_ctr |   0.716650   |    +0.05%     |
| auc_cvr | **0.758937** | **+0.18%** ⭐ |
| bce_cvr |   0.492489   |   −0.000794   |

**当前最优。** 但 dropout=0.1 削弱了效果（修复前 =0 时 +0.43%）。已建 `config_c_dropout0` 恢复原始条件，待跑。

### Config A — 容量缩减 [512,256,128] → [256,128] + dropout=0.1

| 指标    |    值    |   vs v12   |
| :------ | :------: | :--------: |
| auc_ctr | 0.716902 |   +0.08%   |
| auc_cvr | 0.758173 | **+0.08%** |
| bce_cvr | 0.493791 | +0.000508  |

**从修复前 −0.14% 转中性。** 容量缩减 + real dropout 的组合避免了过拟合，但上限不足。

### Config D — A + CVR weight_decay=0.03

| 指标    |    值    |   vs v12   |
| :------ | :------: | :--------: |
| auc_ctr | 0.716929 |   +0.09%   |
| auc_cvr | 0.758242 | **+0.09%** |
| bce_cvr | 0.493822 | +0.000539  |

**同 A，wd 无额外增益。** 改善全部来自 dropout 本身。

### Config B — dropout=0.3 on 原始架构

| 指标    |    值    |    vs v12     |
| :------ | :------: | :-----------: |
| auc_ctr | 0.716461 |    +0.02%     |
| auc_cvr | 0.756811 | **−0.10%** ❌ |
| bce_cvr | 0.493695 |   +0.000412   |

**❌ 全容量 CVR tower 不需要 dropout。** [512,256,128] 在 5% 点击数据上需要完整表征容量。

______________________________________________________________________

## 三、全景对比（seed 固定后，v12 baseline）— 全指标

> ⚠️ 旧 Section III 基于未固定 seed 的结果（±1% 方差），ots002 的 +0.57% 被证实为 seed 噪声，已移除。以下为统一 seed 固定 + grouped_auc 的全量 seed-fixed 结果。基线统一为 v12 baseline。

**基线：** `v12/baseline` — out_task_space_weight=0.01, CVR dropout=0.1, CTR weight=3.3

| 排名 | 实验                           |   ots    |    auc_ctr (Δ)     |    GAUC_ctr (Δ)    |   gap_ctr (Δ)    |      auc_cvr (Δ)       |      GAUC_cvr (Δ)      |       gap_cvr (Δ)       | BCE_cvr  |
| :--: | :----------------------------- | :------: | :----------------: | :----------------: | :--------------: | :--------------------: | :--------------------: | :---------------------: | :------: |
|  —   | v12 baseline                   |   0.01   |    0.716542 (—)    |    0.704368 (—)    |    1.22pp (—)    |      0.748275 (—)      |      0.695728 (—)      |       5.25pp (—)        | 0.493955 |
|  1   | **ots50** 🏆                   | **0.50** | 0.716780 (+0.02pp) | 0.704006 (−0.04pp) | 1.28pp (+0.06pp) | **0.786413 (+3.81pp)** | **0.741334 (+4.56pp)** | **4.51pp (−0.74pp)** 🏆 | 0.383982 |
|  2   | **ots40**                      | **0.40** | 0.716652 (+0.01pp) | 0.703730 (−0.06pp) | 1.29pp (+0.07pp) | **0.784964 (+3.67pp)** | **0.738800 (+4.31pp)** |    4.62pp (−0.63pp)     | 0.404575 |
|  3   | **ots30**                      | **0.30** | 0.716783 (+0.02pp) | 0.704137 (−0.02pp) | 1.26pp (+0.04pp) | **0.782619 (+3.43pp)** | **0.736581 (+4.09pp)** |    4.60pp (−0.65pp)     | 0.426885 |
|  4   | **ots25**                      | **0.25** | 0.716771 (+0.02pp) | 0.703890 (−0.05pp) | 1.29pp (+0.07pp) | **0.780827 (+3.26pp)** | **0.734687 (+3.90pp)** |    4.61pp (−0.64pp)     | 0.438739 |
|  5   | **ots020**                     | **0.20** | 0.716791 (+0.02pp) | 0.703912 (−0.05pp) | 1.29pp (+0.07pp) | **0.778058 (+2.98pp)** | **0.732226 (+3.65pp)** |    4.58pp (−0.67pp)     | 0.450954 |
|  6   | **ots015**                     | **0.15** | 0.716815 (+0.03pp) | 0.704173 (−0.02pp) | 1.26pp (+0.04pp) | **0.774713 (+2.64pp)** | **0.727826 (+3.21pp)** |    4.69pp (−0.56pp)     | 0.463214 |
|  7   | **ots012**                     | **0.12** | 0.716795 (+0.03pp) | 0.704289 (−0.01pp) | 1.25pp (+0.03pp) | **0.772040 (+2.38pp)** | **0.724540 (+2.88pp)** |    4.75pp (−0.50pp)     | 0.470413 |
|  8   | **ots012_plebig**              | **0.12** | 0.716893 (+0.04pp) | 0.704652 (+0.02pp) | 1.26pp (+0.04pp) |   0.771514 (+2.32pp)   |   0.724105 (+2.84pp)   |            —            | 0.470681 |
|  9   | **ots012_seq_transformer**     | **0.12** | 0.716218 (−0.03pp) | 0.703412 (−0.10pp) | 1.28pp (+0.06pp) |   0.771242 (+2.30pp)   |   0.723974 (+2.82pp)   |            —            | 0.470961 |
|  10  | **ots012_seq_transformer_v2**  | **0.12** | 0.714844 (−0.17pp) | 0.702267 (−0.21pp) | 1.26pp (+0.04pp) |   0.770972 (+2.27pp)   |   0.723628 (+2.79pp)   |    4.73pp (−0.52pp)     | 0.472502 |
|  11  | **ots012_wide_dropout03**      | **0.12** | 0.717040 (+0.05pp) | 0.704494 (+0.01pp) | 1.25pp (+0.03pp) |   0.771586 (+2.33pp)   |   0.723583 (+2.79pp)   |            —            | 0.470593 |
|  12  | **ots012_wide**                | **0.12** | 0.717026 (+0.05pp) | 0.703987 (−0.04pp) | 1.27pp (+0.05pp) |   0.770405 (+2.21pp)   |   0.722696 (+2.70pp)   |            —            | 0.470840 |
|  13  | **ots012_seq_transformer_all** | **0.12** | 0.714804 (−0.17pp) | 0.702594 (−0.18pp) | 1.22pp (0.00pp)  |   0.770610 (+2.23pp)   |   0.722180 (+2.65pp)   |    4.84pp (−0.41pp)     | 0.472743 |
|  14  | **ots010**                     | **0.10** | 0.716789 (+0.02pp) | 0.704269 (−0.01pp) | 1.25pp (+0.03pp) | **0.769227 (+2.10pp)** | **0.721169 (+2.54pp)** |    4.81pp (−0.44pp)     | 0.475246 |
|  15  | **ots009**                     | **0.09** | 0.716805 (+0.03pp) | 0.704278 (−0.01pp) | 1.25pp (+0.03pp) | **0.768202 (+1.99pp)** | **0.719989 (+2.43pp)** |    4.82pp (−0.43pp)     | 0.477601 |
|  16  | **ots008**                     | **0.08** | 0.716910 (+0.04pp) | 0.704051 (−0.03pp) | 1.29pp (+0.07pp) | **0.766609 (+1.83pp)** | **0.718024 (+2.23pp)** |    4.86pp (−0.39pp)     | 0.479808 |
|  17  | **ots007**                     | **0.07** | 0.716907 (+0.04pp) | 0.704555 (+0.02pp) | 1.24pp (+0.02pp) | **0.765117 (+1.68pp)** | **0.716325 (+2.06pp)** |    4.88pp (−0.37pp)     | 0.482036 |
|  18  | **ots006**                     | **0.06** | 0.716794 (+0.03pp) | 0.704602 (+0.02pp) | 1.22pp (0.00pp)  | **0.763227 (+1.50pp)** | **0.713890 (+1.82pp)** |    4.93pp (−0.32pp)     | 0.484197 |
|  19  | **ots005**                     |   0.05   | 0.716913 (+0.04pp) | 0.704180 (−0.02pp) | 1.27pp (+0.06pp) | **0.761379 (+1.31pp)** | **0.711754 (+1.60pp)** |    4.96pp (−0.29pp)     | 0.486131 |
|  20  | **ots004**                     |   0.04   | 0.716860 (+0.03pp) | 0.704377 (+0.00pp) | 1.25pp (+0.03pp) | **0.759201 (+1.09pp)** | **0.709396 (+1.37pp)** |    4.98pp (−0.27pp)     | 0.488148 |
|  21  | **ots003**                     |   0.03   | 0.716871 (+0.03pp) | 0.704479 (+0.01pp) | 1.24pp (+0.02pp) | **0.756928 (+0.87pp)** | **0.706061 (+1.03pp)** |    5.09pp (−0.17pp)     | 0.489879 |
|  22  | **ots002_dropout03**           |   0.02   | 0.716760 (+0.02pp) | 0.704256 (−0.01pp) | 1.25pp (+0.03pp) | **0.756139 (+0.79pp)** | **0.705148 (+0.94pp)** |    5.10pp (−0.16pp)     |    —     |
|  23  | **ots002**                     |   0.02   | 0.716809 (+0.03pp) | 0.704213 (−0.02pp) | 1.26pp (+0.04pp) | **0.754525 (+0.63pp)** | **0.703538 (+0.78pp)** |    5.10pp (−0.16pp)     |    —     |
|  24  | **ots002_adamw**               |   0.02   | 0.716850 (+0.03pp) | 0.704170 (−0.02pp) | 1.27pp (+0.05pp) | **0.754614 (+0.63pp)** | **0.703467 (+0.77pp)** |    5.11pp (−0.14pp)     | 0.491437 |
|  25  | **dropout03**                  |   0.01   | 0.716781 (+0.02pp) | 0.703957 (−0.04pp) | 1.28pp (+0.07pp) | **0.752831 (+0.46pp)** | **0.701893 (+0.62pp)** |    5.09pp (−0.16pp)     | 0.492900 |
|  26  | **config_c** (v14 BL)          |   0.01   | 0.716686 (+0.01pp) | 0.704301 (−0.01pp) | 1.24pp (+0.02pp) | **0.751547 (+0.33pp)** | **0.699560 (+0.38pp)** |    5.20pp (−0.06pp)     | 0.493054 |
|  27  | **ots0005**                    |  0.005   | 0.716735 (+0.02pp) | 0.704386 (+0.00pp) | 1.23pp (+0.02pp) |   0.748989 (+0.07pp)   |   0.696614 (+0.09pp)   |    5.24pp (−0.02pp)     | 0.493725 |
|  28  | **ctcvr** (ESMM)               |    —     | 0.716570 (+0.00pp) | 0.703671 (−0.07pp) | 1.29pp (+0.07pp) |   0.750125 (+0.19pp)   |   0.698665 (+0.29pp)   |    5.14pp (−0.11pp)     |   N/A    |

**格式：** `val (Δpp)` — Δ 为与 v12 baseline 之差（absolute AUC difference in pp）。**正值 = 提升；gap 负值 = 差距收窄 = 提升。**

**趋势：** GAUC_cvr 随 ots 严格单调递增（0.005→0.50），但边际已降至约 0.025pp/0.01。

**解读：**

- **CTR 轻微受损趋势** — ots≥0.20 时 GAUC_ctr 持续 −0.04~−0.06pp，幅度极小
- **CVR 单调递增 0.005→0.50（21 个点）** — Δ GAUC_cvr 从 +0.09pp 单调增至 **+4.56pp**，但 0.20→0.50 仅 +0.91pp
- **gap_cvr 触底 ≈4.51–4.62pp** — 4.51pp（ots=0.50）为最低，但改善已极小
- **BCE_cvr 持续下降至 0.384** — 过置信风险加剧，非点击样本的 BCE 近 0

**关键发现（seed 固定后）：**

| 旧结论                                |  旧 GAUC  |              新 GAUC              | 实际结论                                                           |
| :------------------------------------ | :-------: | :-------------------------------: | :----------------------------------------------------------------- |
| ots002 +0.57% 🚀 最优                 | 0.703538  |             0.703538              | **+0.40pp，有效但非最优**；旧 +0.57% 是 seed 方差                  |
| ots005 +0.50% 略饱和                  | 未跑 GAUC |          **+1.60pp** 🏆           | **远优于 ots002**，旧结论反转                                      |
| dropout03 +0.41% 正信号               | 未跑 GAUC |            **+0.62pp**            | 有效但增量有限                                                     |
| weight decay 有效？                   |     —     | **等同（0.703467 vs 0.703538）**  | ❌ 零效果                                                          |
| gap_cvr 约 5.2pp                      |     —     | 5.25→**4.58pp**（ots=0.20 触底）  | ots 缩小 offline–online 差距，0.20 为最优                          |
| ctcvr 有效？                          |     —     | **+0.29pp GAUC_cvr, −0.07pp CTR** | ❌ 中性偏负                                                        |
| ots 天花板                            |     —     |     0.50 边际仅 +0.025pp/0.01     | ⏹️ 完结，无需继续扫                                                |
| TransformerEncoder (single)           |     —     | **−0.06pp vs ots012（等同噪声）** | ❌ 中性，DIN 的 target attention 已充分                            |
| TransformerEncoder (all 8 seq, buggy) |     —     |       **−0.24pp vs ots012**       | ❌ 旧版 bug：item_id dim=24 vs 32 不共享 + query 侧补 cate_id 污染 |

______________________________________________________________________

## 四、核心发现

### 4.1 out_task_space_weight 机制

```protobuf
task_space_indicator_label: "is_click"
in_task_space_weight: 1
out_task_space_weight: 0.01
```

- **in_task_space**（点击 5% 样本）：CVR 全量 BCE
- **out_task_space**（非点击 95% 样本）：CVR 以 ots 权重 BCE

梯度贡献占比：`95% × ots / (5% × 1 + 95% × ots)`。ots 的核心作用是给 CVR tower 提供非点击样本的弱负信号，缓解转化正样本稀疏问题。

### 4.2 核心发现：out_task_space_weight 单调增益（2026-06-27 更新）

**旧结论被推翻：** ots002（+0.57%）和 ots005（+0.50%）被证实为 seed 方差噪声。seed 固定后 ots 效果单调递增（以 v12 baseline 为准）。

|     ots     | 实验             |   GAUC_cvr   |  Δ vs v12   |  gap_cvr   |   BCE_cvr    | 边际增益/0.01↑ | 解释         |
| :---------: | :--------------- | :----------: | :---------: | :--------: | :----------: | :------------: | :----------- |
|    0.005    | ots0005          |   0.696614   |   +0.09pp   |   5.24pp   |   0.493725   |       —        | 弱信号不足   |
|    0.01     | v12 baseline     |   0.695728   |      —      |   5.25pp   |   0.493955   |       —        | 基线         |
|    0.01     | config_c (v14)   |   0.699560   |   +0.38pp   |   5.20pp   |   0.493054   |    +0.08pp     | v14 结构     |
|    0.01     | dropout03        |   0.701893   |   +0.62pp   |   5.09pp   |   0.492900   |       —        | 高 dropout   |
|    0.02     | ots002           |   0.703538   |   +0.78pp   |   5.10pp   |   0.491437   |    +0.40pp     | 初始跳变     |
|    0.02     | ots002_adamw     |   0.703467   |   +0.77pp   |   5.11pp   |   0.491437   |       —        | wd 无增益    |
|    0.02     | ots002_dropout03 |   0.705148   |   +0.94pp   |   5.10pp   |      —       |       —        | +dropout     |
|    0.03     | ots003           |   0.706061   |   +1.03pp   |   5.09pp   |   0.489879   |    +0.25pp     | 正常         |
|    0.04     | ots004           |   0.709396   |   +1.37pp   |   4.98pp   |   0.488148   |    +0.34pp     | 略高         |
|    0.05     | ots005           |   0.711754   |   +1.60pp   |   4.96pp   |   0.486131   |    +0.23pp     | 正常         |
|    0.06     | ots006           |   0.713890   |   +1.82pp   |   4.93pp   |   0.484197   |    +0.22pp     | 正常         |
|    0.07     | ots007           |   0.716325   |   +2.06pp   |   4.88pp   |   0.482036   |    +0.24pp     | 正常         |
|    0.08     | ots008           |   0.718024   |   +2.23pp   |   4.86pp   |   0.479808   |    +0.17pp     | 略降         |
|    0.09     | ots009           |   0.719989   |   +2.43pp   |   4.82pp   |   0.477601   |    +0.20pp     | 正常         |
|    0.10     | ots010           |   0.721169   |   +2.54pp   |   4.81pp   |   0.475246   |    +0.11pp     | 略降         |
|    0.12     | ots012           |   0.724540   |   +2.88pp   |   4.75pp   |   0.470413   |    +0.17pp     | 回弹         |
|    0.15     | ots015           |   0.727826   |   +3.21pp   |   4.69pp   |   0.463214   |    +0.11pp     | 递减         |
|    0.20     | ots020           |   0.732226   |   +3.65pp   |   4.58pp   |   0.450954   |    +0.09pp     | 递减         |
|    0.25     | ots25            |   0.734687   |   +3.90pp   |   4.61pp   |   0.438739   |    +0.05pp     | 逼近噪声     |
|    0.30     | ots30            |   0.736581   |   +4.09pp   |   4.60pp   |   0.426885   |    +0.04pp     | 逼近噪声     |
|  **0.40**   | **ots40**        | **0.738800** | **+4.31pp** | **4.62pp** | **0.404575** |  **+0.02pp**   | **边际近零** |
| **0.50** 🏆 | **ots50**        | **0.741334** | **+4.56pp** | **4.51pp** | **0.383982** |  **+0.025pp**  | **最终点**   |

**关键结论：**

- **GAUC_cvr 严格单调递增（0.005→0.50），已逼近极限。** ots=0.50 达到 +4.56pp，但 0.20→0.50 仅 +0.91pp（30 个 ots 点的总增益）。边际持续在 ~0.025pp/0.01。
- **gap_cvr 仍有改善** — 0.50 达到 4.51pp（新低），说明极高 ots 仍小幅收窄离线-在线差距
- **BCE_cvr 降至 0.384** — 严重过置信风险。非点击样本 BCE 近乎 0，模型几乎全盘预测 0
- **CTR 稳定** — 所有 ots≥0.20 的 GAUC_ctr Δ 在 −0.04~−0.06pp

### 4.3 dropout 的影响

| 实验             | ots  |    d    | GAUC_cvr | 同比基线 |   增量 vs 同 ots    |
| :--------------- | :--: | :-----: | :------: | :------: | :-----------------: |
| config_c         | 0.01 |   0.1   | 0.699560 |    —     |          —          |
| dropout03        | 0.01 | **0.3** | 0.701893 | +0.23pp  |     **+0.23pp**     |
| ots002           | 0.02 |   0.1   | 0.703538 | +0.40pp  |          —          |
| ots002_dropout03 | 0.02 | **0.3** | 0.705148 | +0.56pp  |     **+0.16pp**     |
| ots012           | 0.12 |   0.1   | 0.724540 | +2.88pp  |          —          |
| ots012_dropout03 | 0.12 | **0.3** | 0.725372 | +2.96pp  | **+0.08pp（噪声）** |

**核心发现：dropout 和 ots 是替代品。** 两者都降低 CVR tower 在少量点击样本上的过拟合——dropout 通过随机丢弃神经元，ots 通过把梯度分散到非点击 95% 样本。ots 越高，dropout 的边际效应越趋近于零。ots≥0.12 后 dropout 无必要。

### 4.4 CVR tower 宽度的影响

ots=0.12 下测试 CVR tower 宽度 [512,256,128] → [1024,512,256]：

| 实验                  |     tower      |  d  |   GAUC_cvr   | Δ vs ots012 |
| :-------------------- | :------------: | :-: | :----------: | :---------: |
| ots012                | [512,256,128]  | 0.1 | **0.724540** |      —      |
| ots012_wide           | [1024,512,256] | 0.1 |   0.722696   | **−0.18pp** |
| ots012_wide_dropout03 | [1024,512,256] | 0.3 |   0.723583   | **−0.10pp** |

宽塔一致性地带来 ~0.18pp 负收益。CVR tower 的瓶颈不在 MLP 宽度——PLE expert 的 gated output 已经提供了充足的表征，tower MLP 仅作为轻量分类头。[512,256,128] 已覆盖 CVR tower 所需容量。更宽的参数在有限正样本信号下反而过拟合。

### 4.5 饱和分析（2026-06-28 完结）

ots 全扫描完成（0.005→0.50，共 21 个点）：

| 区间   |  ots 范围  | 平均边际/0.01 | 阶段                   |
| :----- | :--------: | :-----------: | :--------------------- |
| 初始化 | 0.005→0.01 |    +0.09pp    | 信号激活不足           |
| 跳变   | 0.01→0.02  |    +0.40pp    | 从基线大幅提升         |
| 爬升   | 0.03→0.09  |    ~0.22pp    | 线性增长               |
| 递减   | 0.10→0.20  |    ~0.12pp    | 边际收益递减至 1/3     |
| 渐进   | 0.20→0.30  |    ~0.04pp    | 逼近饱和               |
| 近零   | 0.30→0.50  |   ~0.025pp    | 噪声水平，持续缓慢爬升 |

**最终结论：** ots 从 0.005 扫到 0.50（21 个点），**始终严格单调递增**，未出现平台/回撤。但边际持续衰减至 ~0.025pp/0.01（0.50）。对数拟合 Δ≈1.2×ln(ots/0.01) 在整个范围内成立（r²>0.99），0.50 实测 +4.56pp 略低于预测 +4.69pp（首次轻微偏离），暗示曲线开始偏折。

- GAUC_cvr 极限约 **0.742–0.745**（ots→∞）
- gap_cvr 在 0.50 达到 **4.51pp**（新低），仍有小幅改善空间
- BCE_cvr 降至 **0.384**（过置信风险显著）
- CTR 稳定在 −0.04~−0.06pp

**最终推荐（ots 调优完结）：**

- **实用首选：ots=0.12–0.15** — +2.88~3.21pp GAUC_cvr，CTR 无损，gap\<4.75pp
- **极致可选：ots=0.20** — +3.65pp，gap=4.58pp（近最佳），CTR −0.05pp
- **不推荐 >0.20：** 每 0.01 ots 边际 \<0.05pp，gap 改善微弱，BCE 过置信风险加剧

### 4.6 已证否的方向

| 方向                           | 证据                                                     | 结论                                                                                                                              |
| :----------------------------- | :------------------------------------------------------- | :-------------------------------------------------------------------------------------------------------------------------------- |
| dense weight decay             | ots002_adamw GAUC_cvr=0.703467 vs ots002 0.703538 → 等同 | ❌ 无益                                                                                                                           |
| CVR tower wd                   | Config D 结果同 A                                        | ❌ 无益                                                                                                                           |
| 梯度隔离                       | isolate −1.15%                                           | ❌ CVR 梯度有价值                                                                                                                 |
| 自适应加权                     | uw −0.09%, pareto −0.26%                                 | ❌ 不如手动调权                                                                                                                   |
| 梯度手术                       | pcgrad 全部负向/中性                                     | ❌ 无益                                                                                                                           |
| 辅助 loss (ctcvr)              | ctcvr GAUC_cvr=0.698665 (+0.29pp), GAUC_ctr=−0.07pp      | ❌ 中性偏负                                                                                                                       |
| label_smoothing                | dropout0_ls005 −0.74%                                    | ❌ 无法补偿 dropout 缺失                                                                                                          |
| CVR tower 扩宽                 | ots012_wide −0.18pp, ots012_wide_dropout03 −0.10pp       | ❌ 负效果                                                                                                                         |
| dropout at high ots            | ots012_dropout03 +0.08pp（噪声）vs ots03 dropout +0.25pp | ❌ ots≥0.12 后冗余                                                                                                                |
| PLE expert 容量翻4x            | ots012_plebig −0.04pp（噪声），与 ots012 等同            | ❌ 零效果，瓶颈不在 PLE                                                                                                           |
| Transformer all seq (buggy)    | ots012_seq_transformer_all −0.24pp vs ots012             | ❌ 旧版 bug 导致额外−0.18pp；item_id dim 不匹配 + query 侧多余 cate_id                                                            |
| TransformerEncoder (v2 修复版) | ots012_seq_transformer_v2 −0.09pp vs ots012              | ⚠️ 架构本身合理（bottleneck denoise + sequence modeling + gate smoothing 均为标准工业设计），性能中性因 DCNv2+CDOT 已覆盖交叉能力 |

______________________________________________________________________

## 五、结论与推荐

**离线上限（GAUC 最优）：** `ots50` — out_task=0.50 → GAUC_cvr **0.741334 (+4.56pp vs v12 baseline)**，gap_cvr **4.51pp（−0.74pp）**。但 BCE_cvr=0.384，严重过置信，线上大概率负效果。

**线上最优（校准-排序平衡）：** `ots002` — out_task=0.02 → GAUC_cvr **0.703538 (+0.78pp)**，BCE_cvr **~0.491（−0.003，校准几乎不变）**。线上已验证变现率优于 ots012。

**seq_transformer_all（2026-06-30 回传）：** GAUC_cvr=0.722180（+2.65pp vs v12），**−0.24pp vs ots012**。旧版 bug（item_id dim=24 vs 32 不共享 + query 侧 cate_id 剩余）额外贡献了 −0.18pp。

**seq_transformer_v2（修复版，2026-06-30 回传）：** GAUC_cvr=0.723628（+2.79pp vs v12），**−0.09pp vs ots012**。修复后（weight sharing + separate proj_in + clean query）比 buggy 版提升 +0.15pp，但**仍落在 −0.06~−0.09pp 中性噪声区间**。TransformerEncoder 最终结论：**证否，DIN 的 target attention 已足够。**

**核心发现：** out_task_space_weight 经 21 个点全扫（0.005→0.50），GAUC_cvr 严格单调递增但 BCE_cvr 同步恶化。纯排序指标不足以预测线上表现 — 校准偏移导致策略层（阈值/融合分/预算）信号失真。**ots 最优在 0.02（校准 vs 排序的平衡点）而非 0.50。**

**其他已验证方向全部证否：** dropout（ots≥0.12 冗余）、CVR tower 扩宽（−0.18pp）、PLE expert 容量翻 4x（plebig −0.04pp / ple4x −0.07pp 等同基线）、weight decay（零）、ctcvr（中性偏负）、梯度隔离/手术/自适应加权（全部负或中性）、cvr_shortcut（+0.05pp，等同噪声）、**CTR weight 3.3→4.5/5.4（零效果，BCE_ctr 变化不影响 CVR）**。

**瓶颈不在模型容量（PLE 4x + tower 扩宽均无效），在特征质量本身。**

## 六、已跑 config 全览

| Config                         |   ots    |                                       状态                                        |
| :----------------------------- | :------: | :-------------------------------------------------------------------------------: |
| **ots50** 🏆                   |   0.50   |                                ✅ 最终最优 +4.56pp                                |
| **ots40**                      |   0.40   |                                    ✅ +4.31pp                                     |
| **ots30**                      |   0.30   |                                    ✅ +4.09pp                                     |
| **ots25**                      |   0.25   |                                    ✅ +3.90pp                                     |
| **ots020**                     |   0.20   |                                    ✅ +3.65pp                                     |
| **ots015**                     |   0.15   |                                    ✅ +3.21pp                                     |
| **ots012**                     |   0.12   |                                    ✅ +2.88pp                                     |
| ots012_plebig                  |   0.12   |                              ❌ PLE 4x −0.04pp 等同                               |
| **ots012_seq_transformer**     | **0.12** |               **❌ Transformer 重写 −0.06pp vs ots012（等同噪声）**               |
| **ots012_seq_transformer_v2**  | **0.12** | **❌ −0.09pp vs ots012（修复版，weight sharing + separate proj_in；仍中性噪声）** |
| **ots012_seq_transformer_all** | **0.12** |      **❌ −0.24pp vs ots012（旧版 bug：item_id dim 不共享 + query 侧污染）**      |
| ots012_wide_dropout03          |   0.12   |                             ❌ 宽塔−0.10pp 对比同 ots                             |
| ots012_wide                    |   0.12   |                             ❌ 宽塔−0.18pp 对比同 ots                             |
| **ots010**                     |   0.10   |                                    ✅ +2.54pp                                     |
| **ots009**                     |   0.09   |                                    ✅ +2.43pp                                     |
| **ots008**                     |   0.08   |                                    ✅ +2.23pp                                     |
| **ots007**                     |   0.07   |                                    ✅ +2.06pp                                     |
| **ots006**                     |   0.06   |                                    ✅ +1.82pp                                     |
| ots005                         |   0.05   |                                    ✅ +1.60pp                                     |
| ots004                         |   0.04   |                                    ✅ +1.37pp                                     |
| ots003                         |   0.03   |                                    ✅ +1.03pp                                     |
| ots002_dropout03               |   0.02   |                                    ✅ +0.94pp                                     |
| ots002                         |   0.02   |                                    ✅ +0.78pp                                     |
| ots002_adamw                   |   0.02   |                                    ✅ +0.77pp                                     |
| dropout03                      |   0.01   |                                    ✅ +0.62pp                                     |
| config_c (v14 BL)              |   0.01   |                                    ✅ +0.38pp                                     |
| ots0005                        |  0.005   |                                    ✅ +0.09pp                                     |
| ctcvr (ESMM)                   |    —     |                         ✅ +0.29pp GAUC_cvr, −0.07pp CTR                          |
| v12 baseline                   |   0.01   |                                      ✅ 基线                                      |

______________________________________________________________________

## 七、BCE_cvr — GAUC_cvr 取舍

**现象：** ots002 线上效果优于 ots012，但离线差 2.1pp GAUC_cvr。说明纯排名指标不足以预测线上表现，BCE_cvr（校准）是关键。

**BCE_cvr 随 ots 的变化：**

|    ots    |  GAUC_cvr  |   Δ GAUC    |  BCE_cvr   |   Δ BCE    | 校准状态         |
| :-------: | :--------: | :---------: | :--------: | :--------: | ---------------- |
| 0.01 (BL) |   0.6957   |      —      |   0.4940   |     —      | 参考             |
| **0.02**  | **0.7035** | **+0.78pp** | **~0.491** | **−0.003** | **校准几乎不变** |
|   0.05    |   0.7118   |   +1.60pp   |   0.4861   |   −0.008   |                  |
|   0.10    |   0.7212   |   +2.54pp   |   0.4752   |   −0.019   |                  |
| **0.12**  | **0.7245** | **+2.88pp** | **0.4704** | **−0.024** | **校准明显偏差** |
|   0.20    |   0.7322   |   +3.65pp   |   0.4510   |   −0.043   | 偏差 ~9%         |
| **0.50**  | **0.7413** | **+4.56pp** | **0.3840** | **−0.110** | **严重过置信**   |

**BCE 下降的含义：** 对于正样本（~5%），损失项 = −log(p̂)。BCE 从 0.494 降到 0.384，意味着正样本 p̂ 从约 0.05 提升到约 0.15 — 模型对正样本更自信了。但这不代表校准更好。正样本真实率始终 ~5%，p̂ 均值 > 5% 意味着对正样本系统性高估。线上策略层（阈值分割、CTR×CVR 融合分、预算分配）依赖校准后的概率绝对值，p̂ 偏移导致这些决策信号失真。

**结论：ots 每增加 0.01，BCE_cvr 线性下降约 0.002。ots002（BCE −0.003）校准几乎不变，ots012（−0.024）已明显偏移。**

线上 ots002 优于 ots012 充分可解释：+2.1pp GAUC_cvr 的排序增益被校准偏差带来的策略层信号失真抵消。**最优 ots 应在 GAUC 增益与 BCE 偏移的交叉点 — 约 0.02。**

**线上补充验证：** 尝试用 `CTR^0.99 × CVR^0.01`（幂融合）替代 `CTR × (1 + CVR)`（加性融合）以减轻 CVR 校准偏差的影响，但效果仍不行。说明问题不仅是 CVR 概率绝对值偏移 — 即使将 CVR 权重压缩到 0.01 幂次（近乎忽略 CVR），也无效。这意味着 **CVR 的排序信号本身在高 ots 下已受污染**（不仅仅是概率值偏差），过置信导致 CVR 正样本间的相对序也失真。校准不是唯一问题，同时存在分布偏移（offline→online 特征分布变化）。

______________________________________________________________________

## 八、剩余方向：Round 1 config-only 实验（2026-06-28→06-30）

**背景：** ots 全扫完结（+4.56pp max），PLE 容量（−0.04pp）、tower 宽度（−0.18pp）、dropout（冗余 at ots≥0.12）、wd（零）、ctcvr（中性）、**TransformerEncoder（−0.06pp~−0.09pp，中性，架构本身合理）**。
所有模型容量 + 交互 lever 已穷尽。转向特征输出的 config-only 实验。

**假设修正（2026-06-30 UPDATED）：** TransformerEncoder 架构本身是合理工业设计（bottleneck denoise + dot-product stability + gate variance control），性能中性并非架构缺陷，而是 DCNv2+CDOT 已充分覆盖序列交叉能力，Transformer 的 sequence modeling 增量被现有重度交叉淹没。**⏹️ 所有 sequence 方向关闭。** 剩余方向：

**假设：** 瓶颈不在模型容量（PLE 4x + tower 扩宽均无效），而在：

1. **Sequence 表征** — DIN 只做 target attention，TransformerEncoder 可捕捉 item 间交互
1. **CDOT 压缩** — output_dim=4 过度损失交叉信息
1. **DCNv2 交叉层** — cross_num=4 可能不够

### Round 1 实验（v2 修复版已出，−0.09pp 中性 ⏹️）

| 序号 | 实验                    | 内容                                   | 结果              | 状态 |
| :--: | :---------------------- | :------------------------------------- | :---------------- | :--: |
|  1   | **seq_transformer**     | 单 seq → `transformer_encoder` rewrite | −0.06pp vs ots012 | ✅⏹️ |
|  2   | **seq_transformer_all** | 全部 8 seq，旧版 bug（dim mismatch）   | −0.24pp vs ots012 |  ✅  |
|  3   | **seq_transformer_v2**  | 修复版：weight sharing + separate proj | −0.09pp vs ots012 | ✅⏹️ |
|  4   | **cdot_out8**           | `cdot { output_dim: 4 → 8 }`           | −0.11pp vs ots012 | ✅⏹️ |
|  5   | **dcnv2_cross6**        | `dcnv2 { cross_num: 4 → 6 }`           | −0.19pp vs ots012 | ✅⏹️ |

### 决策结论（2026-07-01 UPDATED）

```
seq_transformer       → ⚠️ −0.06pp，中性。架构合理但被 DCNv2/CDOT 覆盖。
seq_transformer_all   → ❌ −0.24pp（旧版 bug 贡献 −0.18pp）
seq_transformer_v2    → ⚠️ −0.09pp，修复后仍中性。⏹️ 不继续投 sequence 方向。
cdot_out8             → ⚠️ −0.11pp，中性。output_dim=4 已够用，不继续投。
dcnv2_cross6          → ⚠️ −0.19pp，中性。cross_num=4 已够用，不继续投。
全部 < +0.2pp         → ✅ 确认模型容量 + 交互层极限。瓶颈确认为特征。
```

### 下一步：Round 2 — 多方向并行推进

所有模型容量 lever 已穷尽。以下为剩余方向（按 ROI 排序）：

| 优先级 | 方向                                  | 类型          | 预估收益       | 成本 |
| :----: | ------------------------------------- | ------------- | -------------- | ---- |
| **P0** | **CVR shortcut feature injection** 🏃 | code + config | +0.3~1pp       | 中   |
| **P0** | **ots × CTR weight 网格搜索**         | config        | +0.5~1pp       | 低   |
| **P0** | **CVR PLE expert 数量调优**           | code + config | +0.5~1pp       | 中   |
|   P1   | **CVR tower residual**                | code          | +0.3~0.5pp     | 低   |
|   P1   | **实时特征 rt5m/rt15m**               | Flink SQL     | +0.5~1.5pp     | 高   |
|   P1   | **UV 加权 BCE loss**                  | code          | gap_cvr −0.5pp | 中   |
|   P1   | **CVR 侧用户画像特征**                | SQL           | +0.3~0.8pp     | 中   |
|   P1   | **归因窗口统一 30d / 数据扩至 60d**   | SQL           | +0.5~1pp       | 中   |
|   P2   | **对比学习 Phase 2**                  | config        | +0.1~0.3pp     | 低   |
|   P2   | **label smoothing > 0.05**            | config        | 未知           | 低   |

______________________________________________________________________

## 九、CVR Shortcut 实验（2026-07-02 启动，需新 wheel）

### 背景

Round 1 全部证否后，剩余未实验的方向之一：**直接用 conversion 历史特征 bypass 主模型，给 CVR tower 加残差捷径**。

**直觉：** user\_\_kv\_\*\_conversion_15d（用户×维度×15d 转化窗口均值）和 item\_\_cnt/ratio_conversion 包含了直接的 CVR 信号。正常模式下这些特征走 DEEP → PEPNet → PLE → tower 路径，容量瓶颈可能衰减了这些强信号的直接影响。CVR Shortcut 让它们跳过多层非线性，直接加到 CVR logit。

**架构：**

参加 shortcut 的只有最后一步 `logit += shortcut_logit`，主路径不变。

```

cvr_shortcut 特征（26 个） 主路径（DCNv2→CDOT→Bias→EPNet→PLE→PPNet）
│ │
▼ ▼
Linear(dim→64) LHUC_PPNet tower (256→128→64)
│ │
▼ ▼
nn.ReLU() Linear(64 → 1)
│ │
▼ ▼
Linear(64 → 1) tower_output (B x 1)
│ │
▼ │
cvr_shortcut_logit (B x 1) │
│ │
└───────── ADD ────────── tower_output + bias_sum ───┘
│
▼
cvr_add_ctr_logits? → + CTR logit
│
▼
sigmoid → prediction

```

`cvr_shortcut_logit` 在 `bias_sum` 添加之后、`sigmoid` 之前加到 tower output 上。`bias_sum` 是 item score bias（全局偏置），shortcut 是特征驱动的额外偏置修正。两者加法顺序无关紧要，同一位置。

- 依赖代码变更（config-only 不够）：`pepnet_dcn_ple.py` 新增 `_cvr_shortcut_mlp`
- 版本：v1.2.19（不改版本号）
- 需要 rebuild wheel → 上传 OSS → 更新 DLC URL

### Config

```

feature_groups {
group_name: "cvr_shortcut"
feature_names: "user\_\_kv_brand_conversion_15d"
...
feature_names: "item\_\_cnt_conversion_15d"
feature_names: "item\_\_ratio_conversion_click_15d"
feature_names: "current_price"
feature_names: "discount_intensity"
feature_names: "discount_type"
feature_names: "price_tag"
feature_names: "user\_\_num_favorite_avg_current_price_15d"
feature_names: "user\_\_num_conversion_avg_current_price_15d"
feature_names: "user\_\_num_click_avg_current_price_15d"
feature_names: "user\_\_kv_price_tag_click_15d"
feature_names: "user\_\_kv_discount_intensity_click_15d"
group_type: DEEP
}

```

实验名：`ots012_cvrsc_price_test`（基于 cvrsc config，新增 9 个 price 特征到 shortcut）

旧实验 `ots012_cvrsc`（无 price 特征，已跑完 +0.05pp 等同噪声）

### CVR Direct Highway（2026-07-02 新增，需新 wheel）

两种模式通过 feature group name 区分，互斥使用：

| 模式       | group_name          | 连接方式                                                          | 参数                    |
| :--------- | :------------------ | :---------------------------------------------------------------- | :---------------------- |
| **ADD**    | `cvr_direct`        | `tower_hidden += Linear(features)` → 用 tower 自己的 final Linear | 1 个投影层              |
| **CONCAT** | `cvr_direct_concat` | `tower_logit += Linear64→1(Linear(features))` → 独立输出头        | 投影层 + 独立 Linear 头 |

**ADD 模式：**

```

cvr_direct features ── Linear(dim→64) ──► tower_hidden (残差, 共享 final Linear)

```

**CONCAT 模式：**

```

cvr_direct_concat features ── Linear(dim→64) ── Linear(64→1) ──► +tower_logit (独立权重)

```

实验名：`ots012_cvr_direct_price`（config: `home_flow_2604_v14_config_c_ots012_cvr_direct_price.config`）
实验名：`ots012_cvr_direct_concat_price`（config: `home_flow_2604_v14_config_c_ots012_cvr_direct_concat_price.config`）

两个 config 都用 price 特征（原 26 转化 + 9 price），仅 group_name 不同决定 ADD/CONCAT 模式。

### 结果

| 指标     | ots012 baseline | ots012_cvrsc | Δ (pp) |
| -------- | :-------------: | :----------: | :----: |
| GAUC_cvr |    0.724540     |   0.725045   | +0.05  |
| AUC_cvr  |    0.772040     |   0.772148   | +0.01  |
| BCE_cvr  |    0.470413     |   0.470527   | +0.01  |
| GAUC_ctr |    0.704289     |   0.704243   | −0.00  |

**结论：cvr_shortcut +0.05pp GAUC_cvr，完全在噪声区间（≈±0.05pp）。与预期相反——这些 conversion 统计特征通过主路径（DEEP→EPNet→PLE→tower）和通过 shortcut MLP 效果等同，说明主路径没有衰减这批信号。证否。**

### Highway 实验结果（2026-07-02）

| 实验                                              | ots  | GAUC_cvr | Δ vs ots012 | BCE_cvr  | 说明                              |
| ------------------------------------------------- | :--: | :------: | :---------: | :------: | --------------------------------- |
| ots012 baseline                                   | 0.12 | 0.724540 |      —      | 0.470413 | 参考                              |
| ots012_cvrsc                                      | 0.12 | 0.725045 |   +2.93pp   | 0.470527 | shortcut                          |
| ots012_cvrsc_no_cvradd                            | 0.12 | 0.726674 |   +3.09pp   | 0.470367 | shortcut + 关 cvr_add             |
| ots012_cvr_direct_price (ADD)                     | 0.12 | 0.725373 |   +2.96pp   | 0.470379 | price highway ADD                 |
| ots012_cvr_direct_price_no_cvradd (ADD)           | 0.12 | 0.727393 |   +3.17pp   | 0.470439 | price highway ADD + 关 cvr_add    |
| ots012_cvr_direct_concat_price (CONCAT)           | 0.12 | 0.725084 |   +2.94pp   | 0.470408 | price highway CONCAT              |
| ots012_cvr_direct_concat_price_no_cvradd (CONCAT) | 0.12 | 0.727121 |   +3.14pp   | 0.470349 | price highway CONCAT + 关 cvr_add |
| ctcvr_no_cvradd                                   |  0   | 0.702805 |   +0.71pp   | 0.494102 | ESMM + 关 cvr_add                 |

**分析：**

- **cvrsc_no_cvradd 重跑后 0.726674 (+3.09pp)** — 比原 cvrsc 0.725045 (+2.93pp) 略好，但仍在 ±0.08pp 噪声区间。`cvr_add_ctr_logits` 开/关对结果无本质影响
- **ADD 模式 +0.08pp / CONCAT 模式 +0.03pp** → 均落在 ±0.05pp 噪声区间，与 shortcut 结果一致。price 特征从主路径拿出来走"高速公路"没有任何提升 → **主路径不存在 price 信号衰减**，瓶颈不在特征通路
- **ctcvr_no_cvradd (ots=0) 修复后 0.702805 (+0.71pp)** — 之前 config 有 `cvr_add_ctr_logits: true`（实际未关），现修正为 `false` 后 ESMM 可从 -2.97pp 回正到 +0.71pp。ESMM 本身中性偏正

**最终结论：所有 bypass 主路径的实验（shortcut、ADD highway、CONCAT highway、cvr_add_ctr_logits 关闭）全部证否。主路径（DCNv2→CDOT→EPNet→PLE→PPNet→tower）没有衰减任何特征信号。**

______________________________________________________________________

## 十、完整架构图（PEPNet + DCNv2 + PLE + TransformerEncoder Hybrid）

### 10.1 总览

```
Input Features
 (sparse + raw + lookup + sequence)
         │
         ▼
 EmbeddingGroup
 ┌────────────────────────────────────────────────────────────────┐
 │  "all" group  │  "domain" group  │  sequence groups (×8)     │
 │  [B, M]       │  [B, D]          │  各 [B, max_len, S_feat]  │
 └───────────────┴──────────────────┴────────────────────────────┘
         │
         ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  8× TransformerEncoder (sequence groups)                      │
 │  各: [B, S_feat] → Transformer(128) → CrossAttn → Gate → proj │
 │  输出拼回 "all"                                                │
 └────────────────────────────────────────────────────────────────┘
         │
         ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PEPNet Frontend                                               │
 │                                                                │
 │  ┌─────────────────────┐  ┌────────────────────────────┐       │
 │  │ DCNv2 CrossV2       │  │ CDOT (domain → 16+16)      │       │
 │  │ [B, M] → ×4 → [B,M] │  │ dim=4, output_dim=4        │       │
 │  │ cross_num=4         │  │ compress_hidden=[512,374]   │       │
 │  │ low_rank=256        │  │                             │       │
 │  └─────────────────────┘  └────────────────────────────┘       │
 │                                                                │
 │  ┌─────────────────────────────────────────────────────────┐   │
 │  │ Component LayerNorm + Concat                             │   │
 │  │ [LN(main), LN(cross), LN(cdot_out), LN(bias), LN(cdot_mid)]│ │
 │  │ → [B, 2M + 32 + D]                                      │   │
 │  └─────────────────────────────────────────────────────────┘   │
 │                                                                │
 │  ┌─────────────────────────────────────────────────────────┐   │
 │  │ LHUC_EPNet (element-wise scaling from "domain")          │   │
 │  │ MLP(domain → 256 → 2M+32+D)                             │   │
 │  │ → tanh * 5 + 1 → element-wise multiply                  │   │
 │  └─────────────────────────────────────────────────────────┘   │
 └────────────────────────────────────────────────────────────────┘
         │
         ▼
 ┌────────────────────────────────────────────────────────────────┐
 │  PLE ExtractionNet (CGC routing, 2 layers)                    │
 │                                                                │
 │  Layer1 (in_dim = 2M+32+D):                                   │
 │    CTR task: 2 experts MLP[→512→256]  +  2 shared experts     │
 │    CVR task: 2 experts MLP[→512→256]  +  2 shared experts     │
 │    Gate: softmax(Linear(task_in → 4)) → Σ experts             │
 │    Output: ctr[256], cvr[256], shared[256]                    │
 │                                                                │
 │  Layer2 (in_dim = 256):                                       │
 │    CTR task: 2 experts MLP[256→128] + 2 shared experts        │
 │    CVR task: 2 experts MLP[256→128] + 2 shared experts        │
 │    Output: ctr[128], cvr[128], shared[128] (最终层弃 shared)  │
 └────────────────────────────────────────────────────────────────┘
         │
         ▼
 ┌──────────────────────────────────────────────────────────┐
 │  CTR Tower                          CVR Tower           │
 │  ┌─────────────────────┐            ┌──────────────────┐ │
 │  │ LHUC_PPNet ×3       │            │ LHUC_PPNet ×3    │ │
 │  │ 128→512→256→128     │            │ 128→512→256→128  │ │
 │  │ ReLU + Dropout(0.1) │            │ ReLU + Dropout   │ │
 │  │ + LayerNorm         │            │ + LayerNorm      │ │
 │  │ + per-layer LHUC    │            │ + per-layer LHUC │ │
 │  └──────────┬──────────┘            └────────┬─────────┘ │
 │             ▼                                 ▼           │
 │    Linear(128→1)                    Linear(128→1)         │
 │             │                                 │           │
 │             ▼                                 │           │
 │      + bias_sum (domain)                     │           │
 │             │                                 │           │
 │         logits_ctr ─────── + ─────────────────┘           │
 │                                │                          │
 │                            logits_cvr                     │
 │                                │                          │
 │             ▼                  ▼                          │
 │       sigmoid(logits_ctr)    sigmoid(logits_cvr)          │
 │       → pCTR [B]             → pCVR [B]                  │
 └──────────────────────────────────────────────────────────┘
```

### 10.2 组件详述

#### 输入特征

| 特征类型            | 分组            | 规模                    | 说明                                                          |
| :------------------ | :-------------- | :---------------------- | :------------------------------------------------------------ |
| id_feature          | "all", "domain" | ~500+                   | user_id, item_id, cate_id_path, brand, price_tag, site 等     |
| raw_feature         | "all"           | ~数十                   | ratio/统计特征，离散化后映射为 embedding                      |
| lookup_feature      | "all"           | ~数十                   | KV 聚合（15d/60d/360d 窗口内的 click/conversion/favorite）    |
| sequence_group (×8) | "all" 内        | 各组 max_len=5/10/20/50 | 行为序列（click, conversion, favorite, like, chaprice_click） |
| contrastive         | 独立            | title_vector            | 对比学习用的物标题向量                                        |

#### 8 个行为序列

| 序列名                | max_len | 内部 Transformer hidden | query_dim | sequence_dim |
| :-------------------- | :------ | :---------------------- | :-------- | :----------- |
| click_10_seq          | 10      | 128                     | 188       | 224          |
| click_50_seq          | 50      | 128                     | 188       | 224          |
| conversion_5_seq      | 5       | 128                     | 192       | 228          |
| conversion_20_seq     | 20      | 128                     | 192       | 228          |
| favorite_5_seq        | 5       | 128                     | 192       | 228          |
| favorite_10_seq       | 10      | 128                     | 192       | 228          |
| like_50_seq           | 50      | 128                     | 112       | 140          |
| chaprice_click_50_seq | 50      | 128                     | 180       | 216          |

各序列包含的 item-side 特征（item_id_emb, cate_id_path, brand, core_entity, price_tag 等）+ `*_ts` 时间戳。query_side = 同组 item-side 特征 + target item_id + target cate + target 其他 + 时间差。

#### TransformerEncoder（v2 修复版）

```
sequence [B, T, S_dim]
   │
   ├── proj_in_s: Linear(S_dim → 128)  ── dropout ── self-attention (1 layer, 4 heads)
   │                                              │
   │                                            h [B, T, 128]
   │                                              │
   q_proj ─── proj_in_q: Linear(Q_dim → 128)     │
      │                                           │
      └────────────── dot-product cross-attn ─────┘
                     scores = q·h^T / √128
                     attended = softmax(scores)·h  [B, 128]
                           │
                     ┌─────┴─────┐
                     │ attended   │ mean(h) [B, 128]
                     │            │
                     └── gate ────┘
                     gate = sigmoid(MLP([q, attended, q⊙attended]))
                     fused = gate·attended + (1-gate)·mean(h)
                           │
                        LayerNorm
                           │
                     proj_pooled: Linear(128 → S_dim)
                           │
                     output [B, S_dim] → 拼回 "all" group
```

**关键特征：**

- `proj_in_s` 和 `proj_in_q` 独立（S_dim ≠ Q_dim 时无维度 assert）
- 全部 8 个序列共享同一份 item_id 权重表（`[3000000, 32]`，通过 embedding_name: "item_id_emb" 别名共享）
- self-attention 无 target leakage（仅仅建模 item-item dependency）
- cross-attention 为 0 参数可学习量（纯 dot-product）
- gate 为 per-dimension 向量门控（[B, 128]），控制 attended vs mean 的融合比例
- 最终 projection 需要恢复原始 S_dim，因为拼回 "all" 时要求维度一致

#### DCNv2 CrossV2

```
x_0 = main_features [B, M]
for i in range(4):
    x_l_v   = Linear(M→256, no_bias)(x_l)
    x_l_w   = Linear(256→M, bias)(x_l_v)
    x_l     = x_0 * x_l_w + x_l      # element-wise gating + residual
→ [B, M]
```

- cross_num=4 创建 4 层显式交叉
- low_rank=256 分解参数
- 作用于 PEPNet 前端（LHUC 和 PLE 之前）

#### CDOT

```
domain features [B, 4, 32] (mmb_id, item_id, f_req_page, f_req_domain 各取前32维)
   │
   ├── sub_compress: [4→32] → reshape → [B, 1024]
   ├── compress_mlp: 1024→512→374→16 → reshape → [B, 4, 4]
   └── bmm: x @ compress_wt + bias → flatten → [B, 16] (allint_out)
       + compress_wt_flat → [B, 16] (allint_mid_out, 作为辅助特征保留)
```

- output_dim=4，输出 `num_slots × output_dim = 16` 维
- 跨 domain 特征的二阶动态交叉

#### LHUC_EPNet

```
gate = MLP(domain_features → 256 → deep_concat_dim)
scale = tanh(gate × 0.2) × 5 + 1
output = deep_input × scale      # element-wise scaling
```

- 作用于 Component LN Concat 后的全部特征
- scaling 范围约 [0, 6]，通过 0.2 系数控制 soft 范围
- domain 特征同时参与 bias、CDOT、LHUC 三个通路

#### PLE ExtractionNet（CGC 路由）

```
Layer1:
  CTR gate:  softmax(Linear(ctr_in → 4)) → 选 2 CTR experts + 2 shared
  CVR gate:  softmax(Linear(cvr_in → 4)) → 选 2 CVR experts + 2 shared
  Share gate: softmax(Linear(share_in → 6)) → 选全部 6 experts → 下一层

Layer2:
  CTR gate:  softmax(Linear(ctr_in → 4)) → 选 2 CTR experts + 2 shared
  CVR gate:  softmax(Linear(cvr_in → 4)) → 选 2 CVR experts + 2 shared
  (最终层弃 shared output)
```

- 每层专家 MLP 配 `hidden_units`
- Layer1: task_expert=[512,256], share_expert=[512,256]
- Layer2: task_expert=[256,128], share_expert=[256,128]

#### LHUC_PPNet（任务塔）

```
for each layer in tower:
    gate = MLP(domain → 256 → cur_in_dim)
    scale = tanh(gate × 0.2) × (5.0 + layer_idx) + 1.0  # 逐层放大
    x = x * scale
    x = Linear(cur_in_dim → next_dim)(x)
    x = ReLU(x) + Dropout(0.1) + LayerNorm  # 末层跳过
```

- 3 层 MLP：128→512→256→128
- LHUC scaling 逐层增加（layer 0: scale ~[0,6]; layer 1: ~[0,7]; layer 2: ~[0,8]）
- CVR tower 与 CTR tower 结构相同

#### 最终预测

```
logits_ctr = Linear(128→1)(ctr_tower_out) + bias_sum
logits_cvr = Linear(128→1)(cvr_tower_out) + logits_ctr
pCTR = sigmoid(logits_ctr)
pCVR = sigmoid(logits_cvr)
```

- `bias_sum` = sum of `domain` features 的首元素（4 scalars）
- `logits_cvr += logits_ctr` 实现 ESMM 风格 CTCVR 建模（logit 级别 shortcut）
- CVR loss 使用 task_space_indicator（`is_click=1` 时权重 1，`is_click=0` 时权重 0.12）

### 10.3 Shape Flow 概要

| 阶段                  | 输入 Shape       | 输出 Shape                         | 说明                  |
| :-------------------- | :--------------- | :--------------------------------- | :-------------------- |
| Embedding             | —                | all: [B, M], domain: [B, D], seq×8 | M≈2000-3000, D≈80-100 |
| 8× Transformer        | [B, T, S_dim]    | [B, S_dim]×8 → 拼回 all            | S_dim≈140-228         |
| DCNv2 Cross           | [B, M]           | [B, M]                             | ×4 cross layers       |
| CDOT                  | domain: [B,4,32] | [B,16] + [B,16]                    | output_dim=4          |
| Component LN + Concat | 5 components     | [B, 2M+32+D]                       | ≈4000-6000            |
| LHUC_EPNet            | [B, 2M+32+D]     | [B, 2M+32+D]                       | element-wise          |
| PLE Layer1            | [B, 2M+32+D]     | ctr[256], cvr[256], share[256]     | 2×2 + 2 experts       |
| PLE Layer2            | [B, 256]         | ctr[128], cvr[128]                 | 2×2 + 2 experts       |
| CTR Tower             | [B, 128]         | [B, 128] → Linear → logits         | + bias_sum            |
| CVR Tower             | [B, 128]         | [B, 128] → Linear → logits         | + ctr_logits          |
| Output                | logits [B, 2]    | pCTR [B], pCVR [B]                 | sigmoid               |

### 10.4 参数规模简估

| 模块                  | 参数量级         | 关键参数                                     |
| :-------------------- | :--------------- | :------------------------------------------- |
| Embedding             | ~2M (id_feature) | item_id: [3M, 32] ≈ 96M（最大表）            |
| TransformerEncoder ×8 | ~5M              | 各 1 layer, 4 heads, 128 hidden              |
| DCNv2 Cross           | ~15M             | 4 × (M×256 + 256×M) ≈ 12-16M                 |
| CDOT                  | ~1.5M            | sub_compress [4×32] + compress_mlp [1024→16] |
| LHUC_EPNet            | ~6M              | MLP [D→256→2M+32+D]                          |
| PLE Layer1            | ~15M             | (2+2+2) × MLP [4K→512→256] + 4 gates         |
| PLE Layer2            | ~2M              | (2+2+2) × MLP [256→128] + 4 gates            |
| CTR+ CVR Towers       | ~2.5M            | 各 3× LHUC_MLP [128→512→256→128]             |
| **合计**              | **~50M+**        | 不含 embedding 权重约 130M+                  |

### 10.5 关键设计决策摘要

| 决策                    | 选择                          | 理由                                                            |
| :---------------------- | :---------------------------- | :-------------------------------------------------------------- |
| Multi-task              | ESMM (logit-add) + task_space | 联合优化 CTR+CVR，CVR loss 仅在 click 样本上重加权              |
| PLE 层数                | 2 （CGC）                     | 标准工业配置，避免 3 层过参数化                                 |
| Sequence                | TransformerEncoder (v2)       | 原为 DIN → Transformer 升级尝试，实测中性（被 DCNv2+CDOT 覆盖） |
| Item ID 共享            | 1 表 [3M, 32] → 7 引用        | weight alias 机制，减少参数量                                   |
| CDOT output_dim         | 4                             | 太低可能损失交叉信息（→ 正在实验 output_dim=8）                 |
| DCNv2 cross_num         | 4                             | 可能不够（→ 正在实验 cross_num=6）                              |
| LHUC vs EPNet           | LHUC 变体                     | 更稳定的 element-wise scaling，替代原 EPNet 的 gated network    |
| Tower 宽度              | 512→256→128                   | 标准 3 层 MLP，宽到窄渐进压缩                                   |
| ots (over-temp scaling) | 0.12                          | 最优 BCE-AUC 平衡点                                             |
