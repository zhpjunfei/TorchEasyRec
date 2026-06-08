______________________________________________________________________

## date: 2026-06-08 tags: [experiment, v7, d-variant, dpage, ph] related: \["\[[v6-design-matrix]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v7 PLE+d 变种实验

> 基于 v6_ple_d (修复后确定性 **0.791069**) 进一步探索. 5 个变种全部跑完 (修复前), 待确定性重评.

> **注意**: 以下数据全部为修复前单跑值 (5-run noise 0.73pp). v6_ple_d 修复后确定性值 = 0.791069. 其余变异待重跑后更新.

## 实验列表

| Variant               | 变化                     | CVR AUC (单跑) |    5-run mean     | 距 d=8 mean |  落入 noise?  |
| :-------------------- | :----------------------- | :------------: | :---------------: | :---------: | :-----------: |
| v7_ple                | = v6_ple copy            |     0.7878     |         —         |   +0.26pp   |      ⚠️       |
| **v7_ple_d**          | = v6_ple_d copy (基线)   |   **0.7922**   | **0.7852 ± 0.73** |      —      |       —       |
| **v7_ple_d (确定性)** | eval fix 后              |  **0.791069**  | **0.791069 ± 0**  |      —      |   ✅ exact    |
| v7_ple_d16            | f_req_domain emb 8→16    |     0.7899     |         —         | **+0.47pp** |  ❌ 反而更优  |
| v7_ple_d32            | f_req_domain emb 8→32    |     0.7880     |         —         | **+0.28pp** |  ❌ 反而更优  |
| v7_ple_dpage          | CDOT 移除 f_req_domain   |     0.7818     |   2-run 0.7766    |   -0.86pp   |  ⚠️ 接近 1x   |
| v7_ple_ph             | CDOT 替换 d→pub_hours_fg |     0.7853     |         —         |    ≈ 0pp    | ❌ 实际无差异 |

## 5 个关键发现 (单跑, 5-run noise 0.73pp 下)

### 1. v7_ple_dpage 反常: dpage < d 不是单纯"f_req_domain 必须 in CDOT"

单跑 0.7818 vs v6_ple 0.7878 = -0.60pp (反常).

- 2-run 重跑 0.7818 → 0.7714 (-1.04pp), 进一步证实是 noise
- 2-run mean 0.7766 vs d=8 mean 0.7852 = -0.86pp, **接近 1x noise (0.73pp)**
- **结论**: dpage 真实退步可能只有 -0.5~0pp, 远小于单跑 -0.95pp

### 2. v7_ple_ph 反常: ph (pub_hours_fg) vs d 无显著差异

单跑 0.7853 vs d=8 mean 0.7852 ≈ **0pp, 实际无差异**.

- 之前认为"ph 是真退步"是基于单跑 -0.69pp
- 5-run 视角下: ph ≈ d, **pub_hours_fg 在 PLE 下不输于 f_req_domain**
- 建议: eval 修好后, ph 和 d 都需要重评, **不应急于排除 ph**

### 3. d=16/32 反而更优 (单跑视角)

| dim |      单跑      | 距 d=8 mean |
| :-: | :------------: | :---------: |
|  8  | 0.7852 (5-run) |      —      |
| 16  | 0.7899 (单跑)  | **+0.47pp** |
| 32  | 0.7880 (单跑)  | **+0.28pp** |

之前认为"d=32 真退步", 5-run 视角下 d=32 反而 +0.28pp.

- **d=8 不一定是 sweet spot**, 需重评
- 推测: 8 维对 f_req_domain 500 hash bucket 容量可能略低

### 4. v7_ple_d 5-run std 0.73pp 是核心信号

详见 \[[5run-noise-investigation|5-run 调查]\]. 单跑 0.7922 vs 5-run mean 0.7852:

- 单跑极值差异 -1.78pp
- 1m22s 窗口内单调下降 -1.31pp
- CTR 同期 0.10pp 稳定 (正常 noise)
- **根因: eval pipeline 非确定性, 修好后 std < 0.1pp**

### 5. v7_ple_dpage 2-run 重跑 -1.04pp 证实系统性

| 跑次 | 时间                |  CVR   | 累计 Δ  |
| :--: | :------------------ | :----: | :-----: |
|  1   | 2026-06-06 18:47    | 0.7818 |    —    |
|  2   | 2026-06-07 14:13:04 | 0.7714 | -1.04pp |

**与 v6_ple_d 漂移模式完全一致**, 进一步证实 eval 非确定性是**系统性问题, 非特定模型**.

## v7 阶段生产决策 (暂定)

- **生产候选**: v7_ple_d (= v6_ple_d), dim=8, f_req_domain in CDOT ⚠️ d=16/d=32 修复前均值更高, 待确定性重评 dim 选择
- **confidence**: ✅ **高** (确定性 Std=0pp, 4× bitwise identical)
- **✅ 已验证**: v6_ple_d 确定性真实值 = **0.791069**. 变体待重跑
- **d=16/32 重新评估**: ⏳ 待确定性重跑判断

## 训练脚本

`data/pepnet_demo/sql/sample_v2/train_v7_ple_d_variants.sh` (顺序 dpage → d16 → d32 → ph)

## 🆕 修复后价值重评 (2026-06-08)

v6_ple_d 确定性 = 0.791069. v7 变种需重跑才能确认:

| Variant      | 修复前单跑 | 待确定性重跑 | 推测                 |
| :----------- | :--------: | :----------: | :------------------- |
| v7_ple_d16   |   0.7899   |      ⏳      | d=16 vs d=8 真实差距 |
| v7_ple_d32   |   0.7880   |      ⏳      | d=32 vs d=8 真实差距 |
| v7_ple_dpage |   0.7818   |      ⏳      | dpage 真实退步量     |
| v7_ple_ph    |   0.7853   |      ⏳      | ph vs d 真实差异     |

**当前最佳候选**: PLE + d=8 (f_req_domain in CDOT) = 0.791069. d=16/32 修复前值偏高 (可能落入 noise), 不能断定更优.

## 下一步

- \[[v6-design-matrix|设计矩阵确定性重跑]\]
- \[[eval-pipeline-fix|修复记录]\]
- 重跑 v7 变种 (d16, d32, dpage, ph)
