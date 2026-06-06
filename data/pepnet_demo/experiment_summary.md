# PEPNet_v2 实验结果汇总

## 数据集说明

本项目经历了两套完全不同的训练数据，**结论不可跨数据集直接引用**：

| 阶段                      | 数据集      | 样本量 | 说明                                                    |
| :------------------------ | :---------- | :----: | :------------------------------------------------------ |
| **旧数据集**（exp #1-23） | 53天负采样  | ~530万 | 2026-05 实验，v1c 线上 CVR 0.768                        |
| **新数据集**（v6 实验）   | 7天无负采样 | ~1.5亿 | 2026-06 实验，7天训练+1天 1% 验证，v1c 线上 CVR 约 0.77 |

______________________________________________________________________

# 旧数据集实验（53天负采样，~530万）

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

## 第五阶段：瓶颈诊断

| #   | Config   | 基干            | 变化                      |  CTR AUC  |  CVR AUC  | 说明                    |
| --- | -------- | --------------- | ------------------------- | :-------: | :-------: | ----------------------- |
| 22  | v1ctower | cdot32_weight03 | tower → [128,64,32]       | **0.695** | **0.742** | ❌ 排除 tower 过参数化  |
| 23  | 2epochs  | cdot32_weight03 | num_epochs=2, T_max=12655 |  过拟合   |  过拟合   | ❌ 第2个 epoch AUC 下降 |

### v1c 基线（旧数据集）

| 模型                        |  CTR AUC   |  CVR AUC   |
| --------------------------- | :--------: | :--------: |
| v1c (DBMtl_DCNv2) 线上      | **0.690**  | **0.768**  |
| PEPNet_v2 (warmup1000) 最佳 |   0.694    |   0.742    |
| 差距                        | **+0.4pp** | **-2.6pp** |

### 旧数据集关键结论

1. **DCNv2 有效** — cross_num=4, low_rank=256，CDOT domain + DCNv2 比纯 nocdot 高 +0.7pp CTR, +0.4pp CVR
1. **CDOT all 无用，CDOT domain 有用**
1. **cvr_add_ctr_logits 必开** — 关闭掉 0.5pp CVR
1. **relation_mlp 有独立作用（+0.5pp），但与 cvr_add_ctr 冗余**
1. **Domain 特征扩展无效**（旧数据集下）
1. **f_req_page 无用**（旧数据集下，负采样 530 万，结论不适用于新数据集）
1. **搜索样本降权 0.3 有效**
1. **1 epoch 最优**，**warmup 有效**，**cosine LR > constant_lr**

______________________________________________________________________

# v6 新数据集实验（7天 ~1.5亿，2×A10 统一 GPU 数）

## 数据集

- 训练：7天（~1.5亿 PV）
- 验证：最后1天 @ 1% 采样（~5万）
- 标签：is_click + is_conversion（CVR 正样本 ~170万）
- 采样：保留负样本，DISTRIBUTE BY RAND * 10000 控制 reducer

## 统一条件

- **batch_size: 2048 为 per-GPU**，2×A10 下 eff_batch = 4096
- **T_max=73242, warmup=2000, save_checkpoints_steps=1000, num_epochs=1**
- 2 卡 steps/epoch ≈ 38285（cosine 衰减到约 52% epoch）
- AdamW weight_decay 0.01 作用于 dense MLP `.weight` + `cdot.sub_compress_weight`

## 结果全景

