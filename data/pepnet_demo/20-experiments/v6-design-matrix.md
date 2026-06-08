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

| 架构    | 特征扩展       | CVR AUC (修复前) | Δ vs base | 备注                        |
| :------ | :------------- | :--------------: | :-------: | :-------------------------- |
| PEPNet  | baseline_hbs   |      0.7822      |     —     | hash_fix baseline ⏳ 待重跑 |
| PEPNet  | domain_id_only |      0.7864      |   +0.42   | ⏳ 待重跑                   |
| PEPNet  | lsp            |      0.7852      |   +0.30   | ⏳ 待重跑                   |
| PEPNet  | dlsp           |      0.7838      |   +0.16   | ⏳ 待重跑                   |
| PEPNet  | dpage          |        —         |     —     | CDOT 移除 d, 退步 ⏳ 待重跑 |
| PLE     | baseline       |      0.7878      |   +0.56   | ⏳ 待重跑                   |
| PLE     | lsp            |      0.7801      |   -0.21   | ⚠️ lsp 极性反转 ⏳ 待重跑   |
| **PLE** | **d**          |    **0.7922**    | **+1.00** | 🏆 修复前最优 ⏳ 重跑\*\*   |
| PLE     | dlsp           |      0.7831      |   +0.09   | ⏳ 待重跑                   |

## 确定性结果 (修复后, 2026-06-08)

> 每实验 1 次, bitwise identical, Std=0pp.

| 架构    | 特征扩展         | CVR AUC (确定性) | Δ vs baseline_hbs | CTR AUC (确定性) |
| :------ | :--------------- | :--------------: | :---------------: | :--------------: |
| PEPNet  | **baseline_hbs** |   **0.786723**   |         —         |     0.788628     |
| PEPNet  | lsp              |     0.785448     |    **-0.13pp**    |     0.788952     |
| PEPNet  | dlsp             |     0.782194     |    **-0.45pp**    |     0.791949     |
| PEPNet  | domain_id_only   |        ⏳        |                   |                  |
| PLE     | baseline         |        ⏳        |                   |                  |
| **PLE** | **d**            |   **0.791069**   |    **+0.43pp**    |     0.790610     |
| PLE     | lsp              |        ⏳        |                   |                  |
| PLE     | dlsp             |        ⏳        |                   |                  |

### 关键影响

- **baseline_hbs 从 0.7822 跳到 0.786723 (+0.45pp)**: 之前踩到 eval 低谷窗口, 导致修复前所有 "Δ vs baseline" 偏正
- **lsp 反转**: 修复前以为 +0.30pp, 实际 **-0.13pp** (lsp 在 PEPNet 下也是负增益)
- **dlsp 反转**: 修复前以为 +0.16pp, 实际 **-0.45pp** (dlsp 显著负增益)
- **v6_ple_d vs baseline_hbs = +0.43pp**: 修复前 0.7922-0.7822=+1.00pp 高估了, 实际 **+0.43pp** (仍在脆弱区间)
- CTR 趋势: baseline_hbs CTR 最低 (0.7886), lsp+dlsp CTR 更高 (0.7890/0.7919) → lsp/dlsp 可能过度优化 CTR 而牺牲 CVR

## 5 个关键发现

### 1. hash_fix (f_req_page hash_bucket_size=100) 是最大单一贡献 +2.6pp

之前 f_req_page 用 `vocab_list` 误配, 改 `hash_bucket_size: 100` 后 CVR +2.6pp 单次. 修后 v6_ple 已含此 fix.

### 2. PLE 在 2 卡上是否有优势 ⏳ 待 v6_ple 重跑

修复前认为 PLE (0.7878) 反超 PEPNet (0.7864), 但 baseline_hbs 确定性值跳到 0.786723, 需等 v6_ple 确定性结果.

### 3. f_req_domain (d) 在 PEPNet 下是负增益 ▸ 需确定性重评估 PLE+d

修复前: PEPNet + d ≈ +0.21pp (单跑). 确定性结果: PEPNet + lsp -0.13pp, PEPNet + dlsp -0.45pp (lsp 和 d 都负). **PEPNet 下特征扩展整体负增益**.

### 4. lsp 在 PEPNet 下也是负增益 (确定性)

| 结论          | 修复前 (单跑) |   确定性    |
| :------------ | :-----------: | :---------: |
| PEPNet + lsp  |    +0.30pp    | **-0.13pp** |
| PEPNet + dlsp |    +0.16pp    | **-0.45pp** |

**之前"lsp 有效"是假象**: baseline 跑在 eval 低谷, lsp 跑在正常点.

### 5. v6_ple_dlsp 需重评

修复前 PLE + lsp + d = 0.7831. 等待 v6_ple/v6_ple_lsp/v6_ple_dlsp 确定性重跑.

### 5.5 v6_ple_d 仍然是最优候选: CVR = 0.791069

PLE + d 确定性 **+0.43pp vs baseline_hbs**. 但比修复前 +1.00pp 保守得多. 仍需等 v6_ple + 变种确定是否 d 是核心贡献.

### 5.6 v6_ple_lsp 极性反转 ⏳ 待重跑

## 旧数据集结论被推翻 (v6 起换 7d 数据)

之前结论 (53-day 负采样数据集, v1c 基线):

- v1c 0.768 vs PEPNet 0.742 = **2.6pp 架构差距**

新结论 (7-day 无负采样, v6_ple_d):

- v6_ple_d 0.7852 vs v1c 0.768 = **+1.7pp 离线优势**

推翻原因: 数据集不同 (53d neg-sample vs 7d no-neg-sample), 见 \[[../30-data/sql-attribution-30d-vs-24h|sql 归因差异]\].

## v6 确定性重跑进度

| 实验              |  修复前值  |     确定性      | Δ vs baseline_hbs |
| :---------------- | :--------: | :-------------: | :---------------: |
| v6_baseline_hbs   |   0.7822   | **✅ 0.786723** |         —         |
| v6_domain_lsp     |   0.7852   | **✅ 0.785448** |      -0.13pp      |
| v6_domain_dlsp    |   0.7838   | **✅ 0.782194** |      -0.45pp      |
| v6_domain_id_only |   0.7864   |       ⏳        |         —         |
| v6_ple            |   0.7878   |       ⏳        |         —         |
| v6_ple_d          | **0.7922** | **✅ 0.791069** |    **+0.43pp**    |
| v6_ple_lsp        |   0.7801   |       ⏳        |         —         |
| v6_ple_dlsp       |   0.7831   |       ⏳        |         —         |

重跑后确认:

- **PEPNet 下特征扩展**: lsp -0.13pp, dlsp -0.45pp → **整体负增益, 不推荐**
- **PLE + d**: +0.43pp vs baseline_hbs, 仍最优候选中
- **PLE baseline**: 待 v6_ple 重跑, 判断 PLE 本身 vs PEPNet

## 下一步

- \[[v7-ple-d-variants|v7 变种]\] — d=8/16/32, dpage, ph 5 个变种
- \[[5run-noise-investigation|5-run 噪声调查]\] — 根因与修复
