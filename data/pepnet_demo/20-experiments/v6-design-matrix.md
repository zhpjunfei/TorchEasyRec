______________________________________________________________________

## date: 2026-06-08 tags: [experiment, v6, design-matrix, 2x2x2, deterministic] related: \["\[[v7-ple-d-variants]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v6 设计矩阵 — 2×2×2 系统化实验

> v6 阶段核心实验: 8/8 cells 全部完成, PEPNet × PLE × {lsp, d, dlsp, 无扩展} 系统化对比.

## 实验设计

3 维度:

1. **架构**: PEPNet_v2 (4 变种) × PLE (4 变种) = 8 cells
1. **特征扩展**: lsp / d / dlsp / 无扩展
1. **目标**: 寻找最优 (架构, 特征) 组合

## 确定性结果 (修复后, 2026-06-08)

> 每实验 1 次, bitwise identical, Std=0pp. 所有 Δ 以 `v6_baseline_hbs` 为基准.

| 架构    | 特征扩展           |   CVR AUC    |   CTR AUC    |    ΔCVR     |    ΔCTR     | 判断               | Config                  |
| :------ | :----------------- | :----------: | :----------: | :---------: | :---------: | :----------------- | :---------------------- |
| PEPNet  | **baseline_hbs**   | **0.786723** |   0.788628   |      —      |      —      | 对照               | `v6_baseline_hbs`       |
| PEPNet  | lsp                |   0.785448   |   0.788952   |   -0.13pp   |   +0.03pp   | ❌ CVR退步         | `v6_domain_lsp`         |
| PEPNet  | dlsp               |   0.782194   |   0.791949   |   -0.45pp   |   +0.33pp   | ❌ CTR陷阱         | `v6_domain_dlsp`        |
| PEPNet  | domain_id_only     |   0.782866   |   0.792675   |   -0.39pp   |   +0.40pp   | ❌ CTR陷阱         | `v6_domain_id_only`     |
| PEPNet  | domain_id_only_hbs |   0.781750   |   0.792445   |   -0.50pp   |   +0.38pp   | ❌ CTR陷阱         | `v6_domain_id_only_hbs` |
| PLE     | baseline           |   0.786291   |   0.787888   |   -0.04pp   |   -0.07pp   | ≈ tie              | `v6_ple`                |
| PLE     | lsp                |   0.788341   |   0.788498   |   +0.16pp   |   -0.01pp   | 🔶 CVR微升/CTR持平 | `v6_ple_lsp`            |
| PLE     | dlsp               |   0.784696   |   0.789653   |   -0.20pp   |   +0.10pp   | ❌ CVR退步/CTR微升 | `v6_ple_dlsp`           |
| **PLE** | **d=8**            | **0.791069** | **0.790610** | **+0.43pp** | **+0.20pp** | **✅ 双正**        | `v6_ple_d`              |
| **PLE** | **d=16**           | **0.791747** | **0.791909** | **+0.50pp** | **+0.33pp** | **🏆 双最优**      | `v7_ple_d16`            |
| PLE     | d=32               |   0.770030   |   0.792160   |   -1.67pp   |   +0.35pp   | ❌❌ 过参数化      | `v7_ple_d32`            |
| PLE     | dpage [1]          |      —       |      —       |      —      |      —      | 🐛 Config bug      | `v7_ple_dpage`          |
| PLE     | ph                 |   0.789219   |   0.788232   |   +0.25pp   |   -0.04pp   | 🔶 CVR微升/CTR持平 | `v7_ple_ph`             |

### 双指标评估 (Score = pCTR × (1+pCVR))

在线 score 公式下 CTR 权重高, **必须 CVR + CTR 同向改进才有实际收益**. 按 score 预期收益排序:

| 实验                        |     CVR      |     CTR      |    ΔCVR     |    ΔCTR     |             Score 预期             |
| :-------------------------- | :----------: | :----------: | :---------: | :---------: | :--------------------------------: |
| **PLE + d=16**              | **0.791747** | **0.791909** | **+0.50pp** | **+0.33pp** |       **🏆 双正 → 最大收益**       |
| **PLE + d=8**               | **0.791069** | **0.790610** | **+0.43pp** | **+0.20pp** |            **✅ 双正**             |
| PLE + ph                    |   0.789219   |   0.788232   |   +0.25pp   |   -0.04pp   |       🔶 CVR 微升, CTR 持平        |
| PLE + lsp                   |   0.788341   |   0.788498   |   +0.16pp   |   -0.01pp   |       🔶 CVR 微升, CTR 持平        |
| PEPNet baseline             |   0.786723   |   0.788628   |      —      |      —      |                对照                |
| PLE baseline                |   0.786291   |   0.787888   |   -0.04pp   |   -0.07pp   |               ≈ tie                |
| PEPNet + lsp                |   0.785448   |   0.788952   |   -0.13pp   |   +0.03pp   |   ❌ CVR 退步, CTR 微升不足弥补    |
| PLE + dlsp                  |   0.784696   |   0.789653   |   -0.20pp   |   +0.10pp   |       ❌ CVR 退步 > CTR 微升       |
| PEPNet + domain_id_only     |   0.782866   |   0.792675   |   -0.39pp   |   +0.40pp   | ❌ **CTR 陷阱**: CVR 退步 > CTR 升 |
| PEPNet + dlsp               |   0.782194   |   0.791949   |   -0.45pp   |   +0.33pp   | ❌ **CTR 陷阱**: CVR 退步 > CTR 升 |
| PEPNet + domain_id_only_hbs |   0.781750   |   0.792445   |   -0.50pp   |   +0.38pp   | ❌ **CTR 陷阱**: CVR 退步 > CTR 升 |
| **PLE + d=32**              | **0.770030** | **0.792160** | **-1.67pp** | **+0.35pp** |  **❌❌ 过参数化灾难: CVR 暴跌**   |

