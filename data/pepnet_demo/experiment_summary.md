# PEPNet_v2 实验结果汇总

## 第一阶段：结构探索

| #   | Config                   |  CDOT  | DCNv2 | cvr_add_ctr | Tower | Epoch |  CTR AUC  |  CVR AUC  | 说明             |
| --- | ------------------------ | :----: | :---: | :---------: | :---: | :---: | :-------: | :-------: | ---------------- |
| 1   | pepnet                   |  all   |  ❌   |    true     |  512  |   1   |   0.685   |   0.736   | 基线             |
| 2   | pepnet_nocdot            |   ❌   |  ❌   |    true     |  512  |   1   |   0.686   |   0.736   | CDOT all 无用    |
| 3   | pepnet_nocdot_noadd      |   ❌   |  ❌   |    false    |  512  |   1   |     —     |   0.731   | cvr_add_ctr 必开 |
| 4   | pepnet_tower256          |  all   |  ❌   |    true     |  256  |   1   |   略差    |   略差    | 小 tower 弱      |
| 5   | pepnet_epoch3            |  all   |  ❌   |    true     |  512  |   3   |   0.658   |   0.704   | 3 epoch 过拟合   |
| 6   | pepnet_cdot_domain       | domain |  ❌   |    true     |  512  |   1   |   0.690   |   0.739   | CDOT domain 有效 |
| 7   | pepnet_cdot_domain_dcnv2 | domain |   ✓   |    true     |  512  |   1   | **0.693** | **0.740** | 🏆 原最佳        |

## 第二阶段：超参数微调

| #   | Config            | 变化                      | CTR AUC |  CVR AUC  |
| --- | ----------------- | ------------------------- | :-----: | :-------: |
| 8   | cross2            | cross_num=2, low_rank=128 |  0.693  |   0.740   |
| 9   | gamma1            | ppnet_gamma=1.0           |  0.694  |   0.741   |
| 10  | warmup1000        | warmup_size=1000          |  0.694  | **0.742** |
| 11  | warmup1000_gamma1 | warmup=1000 + gamma=1.0   |  0.693  | **0.742** |
| 12  | warmup1000_lr5e4  | warmup=1000 + lr=5e-4     |  0.692  |   0.742   |
| 13  | warmup1500        | warmup_size=1500          |  0.693  |   0.740   |

## 第三阶段：结构补全

| #   | Config             | 变化                          | CTR AUC | CVR AUC | 说明                                            |
| --- | ------------------ | ----------------------------- | :-----: | :-----: | ----------------------------------------------- |
| 14  | relation_mlp       | CVR 加 relation_mlp           |  0.694  |  0.741  | −0.1pp，持平 baseline                           |
| 15  | relation_mlp_noadd | relation_mlp + 关 cvr_add_ctr |  0.694  |  0.736  | +0.5pp vs nocdot_noadd，relation_mlp 有独立作用 |
| 16  | domain2            | domain + page + KV            |  0.693  |  0.741  | −0.1pp，domain 特征扩展无效                     |

## 第四阶段：数据扩展

| #   | Config                     | 变化                                               | CTR AUC | CVR AUC | 说明                                                |
| --- | -------------------------- | -------------------------------------------------- | :-----: | :-----: | --------------------------------------------------- |
| 17  | freqpage16                 | f_req_page emb=16 + 全page数据                     |  0.696  |  0.739  | ❌ CTR +0.2pp 但 CVR -0.3pp，不可接受               |
| 18  | cdot32                     | freqpage16 + f_req_page emb=32 + cdot input_dim=32 |  0.696  |  0.740  | ❌ 比 freqpage16 CVR +0.1pp，但仍差 baseline -0.2pp |
| 19  | nofreqpage                 | 去掉 f_req_page（只用原始数据）                    |  0.693  |  0.741  | ➖ ±0pp，f_req_page 删掉无影响                      |
| 20  | cdot32_weight03            | cdot32 + 搜索样本降权 0.3                          |  0.696  |  0.742  | ✅ CTR +0.2pp, CVR ±0pp，大幅优于 freqpage16        |
| 21  | cdot32_weight03_nofreqpage | weight03 + 去掉 f_req_page                         |    —    |    —    | 🔄 运行中                                           |

### v1c 基线

| 模型                        |  CTR AUC   |  CVR AUC   |
| --------------------------- | :--------: | :--------: |
| v1c (DBMtl_DCNv2) 线上      | **0.690**  | **0.768**  |
| PEPNet_v2 (warmup1000) 最佳 |   0.694    |   0.742    |
| 差距                        | **+0.4pp** | **-2.6pp** |

## 第五阶段：瓶颈诊断

