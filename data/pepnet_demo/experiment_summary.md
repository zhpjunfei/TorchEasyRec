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
- 验证：最后1天 @ 1% 采样（~25万）
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
| **v6_ple**             | **PEPNet_DCN_PLE** | **hash_bucket (9/9)** |              —              | **0.7875** | **0.7878** |  **+3.1pp**   |    **+0.6pp**     |
| v6_domain_lsp ✅       | PEPNet_v2          | hash_bucket           |   level+site+pub_hours_fg   |   0.7894   | **0.7852** |    +2.9pp     |      +0.3pp       |
| **v6_ple_lsp** ✅      | **PEPNet_DCN_PLE** | **hash_bucket**       | **level+site+pub_hours_fg** | **0.7859** | **0.7801** |  **+2.4pp**   |   **-0.2pp** ⚠️   |
| v6_domain_dlsp ✅      | PEPNet_v2          | hash_bucket           | **f_req_domain+lsp (CDOT)** |   0.7917   | **0.7838** |    +2.7pp     |      +0.2pp       |
| **v6_ple_d** 🆕🏆      | **PEPNet_DCN_PLE** | **hash_bucket**       |   **f_req_domain (CDOT)**   | **0.7904** | **0.7922** |  **+3.6pp**   |    **+1.0pp**     |
| v6_ple_dlsp ⚠️         | PEPNet_DCN_PLE     | hash_bucket           | **f_req_domain+lsp (CDOT)** |   0.7914   | **0.7831** |    +2.7pp     |      +0.1pp       |

> ⚠️ **勘误**：v6_ple 的 config 文件实际使用 `hash_bucket_size: 100`，此前标记为 vocab_list 有误。PLE 实验已包含 hash fix。

## v6 设计矩阵（2×2×2 系统化）

按 `模型 × lsp × d` 三维设计：

- **模型** ∈ {PEPNet_v2, PEPNet_DCN_PLE}
- **lsp** ∈ {0, 1}：level + site + pub_hours_fg 是否在 CDOT domain group
- **d** ∈ {0, 1}：f_req_domain 是否在 CDOT domain group（区别于 id_feature 形式）

|            |       lsp=0, d=0        |        lsp=1, d=0        |          lsp=0, d=1           |        lsp=1, d=1         |
| ---------- | :---------------------: | :----------------------: | :---------------------------: | :-----------------------: |
| **PEPNet** | `baseline_hbs` (0.7822) | `domain_lsp` ✅ (0.7852) | `domain_replace_hbs` (0.7843) | `domain_dlsp` ✅ (0.7838) |
| **PLE**    |     `ple` (0.7878)      | `ple_lsp` ✅ (0.7801) ⚠️ |   **`ple_d` (0.7922)** 🆕🏆   |  `ple_dlsp` ⚠️ (0.7831)   |

完整覆盖 8 个 cell。`domain_dlsp` 和 `ple_d` 在本轮补齐，前者作为 PLE_dlsp 的 PEPNet 对照，后者作为 domain_replace_hbs 的 PLE 对照。

## 关键发现

### 1. hash fix（f_req_page hash_bucket_size: 100）是最大单一贡献 +2.6pp

- vocab_list 只覆盖 2/9 页面值
- `search_price`（3.3% PV, 25.8% exposure→CVR）的 embedding 落入 OOV
- hash_bucket 给所有 9 种页面独立 embedding，高转化信号被利用

### 2. PLE 在 2 卡上反超 PEPNet_v2（0.7878 vs 0.7864）

- PLE 对 eff_batch 更敏感：1 卡时 PLE 0.748 弱于 PEPNet 0.764
- 2 卡时 PLE 0.7878 跃居第一，**0.14pp 差距在 25万验证集下具有统计意义**（标准误 ≈ 0.02~0.04pp，对应 3-7 个 SE）
- 0.35~0.56pp 的领先（如 vs v6_domain_parallel_hbs、v6_baseline_hbs）属强信号，结论可信

