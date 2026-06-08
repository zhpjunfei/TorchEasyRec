______________________________________________________________________

## date: 2026-06-08 tags: [experiment, v6, design-matrix, 2x2x2] related: \["\[[v7-ple-d-variants]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

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

## v6_ple_d 确定性结果 (修复后, 2026-06-08)

> 修复后 4 次重跑 bitwise identical, Std=0pp.

| 架构    | 特征扩展 | CVR AUC (确定性) |        Δ vs 修复前         | 备注          |
| :------ | :------- | :--------------: | :------------------------: | :------------ |
| **PLE** | **d**    |   **0.791069**   | **-0.11pp vs 单跑 0.7922** | 🏆 确定性真值 |

**关键影响**:

- 修复前 5-run mean 0.7852 有系统性低估偏差 -0.59pp (vs 真值 0.791069)
- 修复前单跑 0.7922 高估 +0.11pp (落入 0.73pp noise 上限)
- 修复后 exact 0.791069, 无需多跑

**其余 7 个 cells 待确定性重跑** (见下方 #v6 确定性重跑指南)

## 5 个关键发现

### 1. hash_fix (f_req_page hash_bucket_size=100) 是最大单一贡献 +2.6pp

之前 f_req_page 用 `vocab_list` 误配, 改 `hash_bucket_size: 100` 后 CVR +2.6pp 单次. 修后 v6_ple 已含此 fix.

### 2. PLE 在 2 卡上反超 PEPNet_v2 (0.7878 vs 0.7864)

PLE (ExtractionNet) CGC 路由 + 多任务共享, 在 2×A10 上比 PEPNet_v2 浅层架构更优 +0.14pp 单次.

### 3. f_req_domain 边际增益在噪声内 (+0.1~0.3pp)

5-run 视角下, d 的 +0.21~0.44pp 落入 0.73pp noise, 显著性减弱. **修后需重评**.

### 4. lsp 特征扩展对 PEPNet_v2 有效 (+0.30pp CVR), 但仍弱于 PLE

lsp (Layer-Sensitive Personalization) 在 PEPNet 架构下正增益, 但在 PLE 下极性反转. 原因可能是 PLE 已建模类似信息.

### 5. v6_ple_dlsp 反常: PLE + lsp + d 全开反而退步 -0.47pp

PLE + lsp (0.7801) + d → 0.7831, 介于 lsp 和 d 之间. 推测 lsp 拖累主导.

### 5.5 v6_ple_d 突破: PLE + d = 0.7922, 新最优 (2026-06-06 14:05)

PLE + f_req_domain 单独组合最优. **生产候选锁定**.

### 5.6 v6_ple_lsp 收官: lsp 在 PLE 下单独就是 -0.77pp (2026-06-06 12:34)

v6_ple_lsp 0.7801 vs v6_ple 0.7878 = -0.77pp. 极性反转主因 = lsp 与 PLE 路由冲突.

## 旧数据集结论被推翻 (v6 起换 7d 数据)

之前结论 (53-day 负采样数据集, v1c 基线):

- v1c 0.768 vs PEPNet 0.742 = **2.6pp 架构差距**

新结论 (7-day 无负采样, v6_ple_d):

- v6_ple_d 0.7852 vs v1c 0.768 = **+1.7pp 离线优势**

推翻原因: 数据集不同 (53d neg-sample vs 7d no-neg-sample), 见 \[[../30-data/sql-attribution-30d-vs-24h|sql 归因差异]\].

## v6 确定性重跑指南 (eval fix 已验证)

修后完全确定性 Std=0pp, 每实验**只跑 1 次即可** (每次 eval ~3.7s):

| 实验              |  修复前值  |   确定性重跑    |
| :---------------- | :--------: | :-------------: |
| v6_baseline_hbs   |   0.7822   |       ⏳        |
| v6_ple            |   0.7878   |       ⏳        |
| v6_ple_d          | **0.7922** | **✅ 0.791069** |
| v6_ple_lsp        |   0.7801   |       ⏳        |
| v6_ple_dlsp       |   0.7831   |       ⏳        |
| v6_domain_lsp     |   0.7852   |       ⏳        |
| v6_domain_dlsp    |   0.7838   |       ⏳        |
| v6_domain_id_only |   0.7864   |       ⏳        |

重跑后重新计算:

- lsp 极性反转: PLE + lsp 是否真为负
- d 真实增益: PLE + d 是否稳定优越
- 架构选择: PEPNet vs PLE 确定性差异

## 下一步

- \[[v7-ple-d-variants|v7 变种]\] — d=8/16/32, dpage, ph 5 个变种
- \[[5run-noise-investigation|5-run 噪声调查]\] — 为什么单跑不可信