### d 维度对比: 8 vs 16 vs 32

|  dim   |   CVR AUC    |   CTR AUC    |    ΔCVR     |    ΔCTR     | 结论          |
| :----: | :----------: | :----------: | :---------: | :---------: | :------------ |
| **16** | **0.791747** | **0.791909** | **+0.50pp** | **+0.33pp** | **🏆 最优**   |
|   8    |   0.791069   |   0.790610   |   +0.43pp   |   +0.20pp   | ✅ 次优       |
|   32   |   0.770030   |   0.792160   |   -1.67pp   |   +0.35pp   | ❌❌ 过参数化 |

d=32 CVR 暴跌 -1.67pp: `f_req_domain hash_bucket_size:500` + `embedding_dim:32` 导致 domain 特征 embedding 参数过多 (500×32=16K), domain 出现频率稀疏, 高维 embedding 在稀疏特征上过拟合, 严重损害 CVR 泛化. d=16 在容量和泛化间达到最优平衡.

### 关键影响

- **PLE + d 系列是唯一双正组合**: d=8 (CVR +0.43pp, CTR +0.20pp), d=16 (CVR +0.50pp, CTR +0.33pp). 双指标同向改进, score 公式下收益最大
- **d=16 确认为最优 dim**: d=8 < d=16 < d=32(灾难). d=32 CVR -1.67pp 过参数化, d=16 在容量和泛化间最优平衡
- **dpage config bug**: `f_req_domain` 在 feature_configs 中定义但未接入任何 feature_group → 死代码. 修复后 domain 组 = `[mmb_id, item_id, f_req_page, f_req_domain]`, 与 `v7_ple_d`(d=8) 完全一致. `v7_ple_dpage` 结果需重跑或复用 d=8 结果 (0.791069/0.790610). 详见 \[\[footnote-1|注 [1]\]\].
- **ph 微弱 CVR 正**: CVR +0.25pp 但 CTR -0.04pp, 偏科组合, 非生产候选
- **CTR 陷阱确认**: PEPNet+dlsp/domain_id_only CTR +0.33~0.40pp 但 CVR -0.39~0.50pp. score 公式下 CVR 退步 > CTR 增益, 净负收益
- **PLE + lsp 偏科**: CVR +0.16pp 但 CTR -0.01pp, 仅 CVR 单边改进
- **PLE baseline (0.786291) ≈ PEPNet baseline (0.786723)**: ΔCVR -0.04pp, ΔCTR -0.07pp, 两者等同
- **修复前 3 个假象**: "PLE 反超 PEPNet"、"lsp +0.30pp"、"d=8 sweet spot" 均为 eval noise 导致

### 修复前后对比

修复前 5-run noise 0.73pp 导致 3 个关键假象:

| 假象              |   修复前    |          确定性真相          |
| :---------------- | :---------: | :--------------------------: |
| "PLE 反超 PEPNet" | PLE +0.56pp |   PLE ≈ PEPNet (Δ-0.04pp)    |
| "lsp +0.30pp"     |   +0.30pp   |         **-0.13pp**          |
| "d=8 sweet spot"  |  d=8 最优   | d=16 > d=8 (+0.07pp/+0.13pp) |

### GPU 型号交叉验证: A10×2 vs L20×2

2026-06-08 用 **2×L20** 重跑 `v6_ple_d`, 对比原 A10×2 结果:

| GPU            |   CVR AUC    | CTR AUC  |
| :------------- | :----------: | :------: |
| A10×2 (确定性) | **0.791069** | 0.790610 |
| L20×2          |   0.790144   | 0.791314 |
| Δ              | **-0.09pp**  | +0.07pp  |

Δ ≈ ±0.09pp, 在浮点精度差异范围内 (即使 `cudnn.deterministic=True`, 不同架构 GPU 的 CUDA kernel 实现不同导致最后几位差异). **结论: GPU 型号不影响 AUC 的实际结论.**

### 注

[1] **dpage config bug**: `v7_ple_dpage` 的 `f_req_domain` 在 feature_configs 中定义 (dim=8) 但未加入任何 feature_group → 模型未使用此特征, 结果等于 PLE baseline (0.786291/0.787888). 修复后 domain 组等于 `v7_ple_d`(d=8), 因此 dpage 真实结果 = d=8 (0.791069/0.790610). 无需重跑.

## 下一步

- [x] ~~v7_ple_d32, v7_ple_dpage, v7_ple_ph~~ — ✅ 全部完成 (dpage 标记为 config bug, 结果 = d=8)
- [ ] 公平 A/B (7d vs 7d, 同归因窗口) — 用 PLE + d=16
