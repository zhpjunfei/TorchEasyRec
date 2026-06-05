# PEPNet_v2 推荐排序模型项目

## 项目背景

首页推荐流（Home Feed）是 MMB 电商平台的核心流量入口。推荐系统需要同时优化 **点击率（CTR）** 和 **转化率（CVR）**，采用多任务学习（Multi-Task Learning）框架。

当前线上模型为 **DBMtl_DCNv2（v1c）**，基于 TF 1.12。为技术栈升级和效果优化，在 PyTorch + TorchEasyRec 框架下复现并增强 **PEPNet_v2** 模型。

## 业务场景

| 维度     | 说明                                                                       |
| -------- | -------------------------------------------------------------------------- |
| 平台     | MMB 电商（东南亚/新兴市场）                                                |
| 场景     | 首页推荐流                                                                 |
| 任务     | 多目标排序                                                                 |
| 目标     | 点击率 (CTR) → 转化率 (CVR)                                                |
| 样本     | 53 天训练 / 7 天验证                                                       |
| 特征     | ~100+ 特征（ID类/序列/KV/统计Ratio/Bias）                                  |
| 指标     | AUC（CTR AUC, CVR AUC）                                                    |
| 样本提取 | 3天 (mmb_id, item_id) 聚合去重，每条样本代表3天内一个(user,item)的交互聚合 |

## 项目目标

1. 在 TorchEasyRec（PyTorch）上完成 PEPNet_v2 模型搭建
1. 找到最优超参组合，最大化 **CVR AUC**（CVR 稀疏，优化难度大于 CTR）
1. 与线上 v1c（DBMtl_DCNv2）对齐对比
1. 择优上线 A/B Test

## 模型架构

## 配置变更记录

### 2026-06-04: v6_domain_lsp.config 基于 site/level 分布优化

**变更内容**（`home_flow_2604_v6_domain_lsp.config` vs baseline `home_flow_2604_v6_baseline.config`）：

| 维度                  |          baseline           |                             domain_lsp                             | 原因                                                |
| :-------------------- | :-------------------------: | :----------------------------------------------------------------: | :-------------------------------------------------- |
| `f_req_page` 编码     |   `vocab_list` (2/9覆盖)    |                      `hash_bucket_size: 100`                       | 修复vocab_list bug，使全部9种页面值都有embedding    |
| domain_group 特征     | mmb_id, item_id, f_req_page | mmb_id, item_id, f_req_page, **level**, **site**, **pub_hours_fg** | level/site分布分析显示强CVR区分度                   |
| `level` embedding_dim |              4              |                               **8**                                | click→CVR B(26%)→F(41%)单调递增14.6pp，值得更多容量 |
| `site` 配置           |   emb8 hash410（在all组）   |                    emb8 hash410（移入domain组）                    | site区分度极强（话题0%→京东商城43.93%）             |
| `pub_hours_fg`        |           在all组           |                            移入domain组                            | 发布时间新鲜度影响CTR/CVR，纳入CDOT                 |
| CDOT `input_dim`      |             16              |                               **24**                               | domain信号更丰富，需更大交叉容量                    |
| CDOT `mid_dim`        |             32              |                               **48**                               | 随input_dim等比缩放，保持2× ratio                   |

**不变项**（与baseline完全一致）：

- 所有其他 feature_configs（~100+特征）
- `all` 组特征列表
- PPNet / EPNet / DCNv2 参数
- Task tower MLP 结构
- optimizer / LR schedule / batch_size

**f_req_page 处理说明**：切换为 `hash_bucket_size: 100` 后，所有9种页面值（含此前OOV的search_price等）都有独立embedding slot。虽然 exp#19 表明 f_req_page 自身 AUC 贡献 ≈ 0，但修复编码后可作为 domain group 中的控制变量，与 level/site 的交叉仍有参考价值。

______________________________________________________________________

## PEPNet_v2 模型结构

### PEPNet_v2

```
Features → Embedding
  ├── main_group (all) → LN ──────────────┐
  ├── cdot_group (domain) → CDOT → LN     ├── concat → deep_input
  ├── bias_group (domain) → Bias → LN     │
  └── dcnv2_group (all) → CrossV2 → LN ───┘
                                              ↓
  lhuc_group (domain) → LHUC-EPNet → scale → deep_input *= scale
                                              ↓
  CTR Tower (LHUC-PPNet) ───────────────────→ logit_ctr ──→ probs_ctr
  CVR Tower (LHUC-PPNet) ── + CTR logits ──→ logit_cvr ──→ probs_cvr
```

#### 核心组件

| 组件            | 功能                                           |
| --------------- | ---------------------------------------------- |
| LHUC-EPNet      | domain-level 门控，tanh [-4,6] 缩放 deep_input |
| LHUC-PPNet      | per-layer scale-before-Dense 门控              |
| CDOT            | slot-level 动态特征压缩变换                    |
| Bias            | 每个特征首维 1-dim 偏置                        |
| CrossV2 (DCNv2) | 低秩显式特征交叉                               |
| Component LN    | 每组件独立 LayerNorm 后 concat                 |

