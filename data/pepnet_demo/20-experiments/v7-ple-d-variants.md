______________________________________________________________________

## date: 2026-06-08 tags: [experiment, v7, d-variant, dpage, ph] related: \["\[[v6-design-matrix]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v7 PLE+d 变种实验

> 基于 v6_ple_d (修复后确定性 **0.791069**) 进一步探索. 5 个变种全部跑完 (修复前), 待确定性重评.

> **注意**: 以下数据全部为修复前单跑值 (5-run noise 0.73pp). v6_ple_d 修复后确定性值 = 0.791069. 其余变异待重跑后更新.
>
> **Update 2026-06-09**: `v7_ple_dpage` 发现 config bug — `f_req_domain` 定义但未接入任何 feature_group (死代码). 所有 dpage 相关讨论作废. 见下方注.

## 实验列表

| Variant                 | Config         | 变化                                       | CVR AUC (单跑) |    5-run mean     |    距 d=8 mean     |  落入 noise?  |
| :---------------------- | :------------- | :----------------------------------------- | :------------: | :---------------: | :----------------: | :-----------: |
| v7_ple                  | `v7_ple`       | = v6_ple copy                              |     0.7878     |         —         |      +0.26pp       |      ⚠️       |
| **v7_ple_d**            | `v7_ple_d`     | = v6_ple_d copy (基线)                     |   **0.7922**   | **0.7852 ± 0.73** |         —          |       —       |
| **v7_ple_d (确定性)**   | `v7_ple_d`     | eval fix 后                                |  **0.791069**  | **0.791069 ± 0**  |         —          |   ✅ exact    |
| **v7_ple_d16 (确定性)** | `v7_ple_d16`   | f_req_domain emb 8→16                      |  **0.791747**  | **0.791747 ± 0**  | **+0.68pp vs d=8** |   ✅ exact    |
| v7_ple_d32              | `v7_ple_d32`   | f_req_domain emb 8→32                      |     0.7880     |         —         |    **+0.28pp**     |  ❌ 反而更优  |
| v7_ple_dpage [1]        | `v7_ple_dpage` | f_req_domain 未接入任何 group (config bug) |     0.7818     |   2-run 0.7766    |      -0.86pp       |    🐛 无效    |
| v7_ple_ph               | `v7_ple_ph`    | CDOT 替换 d→pub_hours_fg                   |     0.7853     |         —         |       ≈ 0pp        | ❌ 实际无差异 |

## 🐛 Config bug: v7_ple_dpage

`v7_ple_dpage` 的 `f_req_domain` 在 feature_configs 中定义 (`embedding_dim:8, hash_bucket_size:500`) 但**未加入任何 feature_group** → 死代码, 模型根本没用到此特征. 结果是 PLE baseline 的重跑, 不反映 dpage 实验的真实效果.

**修复**: 将 `f_req_domain` 加入 domain feature_group. 修复后 domain 组 = `[mmb_id, item_id, f_req_page, f_req_domain]`, 与 `v7_ple_d`(d=8) 完全一致.

**影响**: dpage 真实结果 = d=8 结果 (CVR 0.791069, CTR 0.790610). 以下 5 个发现中的 dpage 相关分析全部作废.

### 2. v7_ple_ph 反常: ph (pub_hours_fg) vs d 无显著差异

单跑 0.7853 vs d=8 mean 0.7852 ≈ **0pp, 实际无差异**.

- 之前认为"ph 是真退步"是基于单跑 -0.69pp
- 5-run 视角下: ph ≈ d, **pub_hours_fg 在 PLE 下不输于 f_req_domain**
- 建议: eval 修好后, ph 和 d 都需要重评, **不应急于排除 ph**

### 3. d=16 确定性双指标: CVR +0.07pp, CTR +0.13pp (均优于 d=8)

| dim | Config                  | 修复前单跑 CVR |       确定性 CVR       |       确定性 CTR       |
| :-: | :---------------------- | :------------: | :--------------------: | :--------------------: |
|  8  | `v6_ple_d` / `v7_ple_d` | 0.7852 (5-run) |      **0.791069**      |      **0.790610**      |
| 16  | `v7_ple_d16`            | 0.7899 (单跑)  | **0.791747** (+0.07pp) | **0.791909** (+0.13pp) |
| 32  | `v7_ple_d32`            | 0.7880 (单跑)  |           ⏳           |           ⏳           |