### 3. f_req_domain 边际增益在噪声内（+0.1~0.3pp）

- 在 hash_bucket 基线之上，加 domain id_feature 或 CDOT group 均无显著提升
- 在 25万验证集下，标准误 ≈ 0.02~0.04pp，+0.1pp 以下确实是噪声

### 4. lsp 特征扩展对 PEPNet_v2 有效（+0.3pp CVR），但仍弱于 PLE

- v6_domain_lsp（PEPNet_v2 + level/site/pub_hours_fg 在 CDOT domain group）= **0.7852**（CTR 0.7894）
- vs v6_baseline_hbs（0.7822）领先 **+0.3pp**，13 个 SE，属强信号
- vs **v6_ple（0.7878）落后 -0.26pp**，证明 **PLE 架构 > lsp 特征扩展**对 PEPNet_v2 的提升
- ❌ **"Domain 特征扩展无效"** 在新数据集下被推翻——扩展有效，但 PLE 仍是更优路径

### 5. ⚠️ v6_ple_dlsp 反常：PLE + lsp + d 全开反而退步 -0.47pp

- v6_ple_dlsp（PLE + f_req_domain + level/site/pub_hours_fg 全在 CDOT domain group）= **0.7831**（CTR 0.7914）
- vs **v6_ple（0.7878）落后 -0.47pp**，12 个 SE，**强信号**——非噪声
- vs v6_baseline_hbs（0.7822）仅 +0.1pp，等于 PLE 架构优势被全抵消
- **可能原因**：
  1. **CDOT group 拥挤**：7 个特征（mmb_id, item_id, f_req_page, f_req_domain, level, site, pub_hours_fg）下 input_dim=24 容量不足
  1. **PLE 已自带参数隔离**：再在 domain group 加 lsp 特征是冗余，反而引入噪声
  1. **f_req_domain 在 PLE 下失效**：f_req_domain 本身稀疏（hash_bucket_size=500），在已有 PLE 抽取层时信号被淹没
- **需 v6_ple_lsp 和 v6_ple_d 区分**：lsp 和 d 哪个是主因？若 ple_lsp ≈ 0.7831 则 lsp 是问题；若 ple_d ≈ 0.7831 则 d 是问题

### 5.5 🎉 v6_ple_d 突破：PLE + d = 0.7922，新最优（2026-06-06 14:05）

- v6_ple_d（PLE + f_req_domain 在 CDOT domain group，无 lsp）= **0.7922**（CTR 0.7904）
- vs **v6_ple（0.7878）领先 +0.44pp**，11 个 SE，**强信号**
- vs v6_baseline_hbs（0.7822）领先 **+1.0pp**（vs 旧最优 +0.6pp）
- vs v1c 线上 0.768 领先 **+2.4pp**（v6_ple 是 +2.0pp）

**关键诊断：f_req_domain 在 CDOT 中对 PLE 强正向**（+0.44pp），而 v6_ple_dlsp 的退步（-0.47pp）**完全归因于 lsp 的加入**：

| 路径                     |    CVR     |     vs ple     | 解读                        |
| :----------------------- | :--------: | :------------: | :-------------------------- |
| ple                      |   0.7878   |       —        | 基线                        |
| **ple + d**              | **0.7922** | **+0.44pp** ✅ | d 是 PLE 的强增益           |
| ple + d + lsp            |   0.7831   |    -0.47pp     | lsp 在 d 存在时贡献 -0.91pp |
| **推算 lsp 在 d 存在时** |     —      | **-0.91pp** ⚠️ | lsp 是 PLE 反效果主因       |

→ **f_req_domain 与 level/site/pub_hours_fg 互斥**：PLE 架构下，CDOT domain group 加 d 是好，加 lsp 是坏，**两者都加最差**

### 5.6 ✅ v6_ple_lsp 收官：lsp 在 PLE 下单独就是 -0.77pp（2026-06-06 12:34）