## 实验设置

- **框架**: TorchEasyRec 1.2.x, PyTorch 2.11, CUDA 12.9
- **GPU**: NVIDIA A10 (sm_86)
- **训练**: 1 epoch, AdamW, cosine warmup 200
- **Batch**: 4096
- **评估**: step-based (每 500 步)
- **优化器**: AdamW, weight_decay 仅作用 MLP.weight + cdot.sub_compress_weight
- **加速**: Torchrec SPMD 分布式训练
- **v1c 基线**: CTR AUC **0.690** / CVR AUC **0.768** (同 53/7 分片)

## 实验结果汇总

| #   | Config                       |  CDOT   | DCNv2 | Epoch |  CTR AUC  |  CVR AUC  | 说明                                  |
| --- | ---------------------------- | :-----: | :---: | :---: | :-------: | :-------: | ------------------------------------- |
| 1   | pepnet                       |   all   |  ❌   |   1   |   0.685   |   0.736   | 基线                                  |
| 2   | pepnet_nocdot                |   ❌    |  ❌   |   1   |   0.686   |   0.736   | CDOT all 无用                         |
| 3   | pepnet_nocdot_noadd          |   ❌    |  ❌   |   1   |     —     |   0.731   | cvr_add_ctr 必开                      |
| 4   | pepnet_tower256              |   all   |  ❌   |   1   |   略差    |   略差    | 小 tower 弱                           |
| 5   | pepnet_epoch3                |   all   |  ❌   |   3   |   0.658   |   0.704   | 3 epoch 过拟合                        |
| 6   | pepnet_cdot_domain           | domain  |  ❌   |   1   |   0.690   |   0.739   | CDOT domain 有效                      |
| 7   | **pepnet_cdot_domain_dcnv2** | domain  |   ✓   |   1   | **0.693** | **0.740** | 🏆 最优                               |
| 8   | pepnet_relation_mlp          | domain  |   ✓   |   1   |   0.694   |   0.741   | relation_mlp 冗余                     |
| 9   | pepnet_relation_mlp_noadd    | domain  |   ✓   |   1   |   0.694   |   0.736   | relation_mlp +0.5pp（无 cvr_add_ctr） |
| 10  | pepnet_domain2               | domain2 |   ✓   |   1   |   0.693   |   0.741   | domain 特征扩展无效                   |

### v1c 基线

| 模型                        |    CTR AUC     |    CVR AUC     |
| --------------------------- | :------------: | :------------: |
| v1c (DBMtl_DCNv2) 线上      |   **0.690**    |   **0.768**    |
| PEPNet_v2 (warmup1000) 最佳 |     0.694      |     0.742      |
| 差距                        | **+0.4pp CTR** | **-2.6pp CVR** |

PEPNet_v2 CTR 略好但 CVR 差距 2.6pp。当时认为架构性差距，后续被推翻。

## 第五阶段：瓶颈诊断

| #   | Config   | 变化                | CTR AUC | CVR AUC | 说明                      |
| --- | -------- | ------------------- | :-----: | :-----: | ------------------------- |
| 22  | v1ctower | tower → [128,64,32] |  0.695  |  0.742  | ❌ 排除 tower 过参数化    |
| 23  | 2epochs  | num_epochs=2        | 过拟合  | 过拟合  | ❌ 第2个epoch AUC开始下降 |

两个实验基干 v4 cdot32_weight03（CDOT input_dim=32, search_weight=0.3）。

### v5 结论（已推翻）

| 实验     |  CTR   |  CVR   | 结论                                        |
| -------- | :----: | :----: | ------------------------------------------- |
| v1ctower | 0.695  | 0.742  | ❌ Tower 容量不是瓶颈                       |
| 2epochs  | 过拟合 | 过拟合 | ❌ 训练步数不是瓶颈（第2个 epoch AUC 下降） |

当时结论：CVR 2.6pp 差距是架构性的。

### ⚠️ 2026-06-01 更新：之前结论有误

之前对比 pepnet.config（cosine LR）和 constant_lr 版本的结论（CVR 0.76970）是 **confounded**：

| 配置                                 | 变化               |   CVR AUC    |
| ------------------------------------ | ------------------ | :----------: |
| pepnet.config (cosine)               | —                  |    0.742     |
| pepnet_fixedlr (constant_lr 仅改 LR) | cosine→constant_lr | **0.730** ❌ |

同一份数据（无 part_optimizers/weight_decay）上，constant_lr 反而让 CVR 从 0.742 降到了 0.730。0.76970 的结果来自同时改了两个变量（cosine→constant + 去掉 wd=0.01），是 confounded。

**当前基线 pepnet.config 最优**：CTR 0.693 / CVR 0.742。