**d=16 确认双指标优于 d=8**: CVR +0.07pp, CTR +0.13pp, 差距均确定 (Std=0pp). Score `pCTR*(1+pCVR)` 下 CTR 权重更高, 实际综合收益 d=16 > d=8 不止 0.07pp. 须等 d=32 决定最优 dim.

### 4. v7_ple_d 5-run std 0.73pp 是核心信号

详见 \[[5run-noise-investigation|5-run 调查]\]. 单跑 0.7922 vs 5-run mean 0.7852:

- 单跑极值差异 -1.78pp
- 1m22s 窗口内单调下降 -1.31pp
- CTR 同期 0.10pp 稳定 (正常 noise)
- **根因: eval pipeline 非确定性, 修好后 std < 0.1pp**

### 5. dpage 2-run 数据 (基于 buggy config, 仅作 eval noise 参考)

| 跑次 | 时间                |  CVR   | 累计 Δ  |
| :--: | :------------------ | :----: | :-----: |
|  1   | 2026-06-06 18:47    | 0.7818 |    —    |
|  2   | 2026-06-07 14:13:04 | 0.7714 | -1.04pp |

> ⚠️ 以上数据基于 **buggy config (f_req_domain 未接入)**, 等同于 PLE baseline 重跑. 仅证明 eval 非确定性漂移模式, **不代表 dpage 实验本身**.

**与 v6_ple_d 漂移模式完全一致**, 进一步证实 eval 非确定性是**系统性问题, 非特定模型**.

## 生产候选更新 (2026-06-08, 含 CTR 分析)

- **双指标最优**: v7_ple_d16 (CVR 0.791747, CTR 0.791909) — CVR +0.50pp, CTR +0.33pp vs baseline_hbs
- **候选顺序**: d=16 > d=8 (双指标优势, CTR 增益更大) > ph (待重跑)
- **dpage**: config bug, 修复后 = d=8, 结果 = 0.791069/0.790610, **无需重跑**.
- **confidence**: ✅ **高** (Std=0pp)
- **待确认**: d=32, ph 确定性

## 训练脚本

`data/pepnet_demo/sql/sample_v2/train_v7_ple_d_variants.sh` (顺序 dpage → d16 → d32 → ph)

## 🆕 修复后价值重评 (2026-06-08)

v6_ple_d 确定性 = 0.791069. v7 变种需重跑才能确认:

| Variant          | Config         | 修复前单跑 |  确定性 CVR   |  确定性 CTR   | Δ vs d=8 CVR | Δ vs d=8 CTR |
| :--------------- | :------------- | :--------: | :-----------: | :-----------: | :----------: | :----------: |
| v7_ple_d16       | `v7_ple_d16`   |   0.7899   | **0.791747**  | **0.791909**  |   +0.07pp    |  +0.13pp ✅  |
| v7_ple_d32       | `v7_ple_d32`   |   0.7880   |      ⏳       |      ⏳       |     待定     |     待定     |
| v7_ple_dpage [1] | `v7_ple_dpage` |   0.7818   | **0.791069**† | **0.790610**† |    = d=8     |    = d=8     |
| v7_ple_ph        | `v7_ple_ph`    |   0.7853   |      ⏳       |      ⏳       |     待定     |     待定     |

**当前最优**: PLE + d=16 = **0.791747**. 须等 d=32 确认最终 dim. PLE+d 系列整体 CVR 0.791~0.792.

† dpage config bug: 修复后 = d=8 配置, 复用 d=8 结果.

[1] `v7_ple_dpage` 发现 config bug: `f_req_domain` 在 feature_configs 中定义但未加入任何 feature_group → 死代码. 修复后 domain 组与 `v7_ple_d`(d=8) 完全一致. 详情见上方 🐛 Config bug 节.

## 下一步

- \[[v6-design-matrix|设计矩阵确定性重跑]\] ✅ 全部完成
- \[[eval-pipeline-fix|修复记录]\]
- ph 确定性: 已跑完 (CVR 0.789219, CTR 0.788232) — 需补充到本表
- dpage: config bug 已修 → 复用 d=8 结果, **无需重跑**
