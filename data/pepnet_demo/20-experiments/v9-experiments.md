______________________________________________________________________

## date: 2026-06-10 tags: \[[experiment, v9, ple-d16, tower-depth, search-weight]\] related: \["\[[v8-experiments]\]", "\[[v6-design-matrix]\]", "\[[v7-ple-d-variants]\]", "\[[../10-architecture/pepnet-dcn-ple]\]"\]

# v9 实验 — 解决 PLE+d16 全天效果衰减

> v9 pipeline 与 v8 一致（v1c 编码, v1 SQL 60d+30d归因）. 以 v8 最优 config（v8_ple_d16_4gpu, PLE+d16, 4卡, T_max=6700）为基线. 所有实验 4卡, batch_size=4096/GPU, 有效=16384. T_max=6700/warmup=1000. 单变量改动.

## 背景

v8 PLE+d16_4gpu AUC 最高（CVR +0.88pp, CTR +0.54pp vs 2GPU baseline），但 A/B 小时级数据发现效果从早上到晚上依次下降，晚上退化为 baseline。根因：

1. **Tower 太浅** [128,64] vs v4 [512,256,128] — 扛不住分布漂移
1. **缺少 search_weight** — 非搜索流量降权，v4 有此机制
1. **CDOT input_dim=16** — 比 v4 的 32 小，域交互能力弱

## 实验清单

| 排行 | 实验          | Config                                   | 变化                                       |   CVR    |   CTR    |  ΔCVR   |  ΔCTR   | 综合Δ |
| :--: | :------------ | :--------------------------------------- | :----------------------------------------- | :------: | :------: | :-----: | :-----: | :---: |
|  1   | sota          | `home_flow_2604_v9_sota.config`          | deep_tower + search_weight + cdot32        | 0.746528 | 0.702565 | +0.17pp | -0.01pp | 0.16  |
|  2   | cdot32        | `home_flow_2604_v9_cdot32.config`        | cdot input_dim: 16→32                      | 0.746390 | 0.702538 | +0.16pp | -0.01pp | 0.15  |
|  3   | search_weight | `home_flow_2604_v9_search_weight.config` | CVR + search_weight                        | 0.745536 | 0.702555 | +0.07pp | -0.01pp | 0.06  |
|  4   | baseline      | `home_flow_2604_v9_baseline.config`      | v8_ple_d16_4gpu (对照)                     | 0.744839 | 0.702668 |    —    |    —    |   —   |
|  5   | deep_tower    | `home_flow_2604_v9_deep_tower.config`    | tower: [512,256,128], ppnet: [512,256,128] | 0.744907 | 0.702282 | +0.01pp | -0.04pp | -0.03 |

> Δ 均 vs v9 baseline（v8_ple_d16_4gpu）

## 结论

1. **CDOT input_dim 32 最有效** — 单变量 CVR +0.16pp，是三项改动中唯一显著提升。域交互维度增加后，domain-specific 特征（f_req_domain）的利用效率更高。
1. **Tower 加深无效** — deep_tower CVR +0.01pp, CTR -0.04pp，综合Δ=-0.03。说明 PLE 提取网络（[512→256] + [256→128]）已提供足够的层次深度，塔本身的容量不是瓶颈。
1. **search_weight 小幅提升 CVR** — +0.07pp，说明非搜索流量降权对 CVR 有正向作用但有限。
1. **SOTA 综合最优** — CVR +0.17pp，但相比 cdot32 单变量仅边际改善 +0.01pp。主要贡献来自 cdot32。
1. **全天效果衰减是否解决仍需 A/B 验证** — off-line AUC 无法衡量时间分布漂移的鲁棒性。建议用 sota config 推 A/B，观察小时级曲线是否更平缓。

## Config 结构差异

| 维度          | baseline  | deep_tower    | search_weight | cdot32    | sota          |
| ------------- | --------- | ------------- | ------------- | --------- | ------------- |
| Tower MLP     | [128,64]  | [512,256,128] | [128,64]      | [128,64]  | [512,256,128] |
| PpNet         | [256,128] | [512,256,128] | [256,128]     | [256,128] | [512,256,128] |
| CDOT dim      | 16        | 16            | 16            | 32        | 32            |
| search_weight | ✗         | ✗             | ✓             | ✗         | ✓             |
| T_max         | 6700      | 6700          | 6700          | 6700      | 6700          |
| GPU           | 4         | 4             | 4             | 4         | 4             |