## 关键发现

### 验证的假设

- ✅ **CDOT all 无用** — 100+ 特征噪声大，CDOT 1 epoch 不收敛
- ✅ **CDOT domain 有用** — 3 个核心特征信号干净，CDOT 学到有效交互
- ✅ **DCNv2 有效** — CrossV2 提供 CDOT 不具备的显式交叉
- ✅ **cvr_add_ctr_logits 必开** — CTR→CVR 信号传递至关重要
- ✅ **relation_mlp 有独立作用，但与 cvr_add_ctr 冗余** — 单独开 +0.5pp CVR，叠加后 0pp
- ❌ **Domain 特征扩展无效** — 加 page + KV 特征后无变化
- ✅ **1 epoch 最优** — CTR 电商场景 1 epoch 后过拟合

### 当前瓶颈

- CVR 2.6pp 差距（PEPNet 0.742 vs v1c 0.768）**原因未完全确定** — constant_lr 误判为万能解，实际上 cosine LR 在当前基线表现更优（0.742 vs 0.730）。
- ~~CVR 2.8pp gap 被 LR 解决~~ → ❌ confounded 结论，已推翻
- ~~架构性差距~~ → 重新评估中
- 🆕 **f_req_domain 特征探索** — v6 实验组：验证 domain 粒度特征是否能缩小 CVR gap

## 后续计划

### v6：f_req_domain 特征探索 + f_req_page 编码修复

基于 `f_req_domain` 的数据分析，同时修复 f_req_page 的 vocab_list 缺陷（仅覆盖 2/9 page）。两维度交叉 = 10 configs：

**f_req_domain 用法（5 种）：**

| #   | variant             | f_req_page id | f_req_page group | f_req_domain id | f_req_domain group |
| --- | ------------------- | :-----------: | :--------------: | :-------------: | :----------------: |
| 1   | baseline            |      ✅       |        ✅        |       ❌        |         ❌         |
| 2   | domain_id_only      |      ✅       |        ✅        |       ✅        |         ❌         |
| 3   | domain_replace      |      ✅       |        ❌        |       ✅        |         ✅         |
| 4   | domain_full_replace |      ❌       |        ❌        |       ✅        |         ✅         |
| 5   | domain_parallel     |      ✅       |        ✅        |       ✅        |         ✅         |

**f_req_page 编码（2 种）：**

- 无后缀: `vocab_list`（原缺陷，只覆盖 2/9 page，OOV → 共享默认 embedding）
- `_hbs`: `hash_bucket_size: 100`（所有 9 个 page 独立 embedding）

组合 = 9 configs（`v6_domain_full_replace` 无 f_req_page 故无 \_hbs 变体），位于 `v6/` 目录。

### 已排除的方向

| 方向            | 原因                                      |
| --------------- | ----------------------------------------- |
| ~~fixedlr~~     | confounded 结论，cosine LR 在当前基线更优 |
| ~~共享 bottom~~ | 已验证非瓶颈                              |
| ~~tower 缩容~~  | 已实验验证无影响                          |

## 数据扩展分析

### 背景

当前模型仅在 `1w_tab_f_index_content`（信息流推荐）和 `1zhekoutuijian`（折购推荐）两个场景提供精排服务。训练数据也只包含这两个场景的样本。

`page_id` 在训练数据中的曝光和转化分布：

| page_id                  |  曝光   |  CTR  | click→CVR | exposure→CVR | 占总量比 | 场景类型  |
| ------------------------ | :-----: | :---: | :-------: | :----------: | :------: | --------- |
| `1w_tab_f_index_content` | 1.11亿  | 37.2% |   30.9%   |    11.5%     |  91.7%   | ✅ 服务中 |
| `search_price`           |  395万  | 48.3% | **53.4%** |  **25.8%**   | **3.3%** | ❌ 未使用 |
| `1zhekoutuijian`         |  132万  | 36.7% |   30.0%   |    11.0%     |   1.1%   | ✅ 服务中 |
| `1yangmao`               |  11万   | 35.7% | **51.9%** |  **18.5%**   |  0.09%   | ❌ 未使用 |
| `2w_tab_f_trend_middle`  |  10万   | 30.5% |   28.9%   |     8.8%     |  0.08%   | ❌ 未使用 |
| `1community`             |  1.7万  | 42.2% |    0%     |      0%      |  0.01%   | ❌ 未使用 |
| 其余小页面               | \<0.5万 | 各异  |   各异    |     各异     | \<0.01%  | ❌ 未使用 |

### 搜索页特征

| 指标             | 推荐流（1w_tab_f_index_content） |      搜索页（search_price）       |
| ---------------- | :------------------------------: | :-------------------------------: |
| 曝光             |              1.11亿              |               395万               |
| UV               |              ~100万              | ~62万（搜索→点击→转化各 UV 不同） |
| CTR              |              37.2%               |          48.3%（+11pp）           |
| **click→CVR**    |            **30.9%**             |       **53.4%（+22.5pp）**        |
| **exposure→CVR** |            **11.5%**             |       **25.8%（+14.3pp）**        |
| 用户每轮曝光数   |              ~109次              |               ~10次               |