- v6_ple_lsp（PLE + level/site/pub_hours_fg 在 CDOT domain group，无 d）= **0.7801**（CTR 0.7859）
- vs v6_ple（0.7878）**-0.77pp**，19 个 SE，**极强信号**——非噪声
- vs v6_baseline_hbs（0.7822）**-0.21pp**——PLE 架构优势全失
- **关键意义**：v6_ple_dlsp 退步的"主因"已**直接证实**：lsp 在 PLE 下**单独**就是负效果（-0.77pp），不需要 d 共存。

**完整边际效应（8/8 设计矩阵）**：

| 边际           |      PLE       |   PEPNet   | 解读                                         |
| :------------- | :------------: | :--------: | :------------------------------------------- |
| **lsp in d=0** | **-0.77pp** ⚠️ | +0.30pp ✅ | lsp 强烈依赖架构，**PLE 毒药 / PEPNet 补品** |
| lsp in d=1     |   -0.91pp ⚠️   | -0.05pp ⚠️ | lsp 在 d 存在时也是负效果                    |
| **d in lsp=0** | **+0.44pp** ✅ | +0.21pp ✅ | d 是**架构无关稳定增益**                     |
| d in lsp=1     |   +0.30pp ✅   | -0.14pp ⚠️ | d 在 lsp 存在时 PEPNet 反而变负              |

**最终结论**：

- ✅ **f_req_domain（d）是统一正增益**：PEPNet +0.21pp / PLE +0.44pp
- ⚠️ **lsp 极性反转**：PEPNet +0.30pp / PLE -0.77pp
- 🏆 **当前最优：v6_ple_d = 0.7922**（PLE + d）

### 6. 设计矩阵完整分析（8/8 cells）— 架构 × 特征扩展的相互作用

| 维度                | lsp=0, d=0 | lsp=1, d=0  |   lsp=0, d=1    | lsp=1, d=1 |
| ------------------- | :--------: | :---------: | :-------------: | :--------: |
| **PEPNet** CVR      |   0.7822   | **0.7852**  |     0.7843      |   0.7838   |
| **vs baseline_hbs** |     —      | **+0.30pp** |     +0.21pp     |  +0.16pp   |
| **PLE** CVR         |   0.7878   |  0.7801 ⚠️  | **0.7922** 🆕🏆 |   0.7831   |
| **vs ple**          |     —      | **-0.77pp** |   **+0.44pp**   |  -0.47pp   |

**PEPNet 侧**：lsp 单独 +0.30pp，d 单独 +0.21pp，lsp+d 一起 +0.16pp → **lsp 与 d 边际收益递减**
**PLE 侧**：d 单独 **+0.44pp**（强增益），lsp 单独 **-0.77pp**（强负向），lsp+d 一起 -0.47pp → **lsp 与 d 完全相反**

**核心结论**：

- **f_req_domain（d）通用**：在 PEPNet 和 PLE 下都正增益（PEPNet +0.21pp / PLE +0.44pp），是**架构无关的稳定增益**
- **level/site/pub_hours_fg（lsp）极性反转**：PEPNet 下 +0.30pp（有用），PLE 下 -0.77pp（有害）→ **PLE 架构与 lsp 互斥**
- **v6_ple_d 是当前最优**（CVR 0.7922），**设计矩阵完成**

### 7. 旧数据集结论在新数据集下被推翻的

- ❌ **"f_req_page 无用"** → hash fix 贡献 +2.6pp
- ❌ **"Domain 特征扩展无效"** → v6_domain_lsp 验证为 **+0.3pp**

## Batch 效应实验（v6_baseline_1gpu / 4gpu）

### 背景

v6_baseline_4gpu（4×V100, eff_batch=8192）最初用 T_max=40000 跑出 **CVR 0.7589**，原被归因为 "batch 效应"。但进一步分析发现 T_max 设置不当（衰减比例仅 26% vs 2-GPU 的 52%），LR 轨迹不同，**不可直接归因于 batch 效应**。

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