| Config                 | 模型               | f_req_page            |         额外 domain         |  CTR AUC   |  CVR AUC   | Δ v6_baseline | Δ v6_baseline_hbs |
| :--------------------- | ------------------ | --------------------- | :-------------------------: | :--------: | :--------: | :-----------: | :---------------: |
| v6_baseline            | PEPNet_v2          | vocab_list (2/9)      |              —              |   0.7880   | **0.7566** |       —       |      −2.6pp       |
| v6_baseline_hbs        | PEPNet_v2          | hash_bucket (9/9)     |              —              |   0.7883   | **0.7822** | **+2.6pp** 🎯 |         —         |
| v6_domain_id_only_hbs  | PEPNet_v2          | hash_bucket           |  f_req_domain (id_feature)  |   0.7928   | **0.7832** |    +2.7pp     |      +0.1pp       |
| v6_domain_id_only      | PEPNet_v2          | vocab_list            |  f_req_domain (id_feature)  |   0.7909   | **0.7864** |    +3.0pp     |      +0.4pp       |
| v6_domain_parallel_hbs | PEPNet_v2          | hash_bucket           |  f_req_domain (CDOT group)  |   0.7918   | **0.7843** |    +2.8pp     |      +0.2pp       |
| **v6_ple** 🏆          | **PEPNet_DCN_PLE** | **hash_bucket (9/9)** |              —              | **0.7875** | **0.7878** |  **+3.1pp**   |    **+0.6pp**     |
| v6_domain_lsp          | PEPNet_v2          | hash_bucket           |   level+site+pub_hours_fg   |     —      |     —      |    🔄 待跑    |        🔄         |
| **v6_ple_lsp** 🆕      | **PEPNet_DCN_PLE** | **hash_bucket**       | **level+site+pub_hours_fg** |     —      |     —      |  **🔄 待跑**  |      **🔄**       |

> ⚠️ **勘误**：v6_ple 的 config 文件实际使用 `hash_bucket_size: 100`，此前标记为 vocab_list 有误。PLE 实验已包含 hash fix。

## 关键发现

### 1. hash fix（f_req_page hash_bucket_size: 100）是最大单一贡献 +2.6pp

- vocab_list 只覆盖 2/9 页面值
- `search_price`（3.3% PV, 25.8% exposure→CVR）的 embedding 落入 OOV
- hash_bucket 给所有 9 种页面独立 embedding，高转化信号被利用

### 2. PLE 在 2 卡上反超 PEPNet_v2（0.7878 vs 0.7864）

- PLE 对 eff_batch 更敏感：1 卡时 PLE 0.748 弱于 PEPNet 0.764
- 2 卡时 PLE 0.7878 跃居第一，差距 0.14pp 在噪声内

### 3. f_req_domain 边际增益在噪声内（+0.1~0.3pp）

- 在 hash_bucket 基线之上，加 domain id_feature 或 CDOT group 均无显著提升

### 4. 旧数据集结论在新数据集下被推翻的

- ❌ **"f_req_page 无用"** → hash fix 贡献 +2.6pp
- ❌ **"Domain 特征扩展无效"** → 新数据集下需重新验证（v6_domain_lsp 待跑）

## Batch 效应实验（v6_baseline_1gpu / 4gpu）

### 背景

v6_baseline_4gpu（4×V100, eff_batch=8192, T_max=40000）在 epoch-0 step-19151 跑出 **CVR 0.7589**。这个结果原被归因为 "batch 效应"，但进一步分析发现 **T_max 设置不当**是主要原因。

### 问题：T_max 未对齐导致 LR 轨迹不同

所有 v6 标准实验固定 T_max=73242。但不同 GPU 数 steps/epoch 不同：

| GPU | eff_batch | steps/epoch | T_max=73242 时衰减 | 最终 LR |
| :-- | --------: | :---------: | :----------------: | :-----: |
| 1   |      2048 |    73242    |        100%        | 0.00010 |
| 2   |      4096 |    38285    |       52.3%        | 0.00051 |
| 4   |      8192 |    19142    |       26.1%        | 0.00086 |

三个 GPU 数的 LR 轨迹完全不同，**无法单独归因于 batch 效应**。

### 修复：对齐 cosine 衰减比例

目标：让不同 GPU 数在 epoch 结束时衰减到相同位置（52.3%，对齐 2-GPU）：

```python
T_max_Ngpu = steps_per_epoch_Ngpu / 0.523
```

| Config                  |    GPU |   T_max    | 衰减比例  |   最终 LR    |
| :---------------------- | -----: | :--------: | :-------: | :----------: |
| v6_baseline_1gpu        |  1×A10 | **140000** | **52.3%** | **0.000514** |
| v6_baseline_hbs（参考） |  2×A10 |   73242    | **52.3%** | **0.000514** |
| v6_baseline_4gpu        | 4×V100 | **37000**  | **51.7%** | **0.000517** |

### 仍然存在的本质差异

T_max 修正后，下列差异无法消除：