搜索页的 CVR（无论是 click-based 还是 exposure-based）都是推荐流的 **2.2x-1.7x**。

### 实验结果

| Config                | 评估集               | CTR AUC |  CVR AUC  |
| --------------------- | -------------------- | :-----: | :-------: |
| warmup1000 (baseline) | 推荐流 only          |  0.694  | **0.742** |
| freqpage16            | 推荐流 + 搜索 + 其他 |  0.696  |   0.739   |

CTR +0.16pp，CVR **-0.34pp**。

### 根因分析

AUC 下降来自两个叠加效应：

#### 效应一：评估集分布偏移

Baseline 的评估集是纯推荐流（96.4% 主场景 + 1.1% 折购），freqpage16 的评估集混入 3.3% 搜索页 + 0.2% 其他 page。不同 page 的 CVR 差异极大：

| Page                   | exposure→CVR | 相对于推荐流 |
| ---------------------- | :----------: | :----------: |
| 1w_tab_f_index_content |    11.5%     |     1.0x     |
| **search_price**       |  **25.8%**   |  **2.24x**   |
| 1yangmao               |    18.5%     |    1.61x     |
| 1community             |      0%      |      0x      |
| 2w_tab_f_trend_middle  |     8.8%     |    0.76x     |

不同曝光→CVR 跨度的样本混在一起评估时，AUC 基率变化。相当于在 100m 短跑比赛中混入马拉松选手——AUC 作为相对排序指标，数字自然不可直接比。

但这只能解释部分偏差。

#### 效应二：CVR tower 参数被污染（主因）

搜索页的 click→CVR = **53.4%**，推荐流仅 **30.9%**，差了 **22.5pp**。

`cvr_add_ctr_logits` 的机制放大了污染：

```
CVR tower: logit_cvr_raw = tower_final(relation_hidden["cvr"])
           logit_cvr = logit_cvr_raw + logit_ctr   # cvr_add_ctr

搜索页:
  - logit_ctr 偏高 (CTR=48% vs 37%)
  - logit_cvr_raw 也偏高 (click→CVR=53% vs 31%)
  - 两者相加 → logit_cvr 被拉高约 30-40%

推荐流:
  - 模型看到搜索样本时，bias 和权重被向上拉
  - 推理推荐流时，同样的特征却产生更高的 logit
  - 推荐流内部的相对序关系被压缩，AUC 下降
```

3.3% 的搜索样本通过 PPNet tower 的共享 bias 和 gate scale 传递污染到所有推荐流预测。

#### 效应三：CTR 微涨解释了 Tower 偏置升高

CTR +0.16pp 说明 tower bias 确实被拉高了——搜索的 48% CTR 带动整体 logit 上升，一部分样本从"不点击"侧进入"点击"侧。CVR 的反向变化说明这种 bias 偏移对 CVR 塔是**有害的**：更高的 CTR logit 叠加到 CVR 后，压缩了 CVR 的相对排序空间。

### 结论

| 方向               |       预期       |           实际            |
| ------------------ | :--------------: | :-----------------------: |
| Embedding 信号增强 |   +0.05~0.15pp   | → CTR +0.16pp ✅ 局部验证 |
| Sigmoid 校准偏移   |      可修正      | → CVR -0.34pp ❌ 不可忽略 |
| Tower 参数拉扯     |   -0.02~0.05pp   |    → -0.34pp ⚠️ 低估了    |
| **净效应**         | **+0.05~0.15pp** |  **CVR -0.34pp ❌ 放弃**  |

**CVR AUC 0.739 vs best 0.742 的差距 ≈ 所有阶段中最差方向之一。搜索页数据的 click→CVR 模式与推荐流差异过大，不适合混入训练。**

### Config 变更

位于 `v4/home_flow_2604_pepnet_v4_freqpage16.config`：

| 变更项                     | 旧值       | 新值                    |
| -------------------------- | ---------- | ----------------------- |
| `f_req_page.embedding_dim` | 4          | 16                      |
| `f_req_page.vocab_list`    | 2 值白名单 | `hash_bucket_size: 100` |

此 config **不再使用**，保留仅作记录。

## 样本提取

当前样本逻辑、问题分析和优化方案详见 `sample_extraction_analysis.md`。

## 特征体系与勘探

完整特征分类、pub_hours 深度分析、SQL 勘验模板见 `feature_exploration_report.md`。

### 特征体系总览

