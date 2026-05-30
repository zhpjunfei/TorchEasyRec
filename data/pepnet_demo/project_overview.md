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

PEPNet_v2 CTR 略好但 CVR 差距 2.6pp。主要假设：PEPNet_v2 参数过多，1 epoch 下 CVR tower 欠拟合（v1c tower [128,64,32] vs 我们的 [512,256,128]）。

## 第五阶段：瓶颈诊断

| #   | Config   | 变化                | CTR AUC | CVR AUC | 说明                      |
| --- | -------- | ------------------- | :-----: | :-----: | ------------------------- |
| 22  | v1ctower | tower → [128,64,32] |  0.695  |  0.742  | ❌ 排除 tower 过参数化    |
| 23  | 2epochs  | num_epochs=2        | 过拟合  | 过拟合  | ❌ 第2个epoch AUC开始下降 |

两个实验基干 v4 cdot32_weight03（CDOT input_dim=32, search_weight=0.3）。

### v5 结论

| 实验     |  CTR   |  CVR   | 结论                                        |
| -------- | :----: | :----: | ------------------------------------------- |
| v1ctower | 0.695  | 0.742  | ❌ Tower 容量不是瓶颈                       |
| 2epochs  | 过拟合 | 过拟合 | ❌ 训练步数不是瓶颈（第2个 epoch AUC 下降） |

**两个假设均已排除。CVR 2.6pp 差距是架构性的**。核心差异：v1c 的 DBMtl 共享 4 层 bottom MLP `[512,256,128,64]` vs PEPNet_v2 的 EPNet 门控+专家。

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

- CVR **2.6pp** 差距（0.742 vs 0.768）
- ❌ **tower 过参数化** → 已排除
- ❌ **训练步数不足** → 已排除（2 epoch 过拟合）
- 🔴 核心假设：**共享 bottom MLP vs MoE** — v1c 的 DBMTL 用 4 层共享 MLP `[512,256,128,64]`，PEPNet_v2 用 EPNet（门控+专家）。共享 MLP 可能比 MoE 更适合当前数据

## 后续计划

### 下一步方向

| 方向            | 描述                                                   | 优先级 |
| --------------- | ------------------------------------------------------ | :----: |
| **共享 bottom** | 在 PEPNet_v2 中添加共享 bottom MLP 选项，匹配 v1c 结构 | ⭐⭐⭐ |
| v1c 完整 diff   | 除 bottom 外的其他差异（loss、特征处理等）             |  ⭐⭐  |
| 样本逻辑优化    | 去掉 click_cnt>0 或降权（等架构对齐后再试）            |   ⭐   |

### 结构 diff

| 方向           | 描述                                      | 优先级 |
| -------------- | ----------------------------------------- | :----: |
| v1c 结构 diff  | 除 tower 外其他隐性差异（CDOT/LHUC/loss） |  ⭐⭐  |
| Cross 结构探索 | CrossNet 变体替代 DCNv2                   |  ⭐⭐  |

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

## 样本提取分析

### 当前逻辑（单级聚合）

训练数据只做 **按天 GROUP BY (mmb_id, item_id)** 去重，没有跨天去重。3 天曝光去重是**线上的服务端过滤策略**（避免同一商品短期内重复曝光给同一用户），不影响训练样本。

```sql
-- ctr_label CTE
SELECT  MIN(event_unix_time), item_id, mmb_id, ...
        ,MAX(IF(event='click',1,0)) AS is_click
        ,MAX(IF(event='conversion',1,0)) AS is_conversion
FROM    home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1
WHERE   dt = '${bdp.system.bizdate}'       -- 单天
GROUP BY item_id, mmb_id                    -- 每(user,item)=1行/天
```

产出：`home_flow_2604_ctrcvr_sorter_label_table_v1` 每天一个分区。多条天分区直接 union 作为训练数据，**不做额外去重**。

### 按天 GROUP BY 的效果

同一天内同一个 (user, item) 的所有事件（曝光、点击、转化）聚合为 1 行：

| 原始事件序列                                | 聚合后                               |
| ------------------------------------------- | ------------------------------------ |
| 曝光 A → 曝光 A → 点击 A                    | is_click=1 ✅ 正确                   |
| 曝光 B → 曝光 B（无点击）                   | is_click=0 ✅ 正确                   |
| 曝光 C → 曝光 C → 点击 C → 曝光 C（第二次） | is_click=1 ⚠️ 第二次曝光的负信号被吞 |