| #   | Config   | 基干            | 变化                      |  CTR AUC  |  CVR AUC  | 说明                    |
| --- | -------- | --------------- | ------------------------- | :-------: | :-------: | ----------------------- |
| 22  | v1ctower | cdot32_weight03 | tower → [128,64,32]       | **0.695** | **0.742** | ❌ 排除 tower 过参数化  |
| 23  | 2epochs  | cdot32_weight03 | num_epochs=2, T_max=12655 |  过拟合   |  过拟合   | ❌ 第2个 epoch AUC 下降 |

## 🔴 之前结论有误（2026-06-01 更新）

### 背景

之前声称 "constant_lr 从 0.74162 提升到 0.76970" 的结论是 **confounded**：

| 配置                             | LR 策略      | weight_decay |   CVR AUC    |
| -------------------------------- | ------------ | :----------: | :----------: |
| 集群 pepnet.config（含 wd=0.01） | cosine       |   ✅ 0.01    |   0.74162    |
| 集群 pepnet.config + constant_lr | constant     |    ❌ 无     | **0.76970**  |
| **本地 pepnet.config**           | **cosine**   |  **❌ 无**   |  **0.742**   |
| **本地 pepnet_fixedlr.config**   | **constant** |  **❌ 无**   | **0.730** ❌ |

本地 pepnet.config（cosine, 无 wd）→ CVR 0.742。仅改 constant_lr → **CVR 0.730，反而降了 1.2pp**。

0.76970 的实验同时改了两个变量（cosine→constant + 去掉 wd=0.01），无法归因于 constant_lr。且该实验在集群版本上运行，与本地的 pepnet.config 版本不同。

### 当前结论

```
当前基线 pepnet.config（cosine LR，无 weight_decay）
  CTR AUC = 0.693
  CVR AUC = 0.742 ✅ 最优

pepnet_fixedlr（constant_lr 0.001，无 weight_decay）
  CTR AUC = 0.694
  CVR AUC = 0.730 ❌ 更差
```

**cosine LR 在当前配置下优于 constant_lr（0.742 vs 0.730）。之前的所有关于 "CVR gap 是 LR 问题" 的结论均已推翻。**

### 经验教训

- **变量隔离**：比较 cosine vs constant 时，必须保持 weight_decay / part_optimizers 不变
- **基线确认**：local config 和 cluster config 的版本差异导致 0.76970 不可复现
- **单变量原则**：一个实验只改一个变量

## 关键结论（已修正）

1. **DCNv2 有效** — cross_num=4, low_rank=256，CDOT domain + DCNv2 比纯 nocdot 高 +0.7pp CTR, +0.4pp CVR
1. **CDOT all 无用，CDOT domain 有用** — domain group 信号干净，CDOT 能学到东西
1. **cvr_add_ctr_logits 必开** — 关闭掉 0.5pp CVR
1. **relation_mlp 有独立作用（+0.5pp），但与 cvr_add_ctr 冗余** — 单独开 +0.5pp，叠加后 0pp
1. **Domain 特征扩展无效** — 加 page + KV 特征、加 f_req_page 均无变化
1. **f_req_page 无用** — 去掉后 CTR/CVR 均不变（0.693/0.741），CDOT domain 只用 mmb_id + item_id 即可
1. **搜索样本降权 0.3 有效** — 全量搜索数据导致 CVR -0.3pp，降权到 0.3 后 CVR 恢复（0.742），CTR 仍 +0.2pp。embedding 受益 + tower 保护 = 双赢
1. **1 epoch 最优** — 3 epoch 过拟合严重 (CTR 0.658, CVR 0.704)
1. **warmup 有效** — 500→1000 带来 +0.2pp
1. **cosine LR > constant_lr** — 当前基线无 weight_decay 时 cosine（0.742）优于 constant（0.730）
1. ~~CVR 2.8pp 差距根因 LR 太低~~ → ❌ **推翻**：confounded 结论，不可复现
1. ~~架构性差距~~ → ❌ **推翻但未替代**：CVR gap（0.742 vs 0.768）根因仍未知

## 综合最优配置（待验证）

基于 constant_lr 的新基线，配置待定。以下为候选：

```
CDOT:       domain (mmb_id, item_id)
DCNv2:      cross_num=4, low_rank=256
Bias:       domain
LHUC:       domain
cvr_add_ctr: true
Tower:      [512, 256, 128], PPNet gamma=2.0
LR:         0.001 (constant)
Weight decay: 无 (对齐 v1c)
```

## 最终结论（2026-06-01 更新）

### 23 组实验结论

PEPNet_v2 在 warmup1000 + cvr_add_ctr 下达到当前最优：**CTR 0.694 / CVR 0.742**。
v1c 基线 CVR **0.768** 高出 **2.6pp**。根因仍未知。

### ⚠️ confounded 结论撤回

之前的 "CVR gap 是 LR 问题" 结论基于 confounded 对比（同时改了 LR 和 weight_decay），且 cluster/local config 版本不一致导致的不可复现结果。已撤回。

### 当前状态