| 类别                   | 举例                                                        |      模型使用      |
| :--------------------- | :---------------------------------------------------------- | :----------------: |
| 基础信息               | item_id, mmb_id, page, scene                                |   ✅ id_feature    |
| 用户画像               | gender, province, app_version, dev_brand                    |   ✅ id_feature    |
| 商品属性               | item_type, brand, cate_id_path, spu_id                      |   ✅ id_feature    |
| 商品价格               | current_price, price_tag, discount_type                     | ✅ id/raw_feature  |
| 商品店铺               | dianpufensi, dianpupingfen, publish_user                    |   ✅ id_feature    |
| 分类层级               | first_cate_id, second_cate_id, third_cate_id                |   ✅ id_feature    |
| 时间特征               | day_h, week_day, pub_hours_fg, reg_days                     | ✅ id/expr_feature |
| 用户统计(15d)          | user\_\_cnt_click_15d, user\_\_cnt_conversion_15d           |   ✅ raw_feature   |
| 用户KV统计(click)      | user\_\_kv_brand_click_15d, user\_\_kv_site_click_15d       | ✅ lookup_feature  |
| 用户KV统计(conversion) | user\_\_kv_brand_conversion_15d                             | ✅ lookup_feature  |
| 用户KV统计(favorite)   | user\_\_kv_brand_favorite_15d                               | ✅ lookup_feature  |
| 物品统计(多窗口)       | first_cate_id\_\_ratio_click_exposure_15d/3d/1d             |   ✅ raw_feature   |
| 交叉统计               | gender\_\_ratio_click_exposure_15d, login_city\_\_ratio\_\* |   ✅ raw_feature   |
| 序列特征               | click_10_seq, conversion_5_seq, favorite_10_seq             | ✅ sequence (DIN)  |
| 标签偏好               | cate_prefer, consume_power, price_prefer                    |   ✅ id_feature    |
| 请求解析               | f_req_page, f_req_domain                                    |   ✅ id_feature    |

### pub_hours 关键发现

`pub_hours_fg` 配置参见 `v6_domain_lsp.config`（expr_feature, emb=8, 20 buckets）。

| 指标     | 值         | 含义                         |
| :------- | :--------- | :--------------------------- |
| P50      | 8.57h      | 50% 商品在曝光前 8.5h 内发布 |
| P75      | 21.59h     |                              |
| P90      | 33.52h     | 90% 在 33.5h 内              |
| P99      | 48.29h     | 建议截断阈值                 |
| CTR 峰值 | 2h (3.79%) | **新品红利**效应             |
| CVR 峰值 | 16-20h     | 用户决策滞后                 |

对 domain group 的价值：发布时间新鲜度影响 user×item 的点击/转化意愿，纳入 CDOT 后帮助 gate 网络学习"新老品"×"用户偏好"的交叉模式。

### pub_hours 处理方案

#### SQL 实现

`fix_sample_v3.sql` 中已有 3 个字段：

| 字段                         | 实现                                        |                用途 |
| :--------------------------- | :------------------------------------------ | ------------------: |
| `pub_hours`                  | `event_unix_time - pub_time` (原始)         | 向后兼容已有 config |
| `pub_hours_aligned`          | `LEAST(pub_time, event_unix_time)` 钳位到 0 |    主特征，对齐线上 |
| `is_reedited_after_exposure` | `IF(pub_time > event_unix_time, 1, 0)`      |        反查样本标记 |

#### LEAST > ABS 方案

|                            | LEAST（钳位到 0） | ABS（取绝对值） |
| :------------------------- | :---------------: | :-------------: |
| 反查样本的离线 `pub_hours` |       **0**       |   2（虚构值）   |
| 线上 `pub_hours`           |       **0**       |   1（值错位）   |
| `is_reedited` 线上生效？   |     ❌ 永远=0     |    ❌ 永远=0    |
| 新品桶(0h)是否被污染？     |    ✅ 略微稀释    |    ❌ 不影响    |

两者 `is_reedited` 线上都为 0，但 ABS 额外导致 `pub_hours` 值在训练/推理间错位。**LEAST 更优**。

#### is_reedited 的角色

不是特征，是**噪声标记（梯度调节器）**：

- 离线训练：告诉模型"这条 `pub_hours=0` 的真实商品更老"，影响梯度方向
- 线上推理：永远 = 0，不生效，模型只依赖正确的 `pub_hours_aligned`
- 类比：`sample_weight` 降权，不是预测信号

不会导致 Training-Serving Skew，因为线上样本根本不触发这个标记。

### 特征优化建议

## 文件清单