第三种情况（先点击再二次曝光）——当天的第二次曝光本应是负样本（已经在同一天点击过了，模型应学习"已点击过的商品不需要再推荐"），但被 max 聚合为正样本。不过按天的粒度下，这种情况较少。

### `click_cnt > 0` 时序过滤

```sql
SUM(is_click) OVER (
  PARTITION BY mmb_id
  ORDER BY event_unix_time
  ROWS BETWEEN 1 PRECEDING AND 1 FOLLOWING
) AS click_cnt
```

操作对象：当天按 `MIN(event_unix_time)` 排序的 (user, item) 行序列。

例：用户当天依次交互 A(click)、B、C、D：

| 商品 | is_click |  click_cnt   |        保留？        |
| ---- | :------: | :----------: | :------------------: |
| A    |    1     | (none+1+0)=1 |    ✅ 自己有点击     |
| B    |    0     |  (1+0+0)=1   | ✅ 在 A 后面（相邻） |
| C    |    0     |  (0+0+0)=0   |     ❌ 离 A 太远     |
| D    |    0     | (0+0+none)=0 |     ❌ 离 A 太远     |

这是**时序难例负采样**——只保留"点击附近"的未点击商品。剔除的是远离点击的商品（用户不感兴趣、或者根本没注意到）。这种采样假设"远离点击的曝光不是好的训练信号"，但有偏——线上推理时大量未点击商品并不在点击商品"附近"。

### 对精排的影响

| 问题                   | 严重程度 | 说明                                                        |
| ---------------------- | :------: | ----------------------------------------------------------- |
| 无法按 request 分组    |    🔴    | GROUP BY 后 request_id 聚合丢失，每行无法归属到具体 request |
| `click_cnt>0` 样本有偏 |    🟡    | 负样本局限于点击商品附近，不代表全量曝光分布                |
| 正样本膨胀             |    🟢    | 仅在同一天同义商品二次曝光场景发生，影响有限                |
| 多天分区直接 union     |    🟢    | 无跨天去重，不同天的相同 (user,item) 各自独立保留为不同样本 |

### 与 v1c 2.6pp 差距的关系

排除 tower 过参数化后，差距来自模型架构本身。当前 SQL 对 v1c 和 PEPNet_v2 是**完全相同的输入**，不是差距的来源。

## 文件清单

| 文件                                                    | 说明                                        |
| ------------------------------------------------------- | ------------------------------------------- |
| `tzrec/models/pepnet_v2.py`                             | PEPNet_v2 模型 (含 DCNv2, CDOT, Bias, LHUC) |
| `tzrec/modules/cdot.py`                                 | CDOT 模块                                   |
| `tzrec/modules/lhuc_net.py`                             | LHUC-EPNet + LHUC-PPNet 模块                |
| `tzrec/modules/interaction.py`                          | CrossV2 (DCNv2) 模块                        |
| `config/home_flow_2604_pepnet.config`                   | 基线配置                                    |
| `config/home_flow_2604_pepnet_cdot_domain_dcnv2.config` | 🏆 最优配置                                 |
| `experiment_summary.md`                                 | 实验小结                                    |

## 数据扩展 Config

| Config                     | 位置                                       | 变更                               |              状态               |
| -------------------------- | ------------------------------------------ | ---------------------------------- | :-----------------------------: |
| freqpage16                 | `v4/..._freqpage16.config`                 | f_req_page emb=4→16, vocab→hash    |             ❌ 放弃             |
| cdot32                     | `v4/..._cdot32.config`                     | freqpage16 + emb=32 + input_dim=32 |             ❌ 放弃             |
| nofreqpage                 | `home_flow_2604_pepnet_nofreqpage.config`  | 去掉 f_req_page                    |            ➖ 无影响            |
| cdot32_weight03            | `v4/..._cdot32_weight03.config`            | cdot32 + 搜索样本 `weight: 0.3`    |      ✅ CVR ±0, CTR +0.2pp      |
| cdot32_weight03_nofreqpage | `v4/..._cdot32_weight03_nofreqpage.config` | weight03 + 去掉 f_req_page         |            🔄 运行中            |
| v5_v1ctower                | `v5/..._v5_v1ctower.config`                | tower [512,256,128] → [128,64,32]  | ❌ CTR 0.695 / CVR 0.742 无提升 |
| v5_2epochs                 | `v5/..._v5_2epochs.config`                 | num_epochs 1→2, T_max 6300→12655   |            ❌ 过拟合            |
| v5_baseline                | `v5/..._v5_baseline.config`                | cdot32_weight03 移入 v5 作为锚点   |                —                |