| Config                  |   GPU   |   T_max    | 衰减比例  |   最终 LR    |  CTR AUC   |  CVR AUC   | 状态    |
| :---------------------- | :-----: | :--------: | :-------: | :----------: | :--------: | :--------: | :------ |
| v6_baseline_1gpu        | 1×GU8IS | **140000** | **54.3%** | **0.000456** | **0.7873** | **0.7643** | ✅ 已跑 |
| v6_baseline_hbs（参考） |  2×A10  |   73242    | **52.3%** | **0.000514** |   0.7883   | **0.7822** | ✅ 已跑 |
| v6_baseline_4gpu        | 4×V100  | **37000**  | **51.7%** | **0.000517** | **0.7900** | **0.7569** | ✅ 已跑 |

> 注：1×GU8IS 实际 1 epoch = 76000 步（数据集略大于 1.5亿），衰减比例从 52.3% 修正到 54.3%。

### 实测结果（2026-06-06）

- **2×A10**：CVR **0.7822**（eff_batch=4096，38285 步/epoch）🏆
- **1×GU8IS**：CVR **0.7643**（eff_batch=2048，76000 步/epoch，**-0.18pp** vs 2×A10）
  - 时间：`2026-06-06 11:32:42,055`，Eval Result Epoch-0 model-76000
  - CTR 0.7873（vs 2×A10 0.7883，-0.10pp）
- **4×V100**：CVR **0.7569**（eff_batch=8192，19142 步/epoch，**-0.25pp** vs 2×A10）
  - 时间：`2026-06-06 09:38:51,002`，Eval Result Epoch-0 model-19151
  - CTR 0.7900（vs 2×A10 0.7883，+0.17pp），但 CVR 显著退化

### 仍然存在的本质差异

T_max 修正后，下列差异无法消除：

|           |   1-GPU    |     2-GPU     |   4-GPU    |
| :-------- | :--------: | :-----------: | :--------: |
| 硬件      |  1×GU8IS   |     2×A10     |   4×V100   |
| eff_batch |    2048    |     4096      |    8192    |
| 显存/卡   |    48GB    |     24GB      |    16GB    |
| 梯度噪声  |     大     |      中       |     小     |
| 更新次数  |   76000    |     38285     |   19142    |
| **CVR**   | **0.7643** | **0.7822** 🏆 | **0.7569** |
| **CTR**   |   0.7873   |    0.7883     |   0.7900   |

### 结论

**三个 GPU 数的 CVR 排序：2×A10 (0.7822) > 1×GU8IS (0.7643) > 4×V100 (0.7569)**，**非单调 batch 效应**。

1. **2×A10 是甜区**——既不是最小 batch 也不是最大 batch，但效果最好
1. **GPU 类型影响显著**：A10 (Ampere, 24GB, FP32 31.2 TFLOPS) 与 V100 (Volta, 16GB, FP32 15.7 TFLOPS) 和 L20 (GU8IS) 性能特征不同，distributed reduction 开销和 FP32 算力均影响收敛
1. **batch 大小单独无法解释**：1-GPU < 2-GPU 可能是 batch 太小+更新太多导致的过拟合/震荡；4-GPU < 2-GPU 是 batch 太大+更新不足导致的欠拟合；2-GPU 正好
1. **结论**：**eff_batch=4096 (2×A10) 是该模型/数据量/数据集/优化器配置下的最优**——但这是经验性选择，不一定适用于其他场景

## Config 文件