| 文件                                                    | 说明                                        |
| ------------------------------------------------------- | ------------------------------------------- |
| `tzrec/models/pepnet_v2.py`                             | PEPNet_v2 模型 (含 DCNv2, CDOT, Bias, LHUC) |
| `tzrec/modules/cdot.py`                                 | CDOT 模块                                   |
| `tzrec/modules/lhuc_net.py`                             | LHUC-EPNet + LHUC-PPNet 模块                |
| `tzrec/modules/interaction.py`                          | CrossV2 (DCNv2) 模块                        |
| `config/home_flow_2604_pepnet.config`                   | 基线配置                                    |
| `config/v6/`                                            | v6 f_req_domain 实验组 (9 configs)          |
| `config/home_flow_2604_pepnet_cdot_domain_dcnv2.config` | 🏆 最优配置                                 |
| `experiment_summary.md`                                 | 实验小结                                    |
| `feature_exploration_report.md`                         | 全量特征体系勘探 + pub_hours 深度分析       |
| `site_mapping.md`                                       | site_e 编码↔站点名映射 (350个)              |

## 数据扩展 Config

| Config                     | 位置                                       | 变更                                                                          |              状态               |
| -------------------------- | ------------------------------------------ | ----------------------------------------------------------------------------- | :-----------------------------: |
| freqpage16                 | `v4/..._freqpage16.config`                 | f_req_page emb=4→16, vocab→hash                                               |             ❌ 放弃             |
| cdot32                     | `v4/..._cdot32.config`                     | freqpage16 + emb=32 + input_dim=32                                            |             ❌ 放弃             |
| nofreqpage                 | `home_flow_2604_pepnet_nofreqpage.config`  | 去掉 f_req_page                                                               |            ➖ 无影响            |
| cdot32_weight03            | `v4/..._cdot32_weight03.config`            | cdot32 + 搜索样本 `weight: 0.3`                                               |      ✅ CVR ±0, CTR +0.2pp      |
| cdot32_weight03_nofreqpage | `v4/..._cdot32_weight03_nofreqpage.config` | weight03 + 去掉 f_req_page                                                    |            🔄 运行中            |
| v5_v1ctower                | `v5/..._v5_v1ctower.config`                | tower [512,256,128] → [128,64,32]                                             | ❌ CTR 0.695 / CVR 0.742 无提升 |
| **pepnet_fixedlr**         | `home_flow_2604_pepnet_fixedlr.config`     | constant_lr + 无 weight_decay（修复 T_max>>steps 问题）                       |       🔄 待验证 CVR~0.768       |
| v5_2epochs                 | `v5/..._v5_2epochs.config`                 | num_epochs 1→2, T_max 6300→12655                                              |            ❌ 过拟合            |
| v5_baseline                | `v5/..._v5_baseline.config`                | cdot32_weight03 移入 v5 作为锚点                                              |                —                |
| 样本提取 v3                | `sql/..._v3.sql`                           | 融合版：保留原表 + ROW_NUMBER 去重 + 30min 点击 + 点击后 24h 转化 + 回看 1 天 |             ✅ 推荐             |

## f_req_domain 特征分析

### 数据来源

`daily_page_domain_distribution.csv` — 单日 24,186,405 条曝光的 f_req_page → f_req_domain 映射分布。

### 核心统计

| 指标                                   | 值        | 含义                                                 |
| -------------------------------------- | --------- | ---------------------------------------------------- |
| unique f_req_page                      | 9         | 粗粒度场景分类                                       |
| unique f_req_domain                    | 203       | 细粒度请求子域                                       |
| 1:1 page→domain 的 page                | 6/9       | 大多数 page 只有 1 个子域，f_req_domain ≈ f_req_page |
| `[1w_tab_f_index_content]` 下的 domain | 193 (95%) | 绝大多数 domain 属于信息流主场景                     |

### PV 分布（极度长尾）

| PV 范围            | domain 数 |   占比   |
| ------------------ | :-------: | :------: |
| < 100              |    42     |  20.7%   |
| < 1,000            |    105    |  51.7%   |
| < 10,000           |    156    |  76.8%   |
| Top 5 domain 覆盖  |  80% PV   | 极度集中 |
| Top 13 domain 覆盖 |  95% PV   |          |

### CTR 分布（domain 级别区分度高）

| 场景                       | page CTR | domain CTR 范围 | 区分度  |
| -------------------------- | :------: | :-------------: | :-----: |
| `[1w_tab_f_index_content]` |  3.70%   |   0% ~ 18.75%   |  ✅ 大  |
| `[search_price]`           |  11.93%  |     11.93%      | ➖ 1:1  |
| 其它 7 page                |   各异   |  与 page 相同   | ❌ 冗余 |

### 关键发现

1. **f_req_domain 高度稀疏** — 51.7% 的 domain PV < 1000，不适合直接加入 CDOT domain group（compress_mlp 会过拟合）
1. **与 f_req_page 冗余** — 6/9 的 page 是 1:1 映射，f_req_domain 在这些场景没有额外信息量
1. **仅在 `[1w_tab_f_index_content]` 内部有价值** — 193 个子 domain 的 CTR 从 0% 到 18.75%，远高于 page 级别的 3.70%
1. **建议方案**：f_req_domain 作为普通 id_feature（emb=8, bucket=500），不加入 CDOT domain group，让 tower MLP 直接利用 domain embedding

## level（帖子质量等级）分布分析