|           | 1-GPU | 2-GPU | 4-GPU |
| :-------- | ----: | :---: | :---: |
| eff_batch |  2048 | 4096  | 8192  |
| 梯度噪声  |    大 |  中   |  小   |
| 更新次数  | 73242 | 38285 | 19142 |

如果修正后 1-GPU 或 4-GPU CVR 仍低于 2-GPU (0.7822)，才说明 **eff_batch=4096 是该模型/数据量下的最优平衡点**，batch 效应真实存在。

## Config 文件

| Config                                | 路径                                                                             |
| :------------------------------------ | -------------------------------------------------------------------------------- |
| pepnet (基线)                         | `home_flow_2604_pepnet.config`                                                   |
| pepnet_nocdot                         | `home_flow_2604_pepnet_nocdot.config`                                            |
| pepnet_cdot_domain                    | `home_flow_2604_pepnet_cdot_domain.config`                                       |
| 🏆 warmup1000 (旧数据集最优)          | `v2/..._warmup1000.config`                                                       |
| ⭐ cdot32_weight03 (旧数据集上线候选) | `v4/..._cdot32_weight03.config`                                                  |
| pepnet_epoch3                         | `home_flow_2604_pepnet_epoch3.config`                                            |
| pepnet_tower256                       | `home_flow_2604_pepnet_tower256.config`                                          |
| pepnet_relation_mlp                   | `v3/..._relation_mlp.config`                                                     |
| pepnet_relation_mlp_noadd             | `v3/..._relation_mlp_noadd.config`                                               |
| pepnet_domain2                        | `v3/..._domain2.config`                                                          |
| pepnet_v4_freqpage16                  | `v4/..._freqpage16.config`                                                       |
| pepnet_v4_cdot32                      | `v4/..._cdot32.config`                                                           |
| pepnet_v4_cdot32_weight03             | `v4/..._cdot32_weight03.config`                                                  |
| pepnet_v4_cdot32_weight03_nofreqpage  | `v4/..._cdot32_weight03_nofreqpage.config` 🔄                                    |
| pepnet_nofreqpage                     | `home_flow_2604_pepnet_nofreqpage.config`                                        |
| ~~pepnet_fixedlr~~ (已撤回)           | ~~`home_flow_2604_pepnet_fixedlr.config`~~                                       |
| v5_v1ctower                           | `v5/..._v5_v1ctower.config`                                                      |
| v5_2epochs                            | `v5/..._v5_2epochs.config` 🔄                                                    |
| v5_baseline                           | `v5/..._v5_baseline.config`                                                      |
| **v6_baseline**                       | `v6/..._v6_baseline.config`                                                      |
| **v6_baseline_hbs**                   | `v6/..._v6_baseline_hbs.config`                                                  |
| **v6_domain_id_only**                 | `v6/..._v6_domain_id_only.config`                                                |
| **v6_domain_id_only_hbs**             | `v6/..._v6_domain_id_only_hbs.config`                                            |
| **v6_domain_replace**                 | `v6/..._v6_domain_replace.config`                                                |
| **v6_domain_replace_hbs**             | `v6/..._v6_domain_replace_hbs.config`                                            |
| **v6_domain_full_replace**            | `v6/..._v6_domain_full_replace.config`                                           |
| **v6_domain_parallel**                | `v6/..._v6_domain_parallel.config`                                               |
| **v6_domain_parallel_hbs**            | `v6/..._v6_domain_parallel_hbs.config`                                           |
| **v6_ple** 🏆                         | `v6/..._v6_ple.config`                                                           |
| **v6_domain_lsp**                     | `v6/..._v6_domain_lsp.config` — level + site + pub_hours_fg 加入 domain group    |
| **v6_ple_lsp** 🆕                     | `v6/..._v6_ple_lsp.config` — PLE + level + site + pub_hours_fg 加入 domain group |
| **v6_baseline_1gpu**                  | `v6/..._v6_baseline_1gpu.config` — T_max=140000, 1×A10                           |
| **v6_baseline_4gpu**                  | `v6/..._v6_baseline_4gpu.config` — T_max=37000, 4×V100                           |
| **v6_ple_dlsp** 🆕                    | `v6/..._v6_ple_dlsp.config` — PLE + f_req_domain + level + site + pub_hours_fg   |
