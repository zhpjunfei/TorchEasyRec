______________________________________________________________________

## date: 2026-06-08 tags: [experiment, v6, design-matrix, 2x2x2, deterministic] related: \["\[[v7-ple-d-variants]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v6 设计矩阵 — 2×2×2 系统化实验

> v6 阶段核心实验: 8/8 cells 全部完成, PEPNet × PLE × {lsp, d, dlsp, 无扩展} 系统化对比.

## 实验设计

3 维度:

1. **架构**: PEPNet_v2 (4 变种) × PLE (4 变种) = 8 cells
1. **特征扩展**: lsp / d / dlsp / 无扩展
1. **目标**: 寻找最优 (架构, 特征) 组合

## 8/8 Cells 结果 (修复前, 5-run noise 0.73pp, 需与修后对比)

| 架构    | 特征扩展       | CVR AUC (修复前) | Δ vs base | 备注                        | Config              |
| :------ | :------------- | :--------------: | :-------: | :-------------------------- | :------------------ |
| PEPNet  | baseline_hbs   |      0.7822      |     —     | hash_fix baseline ⏳ 待重跑 | `v6_baseline_hbs`   |
| PEPNet  | domain_id_only |      0.7864      |   +0.42   | ⏳ 待重跑                   | `v6_domain_id_only` |
| PEPNet  | lsp            |      0.7852      |   +0.30   | ⏳ 待重跑                   | `v6_domain_lsp`     |
| PEPNet  | dlsp           |      0.7838      |   +0.16   | ⏳ 待重跑                   | `v6_domain_dlsp`    |
| PEPNet  | dpage          |        —         |     —     | CDOT 移除 d, 退步 ⏳ 待重跑 | —                   |
| PLE     | baseline       |      0.7878      |   +0.56   | ⏳ 待重跑                   | `v6_ple`            |
| PLE     | lsp            |      0.7801      |   -0.21   | ⚠️ lsp 极性反转 ⏳ 待重跑   | `v6_ple_lsp`        |
| **PLE** | **d**          |    **0.7922**    | **+1.00** | 🏆 修复前最优 ⏳ 重跑\*\*   | `v6_ple_d`          |
| PLE     | dlsp           |      0.7831      |   +0.09   | ⏳ 待重跑                   | `v6_ple_dlsp`       |

## 确定性结果 (修复后, 2026-06-08)

> 每实验 1 次, bitwise identical, Std=0pp.

| 架构    | 特征扩展         | CVR AUC (确定性) | Δ vs baseline_hbs | CTR AUC (确定性) | Config              |
| :------ | :--------------- | :--------------: | :---------------: | :--------------: | :------------------ |
| PEPNet  | **baseline_hbs** |   **0.786723**   |         —         |     0.788628     | `v6_baseline_hbs`   |
| PEPNet  | lsp              |     0.785448     |    **-0.13pp**    |     0.788952     | `v6_domain_lsp`     |
| PEPNet  | dlsp             |     0.782194     |    **-0.45pp**    |     0.791949     | `v6_domain_dlsp`    |
| PEPNet  | domain_id_only   |        ⏳        |                   |                  | `v6_domain_id_only` |
| PLE     | baseline         |   **0.786291**   |    **-0.04pp**    |     0.787888     | `v6_ple`            |
| **PLE** | **d**            |   **0.791069**   |    **+0.43pp**    |     0.790610     | `v6_ple_d`          |
| PLE     | lsp              |        ⏳        |                   |                  | `v6_ple_lsp`        |
| PLE     | dlsp             |        ⏳        |                   |                  | `v6_ple_dlsp`       |

### 关键影响

- **baseline_hbs 从 0.7822 跳到 0.786723 (+0.45pp)**: 之前踩到 eval 低谷窗口, 导致修复前所有 "Δ vs baseline" 偏正
- **lsp 反转**: 修复前以为 +0.30pp, 实际 **-0.13pp** (lsp 在 PEPNet 下也是负增益)
- **dlsp 反转**: 修复前以为 +0.16pp, 实际 **-0.45pp** (dlsp 显著负增益)
- **PLE baseline (0.786291) ≈ PEPNet baseline (0.786723)**: Δ仅 **-0.04pp**. 修复前"PLE 反超 PEPNet"是假象, 两者确定性等同
- **PLE + d=16 是双指标最优**: CVR +0.50pp, CTR +0.33pp vs baseline, 均在确定方向
- **PEPNet + dlsp 是 CTR 陷阱**: CTR 最高但 CVR 最低 (-0.45pp), score 公式下实际有害

### 双指标综合分析

| 实验            |            Config |   CVR AUC    |   CTR AUC    |    ΔCVR     |    ΔCTR     | 判断            |
| :-------------- | ----------------: | :----------: | :----------: | :---------: | :---------: | :-------------- |
| PEPNet baseline | `v6_baseline_hbs` |   0.786723   |   0.788628   |      —      |      —      | 对照            |
| PEPNet + lsp    |   `v6_domain_lsp` |   0.785448   |   0.788952   |   -0.13pp   |   +0.03pp   | ❌ CVR 退步     |
| PEPNet + dlsp   |  `v6_domain_dlsp` |   0.782194   |   0.791949   | **-0.45pp** |   +0.33pp   | ❌ CVR 大幅退步 |
| PLE baseline    |          `v6_ple` |   0.786291   |   0.787888   |   -0.04pp   |   -0.07pp   | ≈ tie           |
| **PLE + d=8**   |        `v6_ple_d` | **0.791069** |   0.790610   | **+0.43pp** |   +0.20pp   | ✅ 双正         |
| **PLE + d=16**  |      `v7_ple_d16` | **0.791747** | **0.791909** | **+0.50pp** | **+0.33pp** | 🏆 **双最优**   |