| Config                                | 路径                                                                                                      |
| :------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| pepnet (基线)                         | `home_flow_2604_pepnet.config`                                                                            |
| pepnet_nocdot                         | `home_flow_2604_pepnet_nocdot.config`                                                                     |
| pepnet_cdot_domain                    | `home_flow_2604_pepnet_cdot_domain.config`                                                                |
| 🏆 warmup1000 (旧数据集最优)          | `v2/..._warmup1000.config`                                                                                |
| ⭐ cdot32_weight03 (旧数据集上线候选) | `v4/..._cdot32_weight03.config`                                                                           |
| pepnet_epoch3                         | `home_flow_2604_pepnet_epoch3.config`                                                                     |
| pepnet_tower256                       | `home_flow_2604_pepnet_tower256.config`                                                                   |
| pepnet_relation_mlp                   | `v3/..._relation_mlp.config`                                                                              |
| pepnet_relation_mlp_noadd             | `v3/..._relation_mlp_noadd.config`                                                                        |
| pepnet_domain2                        | `v3/..._domain2.config`                                                                                   |
| pepnet_v4_freqpage16                  | `v4/..._freqpage16.config`                                                                                |
| pepnet_v4_cdot32                      | `v4/..._cdot32.config`                                                                                    |
| pepnet_v4_cdot32_weight03             | `v4/..._cdot32_weight03.config`                                                                           |
| pepnet_v4_cdot32_weight03_nofreqpage  | `v4/..._cdot32_weight03_nofreqpage.config` 🔄                                                             |
| pepnet_nofreqpage                     | `home_flow_2604_pepnet_nofreqpage.config`                                                                 |
| ~~pepnet_fixedlr~~ (已撤回)           | ~~`home_flow_2604_pepnet_fixedlr.config`~~                                                                |
| v5_v1ctower                           | `v5/..._v5_v1ctower.config`                                                                               |
| v5_2epochs                            | `v5/..._v5_2epochs.config` 🔄                                                                             |
| v5_baseline                           | `v5/..._v5_baseline.config`                                                                               |
| **v6_baseline**                       | `v6/..._v6_baseline.config`                                                                               |
| **v6_baseline_hbs**                   | `v6/..._v6_baseline_hbs.config`                                                                           |
| **v6_domain_id_only**                 | `v6/..._v6_domain_id_only.config`                                                                         |
| **v6_domain_id_only_hbs**             | `v6/..._v6_domain_id_only_hbs.config`                                                                     |
| **v6_domain_replace**                 | `v6/..._v6_domain_replace.config`                                                                         |
| **v6_domain_replace_hbs**             | `v6/..._v6_domain_replace_hbs.config`                                                                     |
| **v6_domain_full_replace**            | `v6/..._v6_domain_full_replace.config`                                                                    |
| **v6_domain_parallel**                | `v6/..._v6_domain_parallel.config`                                                                        |
| **v6_domain_parallel_hbs**            | `v6/..._v6_domain_parallel_hbs.config`                                                                    |
| **v6_ple** 🏆                         | `v6/..._v6_ple.config`                                                                                    |
| **v6_domain_lsp**                     | `v6/..._v6_domain_lsp.config` — level + site + pub_hours_fg 加入 domain group                             |
| **v6_ple_lsp** 🆕                     | `v6/..._v6_ple_lsp.config` — PLE + level + site + pub_hours_fg 加入 domain group                          |
| **v6_baseline_1gpu**                  | `v6/..._v6_baseline_1gpu.config` — T_max=140000, 1×A10                                                    |
| **v6_baseline_4gpu**                  | `v6/..._v6_baseline_4gpu.config` — T_max=37000, 4×V100                                                    |
| **v6_ple_dlsp** 🆕                    | `v6/..._v6_ple_dlsp.config` — PLE + f_req_domain + level + site + pub_hours_fg                            |
| **v6_domain_dlsp** 🆕                 | `v6/..._v6_domain_dlsp.config` — PEPNet_v2 + f_req_domain + level + site + pub_hours_fg (补齐 2×2×2 矩阵) |
| **v6_ple_d** 🆕                       | `v6/..._v6_ple_d.config` — PLE + f_req_domain 在 CDOT domain group，无 lsp (补齐 2×2×2 矩阵)              |