### 数据来源

`level_e` 在 158,408,486 PV / 单日样本中的分布。

### 各等级统计

|   等级   |       PV        |   占比   |    点击PV     |    转化PV     |    CTR    | click→CVR  |  exp→CVR  |   UV    |
| :------: | :-------------: | :------: | :-----------: | :-----------: | :-------: | :--------: | :-------: | :-----: |
|    A1    |     35,375      |   0.0%   |     1,132     |      778      |   3.20%   | **68.73%** |   2.20%   | 23,716  |
|    A2    |     87,011      |   0.1%   |     4,574     |     1,809     | **5.26%** |   39.55%   |   2.08%   | 51,999  |
|    A3    |     431,193     |   0.3%   |    19,527     |     7,499     |   4.53%   |   38.40%   |   1.74%   | 100,981 |
|    A4    |    8,144,534    |   5.1%   |    282,543    |    81,382     |   3.47%   |   28.80%   |   1.00%   | 340,130 |
|    B     |   25,303,856    |  16.0%   |    782,992    |    206,115    | **3.09%** | **26.32%** | **0.81%** | 541,468 |
|    C     |   36,011,932    |  22.7%   |   1,313,247   |    450,341    |   3.65%   |   34.29%   |   1.25%   | 664,085 |
|    D     |   44,045,920    |  27.8%   |   1,572,233   |    585,579    |   3.57%   |   37.25%   |   1.33%   | 745,394 |
|    E     |   22,746,165    |  14.4%   |    802,565    |    316,664    |   3.53%   |   39.46%   |   1.39%   | 683,452 |
|    F     |   21,602,500    |  13.6%   |    983,659    |    402,520    |   4.55%   | **40.92%** | **1.86%** | 787,681 |
| **合计** | **158,408,486** | **100%** | **5,762,472** | **2,052,687** | **3.64%** | **35.62%** | **1.30%** |    —    |

### 数据分布

| 等级 | 累计 PV 占比 |
| :--: | :----------: |
|  A1  |     0.0%     |
|  A2  |     0.1%     |
|  A3  |     0.3%     |
|  A4  |     5.5%     |
|  B   |    21.5%     |
|  C   |    44.2%     |
|  D   |    72.0%     |
|  E   |    86.4%     |
|  F   |    100.0%    |

### 关键发现

1. **A1/A2/A3 不可信** — PV 合计 < 0.5%，click→CVR 波动极大（38%~68%），统计噪声
1. **B 是最差等级** — CTR(3.09%)、click→CVR(26.32%)、exp→CVR(0.81%) 全部最低
1. **转化率从 B→F 单调上升**：click→CVR 26% → 34% → 37% → 39% → 41%，帖子质量越高转化意愿越强
1. **CTR 与等级无单调关系**：CTR 在 3.1%~4.6% 之间波动，不受等级线性影响
1. **对 domain group 的价值**：level 区分不同转化段（B 26% vs F 41%），帮助 CDOT 学习帖子质量×用户交互的交叉模式

## site（请求来源站点）分布分析

### 数据来源

`site_e` 在 158,408,486 PV / 单日样本中的分布（25 个取值）。

### 流量高度集中