| 配置                          |  CVR AUC  |              状态              |
| ----------------------------- | :-------: | :----------------------------: |
| pepnet.config（cosine LR）    | **0.742** |          ✅ 当前最优           |
| pepnet_fixedlr（constant_lr） |   0.730   | ❌ 更差，confounded 结论已撤回 |
| v1c（DBMtl_DCNv2）线上        | **0.768** |            ⭐ 目标             |

### v6 计划

基于 f_req_domain 数据分析，验证 domain 粒度特征对 CVR 的影响。同时修复 f_req_page 编码缺陷（vocab_list 仅覆盖 2/9 page→hash_bucket_size）。

两维度交叉 = 10 configs：

| #   | Config                 | f_req_domain 用法                 |  f_req_page 编码   | 目的                        |
| --- | ---------------------- | --------------------------------- | :----------------: | --------------------------- |
| 1   | v6_baseline            | 无（对照）                        |     vocab_list     |                             |
| 2   | v6_baseline_hbs        | 无                                |  hash_bucket_size  | f_req_page 修复本身有无影响 |
| 3   | v6_domain_id_only      | id_feature 仅模型用               |     vocab_list     |                             |
| 4   | v6_domain_id_only_hbs  | id_feature 仅模型用               |  hash_bucket_size  |                             |
| 5   | v6_domain_replace      | domain group 替换 f_req_page      |     vocab_list     |                             |
| 6   | v6_domain_replace_hbs  | domain group 替换 f_req_page      |  hash_bucket_size  |                             |
| 7   | v6_domain_full_replace | 完全替换 f_req_page（id+group）   | —（无 f_req_page） |                             |
| 8   | v6_domain_parallel     | 与 f_req_page 并行在 domain group |     vocab_list     |                             |
| 9   | v6_domain_parallel_hbs | 与 f_req_page 并行在 domain group |  hash_bucket_size  |                             |

（详见 `v6/` 目录）

## Config 文件

| Config                               | 路径                                                                          |
| ------------------------------------ | ----------------------------------------------------------------------------- |
| pepnet (基线)                        | `home_flow_2604_pepnet.config`                                                |
| pepnet_nocdot                        | `home_flow_2604_pepnet_nocdot.config`                                         |
| pepnet_cdot_domain                   | `home_flow_2604_pepnet_cdot_domain.config`                                    |
| 🏆 warmup1000 (最优 AUC)             | `v2/..._warmup1000.config`                                                    |
| ⭐ cdot32_weight03 (上线候选)        | `v4/..._cdot32_weight03.config`                                               |
| pepnet_epoch3                        | `home_flow_2604_pepnet_epoch3.config`                                         |
| pepnet_tower256                      | `home_flow_2604_pepnet_tower256.config`                                       |
| pepnet_relation_mlp                  | `v3/..._relation_mlp.config`                                                  |
| pepnet_relation_mlp_noadd            | `v3/..._relation_mlp_noadd.config`                                            |
| pepnet_domain2                       | `v3/..._domain2.config`                                                       |
| pepnet_v4_freqpage16                 | `v4/..._freqpage16.config`                                                    |
| pepnet_v4_cdot32                     | `v4/..._cdot32.config`                                                        |
| pepnet_v4_cdot32_weight03            | `v4/..._cdot32_weight03.config`                                               |
| pepnet_v4_cdot32_weight03_nofreqpage | `v4/..._cdot32_weight03_nofreqpage.config` 🔄                                 |
| pepnet_nofreqpage                    | `home_flow_2604_pepnet_nofreqpage.config`                                     |
| ~~pepnet_fixedlr~~ (已撤回)          | ~~`home_flow_2604_pepnet_fixedlr.config`~~                                    |
| v5_v1ctower                          | `v5/..._v5_v1ctower.config` — CTR 0.695 / CVR 0.742                           |
| v5_2epochs                           | `v5/..._v5_2epochs.config` 🔄                                                 |
| v5_baseline                          | `v5/..._v5_baseline.config`                                                   |
| **v6_baseline**                      | `v6/..._v6_baseline.config`                                                   |
| **v6_baseline_hbs**                  | `v6/..._v6_baseline_hbs.config`                                               |
| **v6_domain_id_only**                | `v6/..._v6_domain_id_only.config`                                             |
| **v6_domain_id_only_hbs**            | `v6/..._v6_domain_id_only_hbs.config`                                         |
| **v6_domain_replace**                | `v6/..._v6_domain_replace.config`                                             |
| **v6_domain_replace_hbs**            | `v6/..._v6_domain_replace_hbs.config`                                         |
| **v6_domain_full_replace**           | `v6/..._v6_domain_full_replace.config`                                        |
| **v6_domain_parallel**               | `v6/..._v6_domain_parallel.config`                                            |
| **v6_domain_parallel_hbs**           | `v6/..._v6_domain_parallel_hbs.config`                                        |
| **v6_domain_lsp**                    | `v6/..._v6_domain_lsp.config` — level + site + pub_hours_fg 加入 domain group |