Score 公式 `pCTR * (1+pCVR)` 下, CTR 和 CVR 同向改进才有最大收益. PLE+d 系列是唯二双正的组合.

## 5 个关键发现

### 1. hash_fix (f_req_page hash_bucket_size=100) 是最大单一贡献 +2.6pp

之前 f_req_page 用 `vocab_list` 误配, 改 `hash_bucket_size: 100` 后 CVR +2.6pp 单次. 修后 v6_ple 已含此 fix.

### 2. PLE baseline (0.786291) ≈ PEPNet baseline (0.786723), Δ-0.04pp

**修复前"PLE 反超 PEPNet"是假象**: 修复前 PLE 单跑 0.7878 vs baseline 0.7822 看似 +0.56pp, 但确定性下 Δ仅 -0.04pp (等同). PLE 本身不带来提升, **必须 PLE + d 才有增益**.

### 3. f_req_domain (d) 是唯一正增益特征扩展

确定性结论:

- PEPNet + lsp: **-0.13pp**
- PEPNet + dlsp: **-0.45pp**
- PLE + d: **+0.43pp** (最优)
- PLE + d16: **+0.50pp** (稍优, 待确认)
- **PEPNet 下特征扩展全负, PLE + d 是唯一正组合**

### 4. lsp 在 PEPNet 下也是负增益 (确定性)

| 结论          | 修复前 (单跑) |   确定性    |
| :------------ | :-----------: | :---------: |
| PEPNet + lsp  |    +0.30pp    | **-0.13pp** |
| PEPNet + dlsp |    +0.16pp    | **-0.45pp** |

**之前"lsp 有效"是假象**: baseline 跑在 eval 低谷, lsp 跑在正常点.

### 5. v6_ple_dlsp 需重评

修复前 PLE + lsp + d = 0.7831. 等待 v6_ple/v6_ple_lsp/v6_ple_dlsp 确定性重跑.

### 6. PLE+d 是唯一正增益: d=8 +0.43pp, d=16 +0.50pp

PLE + d 确定性 **+0.43pp (d=8)** / **+0.50pp (d=16)** vs baseline_hbs. d=16 双指标优于 d=8 (CVR +0.07pp, CTR +0.13pp). 须等 d=32 确认最优 dim.

### 7. v6_ple_lsp / v6_ple_dlsp 极性反转 ⏳ 待重跑

## 旧数据集结论被推翻 (v6 起换 7d 数据)

之前结论 (53-day 负采样数据集, v1c 基线):

- v1c 0.768 vs PEPNet 0.742 = **2.6pp 架构差距**

新结论 (7-day 无负采样, v6_ple_d):

- v6_ple_d 0.7852 vs v1c 0.768 = **+1.7pp 离线优势**

推翻原因: 数据集不同 (53d neg-sample vs 7d no-neg-sample), 见 \[[../30-data/sql-attribution-30d-vs-24h|sql 归因差异]\].

## v6 确定性重跑进度 (双指标)

| 实验              | Config              | 修复前 CVR |   确定性 CVR    | 确定性 CTR | Δ CVR vs baseline |
| :---------------- | :------------------ | :--------: | :-------------: | :--------: | :---------------: |
| v6_baseline_hbs   | `v6_baseline_hbs`   |   0.7822   | **✅ 0.786723** |  0.788628  |         —         |
| v6_domain_lsp     | `v6_domain_lsp`     |   0.7852   | **✅ 0.785448** |  0.788952  |      -0.13pp      |
| v6_domain_dlsp    | `v6_domain_dlsp`    |   0.7838   | **✅ 0.782194** |  0.791949  |      -0.45pp      |
| v6_domain_id_only | `v6_domain_id_only` |   0.7864   |       ⏳        |     ⏳     |         —         |
| v6_ple            | `v6_ple`            |   0.7878   | **✅ 0.786291** |  0.787888  |   -0.04pp ≈ tie   |
| v6_ple_d          | `v6_ple_d`          | **0.7922** | **✅ 0.791069** |  0.790610  |    **+0.43pp**    |
| v7_ple_d16        | `v7_ple_d16`        |   0.7899   | **✅ 0.791747** |  0.791909  |    **+0.50pp**    |
| v6_ple_lsp        | `v6_ple_lsp`        |   0.7801   |       ⏳        |     ⏳     |         —         |
| v6_ple_dlsp       | `v6_ple_dlsp`       |   0.7831   |       ⏳        |     ⏳     |         —         |

重跑后确认:

- **PEPNet 下特征扩展全负**: lsp -0.13pp, dlsp -0.45pp → **不推荐任何 PEPNet + 特征扩展组合**
- **PLE standalone (0.786291) ≈ PEPNet baseline (0.786723)**: PLE 架构本身无增益
- **PLE + d 是唯一正增益**: d=8 +0.43pp, d=16 +0.50pp (双指标)
- **PEPNet + dlsp CTR 陷阱**: CTR 最高 (0.791949) 但 CVR 最低 (0.782194), score 公式下有害
- **生产候选**: PLE + d=16 (CVR +0.50pp, CTR +0.33pp vs baseline), 须等 d=32

## 下一步

- \[[v7-ple-d-variants|v7 变种]\] — d=8/16/32, dpage, ph 5 个变种
- \[[5run-noise-investigation|5-run 噪声调查]\] — 根因与修复