|   site   | 站点名       |       PV        |    占比     |    CTR    | click→CVR  |  exp→CVR  |   UV    | 备注                 |
| :------: | :----------- | :-------------: | :---------: | :-------: | :--------: | :-------: | :-----: | :------------------- |
|   366    | 京东自营     |   50,528,268    |  **31.9%**  |   3.76%   |   34.02%   |   1.28%   | 751,126 |                      |
|    1     | 京东商城     |   48,630,663    |  **30.7%**  |   3.51%   | **43.93%** | **1.54%** | 763,245 | **转化率最高**       |
|   278    | 天猫旗舰店   |   21,813,507    |    13.8%    |   3.44%   |   29.44%   |   1.01%   | 651,052 |                      |
|    10    | 天猫商城     |   13,227,633    |    8.4%     | **4.35%** |   30.67%   |   1.33%   | 644,554 | CTR 较高             |
|   190    | 天猫超市     |   10,653,058    |    6.7%     | **2.89%** |   36.65%   |   1.06%   | 350,143 | CTR 最低             |
|    36    | 唯品会       |    4,832,414    |    3.1%     |   2.79%   |   36.51%   |   1.02%   | 395,280 |                      |
|   253    | 天猫国际     |    1,715,693    |    1.1%     |   3.09%   |   26.15%   |   0.81%   | 267,720 |                      |
|    15    | 淘宝         |    1,670,428    |    1.1%     | **4.83%** |   33.90%   | **1.64%** | 344,117 |                      |
|   346    | **话题**     |    1,634,999    |    1.0%     | **6.17%** | **0.00%**  | **0.00%** | 154,415 | **只点不转(内容流)** |
|    54    | 美团         |    1,168,905    |    0.7%     |   2.72%   |   30.77%   |   0.84%   | 162,896 |                      |
|   307    | 拼多多       |     698,236     |    0.4%     |   3.33%   |   29.87%   |   0.99%   | 163,848 |                      |
|    0     | (未知)       |     653,538     |    0.4%     | **6.09%** |   22.93%   |   1.40%   | 185,107 | 疑似旧编码           |
|   184    | 天猫专营店   |     500,146     |    0.3%     |   2.65%   |   30.75%   |   0.81%   | 142,712 |                      |
|   383    | 中国移动     |     253,814     |    0.2%     |   8.07%   | **81.96%** | **6.62%** | 59,442  | 样本少不可靠         |
|   113    | 慢慢买       |     185,372     |    0.1%     |   5.48%   |   54.46%   |   2.99%   | 94,459  |                      |
|   369    | 微信         |     103,641     |    0.1%     |   4.10%   |   26.98%   |   1.11%   | 61,861  |                      |
|   378    | 麦当劳       |     49,886      |    0.0%     |   5.79%   |   7.76%    |   0.45%   | 43,110  |                      |
|   379    | 抖音小店     |     25,075      |    0.0%     |   4.30%   |   31.10%   |   1.34%   | 17,660  |                      |
|   368    | 支付宝       |     24,387      |    0.0%     |   5.99%   |   37.55%   |   2.25%   | 20,126  |                      |
|   375    | 云闪付       |     23,708      |    0.0%     |   5.82%   |   3.05%    |   0.18%   | 18,842  |                      |
|   281    | 飞猪(淘宝)   |     14,270      |    0.0%     |   2.40%   |   14.87%   |   0.36%   |  8,982  |                      |
|   128    | 小米官方商城 |       402       | **\<0.01%** |   6.72%   |   62.96%   |   4.23%   |   351   | ⚠极少                |
|   252    | 京东国际     |       307       | **\<0.01%** |   1.30%   |   50.00%   |   0.65%   |   295   | ⚠极少                |
|    6     | 苏宁易购     |       130       | **\<0.01%** |   2.31%   |   33.33%   |   0.77%   |   117   | ⚠极少                |
|   370    | 滴滴         |        6        | **\<0.01%** |  50.00%   |  100.00%   |  50.00%   |    3    | ⚠极少                |
| **合计** | —            | **158,408,486** |  **100%**   | **3.64%** | **35.62%** | **1.30%** |    —    |                      |

### 数据集中度

|    分组     | site 数 |    总PV     |   占比    |  CTR  | click→CVR | exp→CVR |
| :---------: | :-----: | :---------: | :-------: | :---: | :-------: | :-----: |
|   PV≥10M    |    5    | 144,853,129 | **91.4%** | 3.62% |  36.39%   |  1.32%  |
| 1M≤PV\<10M  |    5    | 11,022,439  |   7.0%    | 3.64% |  24.98%   |  0.91%  |
| 100K≤PV\<1M |    6    |  2,394,747  |   1.5%    | 4.64% |  39.23%   |  1.82%  |
|  PV\<100K   |    9    |   138,171   |   0.1%    | 5.20% |  17.04%   |  0.89%  |

### 关键发现

1. **极度集中**：Top 5 site 占总 PV 的 **91.4%**，且均为电商平台（京东自营31.9% + 京东商城30.7% + 天猫旗舰店13.8% + 天猫商城8.4% + 天猫超市6.7%）
1. **京东商城(site 1)是最优质站点**：click→CVR **43.93%**（远高于均值35.62%），CTR 3.51%，UV 覆盖763K
1. **天猫商城(site 10)点击驱动**：CTR **4.35%**（主流site中最高），转化率中等(30.67%)
1. **天猫超市(site 190)低点击率高转化**：CTR **2.89%**（主流5 site中最低），但click→CVR 36.65% 尚可，用户意图明确
1. **话题(site 346)奇特**：CTR 6.17% 极高，但 **转化率为 0**（100,918 次点击零转化）。结合sitename="话题"，推测是内容流（无商品转化），建议从CVR训练样本中排除或作为纯CTR站点处理
1. **拼多多(site 307) / 天猫国际(site 253) 转化偏弱**：click→CVR 分别仅29.87%和26.15%，可能用户比价意图强
1. **site 383(中国移动)样本量小但转化异常高**：CTR 8.07%、click→CVR 81.96%（仅554 conv PV），不可靠
1. **对 domain group 的价值**：
   - site 区分度极强（话题0% → 京东商城43.93%），是 CDOT **最关键**的交叉维度
   - 京东系(自营+商城) vs 天猫系(旗舰店+商城+超市) vs 其他(话题、美团)，三大集团行为模式截然不同
   - 仅25个有量取值，embedding dim=8 足够，hash_bucket_size 可降为100
   - site 346(话题)无CVR标签，domain group 应学到"话题×user→只优化CTR"的模式
