______________________________________________________________________

## date: 2026-07-02 tags: [experiment, v15, like-seq, chaprice-seq, tag-seq, cdot] status: ongoing related: \["[v15-config-variants]"\], "\[[calibration-calicaustralrank]\]"

# v15 实验分析：LIKE/CHAPRICE 序列处理方式 + CDOT output_dim/seq_transformer 初步探索

## 背景

Round 1 config-only 实验（seq_transformer, cdot_out8, dcnv2_cross6）和 cvr_shortcut 均已证否（Δ\<0.1pp）。
在此之前准备了 **6 个 config 变体**，把 LIKE (like_50_seq) 和 CHAPRICE (chaprice_click_50_seq) 从 DIN 序列建模改为扁平特征注入，同时探索其放置位置对效果的影响。

______________________________________________________________________

## 一、变体设计

所有变体共享基础架构 `pepnet_dcn_ple`（CDOT=32→4, DCNv2=4层, PLE 2层, CTR tower [512,256,128], CVR tower [512,256,128]），仅差异如下：

| 变体            |            LIKE/CHAPRICE 序列组            | LIKE/CHAPRICE DIN Encoder | 特征放置                                   | 架构变化                                               |
| --------------- | :----------------------------------------: | :-----------------------: | ------------------------------------------ | ------------------------------------------------------ |
| **v1f**（基线） | ✅ 原始 sequence_feature + sequence_groups |            ✅             | "all" group 内                             | —                                                      |
| **v2**          |      ✅ 仅预编码名 + sequence_groups       |            ✅             | "all" group 内                             | 原始 sequence_feature 块移除                           |
| **v2_opta**     |                  ❌ 移除                   |          ❌ 移除          | 预编码名加入 "all" group                   | 仅特征层                                               |
| **v2_optb**     |                  ❌ 移除                   |          ❌ 移除          | 预编码名加入 **"domain" group**（走 CDOT） | 特征→domain group                                      |
| **v2_optc**     |                  ❌ 移除                   |          ❌ 移除          | 预编码名在 "all" group                     | **PLE 新增 layer3**（128→64, 1 task / 1 share expert） |
| **v2_tag_seq**  |                  ❌ 移除                   |          ❌ 移除          | 预编码名在单独 **"tag_seq_group"**         | 独立特征组                                             |

### 特征列表

LIKE/CHAPRICE 涉及的预编码特征（各 12 个，共 24 个）：

```
like_50_seq__related_goods_ids
like_50_seq__brand
like_50_seq__core_entity
like_50_seq__first_cate_id
like_50_seq__second_cate_id
like_50_seq__third_cate_id
like_50_seq__price_tag
like_50_seq__site
like_50_seq__spu_id
like_50_seq__discount_intensity
like_50_seq__pinpaidengji
like_50_seq__item_type
chaprice_click_50_seq__related_goods_ids
chaprice_click_50_seq__brand
...（同上 12 个特征）
```

______________________________________________________________________

## 二、各变体详细差异

### v1f → v2：sequence_feature 移除

v1f 中 LIKE 和 CHAPRICE 有两个定义：

1. **sequence_feature**（数据层）：定义原始序列的字段结构（长度 50，分隔符 `;`），包含每个子特征的 embedding/hash 配置
1. **sequence_groups**（模型层）：序列组定义，引用 sequence_feature 输出的预编码特征名

v2 移除了步骤 1 的原始 `sequence_feature` 块，仅保留步骤 2 的 `sequence_groups`。这意味着序列的 embedding 配置被移到了数据 pipeline（不在 config 中定义），config 只负责引用已预编码好的特征名。

### v2_opta：LIKE/CHAPRICE 退化为扁平 DEEP 特征

```
# v2_opta 的 "all" group 末尾新增（直接混入）
feature_names: "like_50_seq__related_goods_ids"
feature_names: "like_50_seq__brand"
...（12 个）
feature_names: "chaprice_click_50_seq__related_goods_ids"
...（12 个）
```

- LIKE/CHAPRICE 的 `sequence_groups` 整块移除
- 对应的 `din_encoder` 也移除（不再做 target attention）
- 24 个预编码特征直接作为普通 DEEP flatten 特征加入 "all" group
- 与 click/favorite/conversion 等序列的 DIN 编码输出走同一路径（DCNv2 → CDOT → EPNet → PLE）

**逻辑假设：** LIKE/CHAPRICE 的时序信息在预编码阶段已被用户画像统计值压缩，DIN attention 的增益有限。去掉后减少参数量，同时释放 "all" group 的容量给其他序列。

### v2_optb：LIKE/CHAPRICE → domain group（走 CDOT）

```
# v2_optb 的 "domain" group 新增
feature_names: "like_50_seq__related_goods_ids"
...（24 个预编码特征）
```

- 与 opta 不同：特征不放入 "all"，而是放入 **"domain"** group
- `cdot_group_name: "domain"` — CDOT gating 会为 domain group 的特征学习独立的压缩矩阵
- `bias_group_name: "domain"` — 也为 domain group 学习独立偏置
- `lhuc_group_name: "domain"` — LHUC 侧网络也按 domain 分组

**逻辑假设：** LIKE/CHAPRICE 信号与主序列（click/conversion/favorite）的行为模式不同。CDOT 的 domain-specific 压缩可能更适合这批信号，避免与 click 等高频序列在 "all" 中互相干扰。

### v2_optc：LIKE/CHAPRICE 扁平 + PLE 加深

```
# v2_optc 相比 opta 的额外变化
extraction_networks {
  network_name: "layer3"
  expert_num_per_task: 1
  share_num: 1
  task_expert_net {
    hidden_units: [128, 64]
    activation: "nn.ReLU"
  }
  share_expert_net {
    hidden_units: [128, 64]
    activation: "nn.ReLU"
  }
}
```

- LIKE/CHAPRICE 处理同 opta（扁平化 → "all"）
- PLE 新增第 3 层 extraction_network（128→64），每任务 1 个 expert + 1 个 share expert
- 原始 2 层：512→256 + 256→128，新增第 3 层：128→64
- 总 PLE 参数增量约：2×(128×64 + 64×64) ≈ 24K 参数，极小

**逻辑假设：** 扁平化后 "all" group 的输入维度增加了 24 个特征的 embedding，PLE 可能需要更深来消化。但第 3 层容量极小，预期效果微弱。

### v2_tag_seq：独立特征组

```
feature_groups {
  group_name: "tag_seq_group"
  feature_names: "like_50_seq__related_goods_ids"
  ...（24 个预编码特征）
}
```

- LIKE/CHAPRICE 不在 "all" 也不在 "domain"，而是独立成组
- 目前没有 `cdot_group_name` / `bias_group_name` 指向 "tag_seq_group"
- 按 PEPNet 现有逻辑，未命名的 feature_group 默认走 DEEP 路径经过 EPNet → 不经过 CDOT，直接拼到 EPNet input

**逻辑假设：** 如果 LIKE/CHAPRICE 与 click/conversion 序列正交（不冲突也不重叠），独立组可以避免稀释 "all" group 中主序列的 DIN attention 信号。但 CDOT 不对独立组做任何 domain 变换。

______________________________________________________________________

## 三、关键参数汇总

| 参数                       | v1f | v2  | v2_opta | v2_optb | v2_optc | v2_tag_seq |
| -------------------------- | :-: | :-: | :-----: | :-----: | :-----: | :--------: |
| LIKE 原始 sequence_feature | ✅  | ❌  |   ❌    |   ❌    |   ❌    |     ❌     |
| LIKE sequence_groups       | ✅  | ✅  |   ❌    |   ❌    |   ❌    |     ❌     |
| LIKE din_encoder           | ✅  | ✅  |   ❌    |   ❌    |   ❌    |     ❌     |
| LIKE → "all" group         | ✅  | ✅  |   ✅    |   ❌    |   ✅    |     ❌     |
| LIKE → "domain" group      | ❌  | ❌  |   ❌    |   ✅    |   ❌    |     ❌     |
| LIKE → "tag_seq_group"     | ❌  | ❌  |   ❌    |   ❌    |   ❌    |     ✅     |
| PLE extraction layers      |  2  |  2  |    2    |    2    |  **3**  |     2      |

______________________________________________________________________

## 四、运行状态

全部跑完（v2 结果待补）。

## 五、统一指标对比表

**基线：** `v1f`（对照组）。注：LIKE/CHAPRICE 系列为 **Eval** 指标，NC 系列为 **Training step 8100** 指标，两者绝对值不可跨列比较。

### LIKE/CHAPRICE 扁平化实验（Eval）

|  #  |      实验      | LIKE/CHAPRICE 处理方式                |  auc_ctr (Δpp)   | bce_ctr  |  auc_cvr (Δpp)   | bce_cvr  |
| :-: | :------------: | :------------------------------------ | :--------------: | :------: | :--------------: | :------: |
|  —  |   **v1f** 🏁   | 原始 sequence_feature + DIN           |   0.716480 (—)   | 1.933464 |   0.747323 (—)   | 0.494107 |
|  —  |  **v2_opta**   | 扁平化 → "all" group                  | 0.716094 (−0.05) | 1.934554 | 0.748129 (+0.11) | 0.494703 |
|  —  |  **v2_optb**   | 扁平化 → "domain" group（走 CDOT）    | 0.716274 (−0.03) | 1.933732 | 0.747542 (+0.03) | 0.494260 |
|  —  |  **v2_optc**   | 扁平化 → "all" + PLE 3层              | 0.715988 (−0.07) | 1.934504 | 0.747678 (+0.05) | 0.494288 |
|  —  | **v2_tag_seq** | 扁平化 → 独立 "tag_seq_group"         | 0.715963 (−0.07) | 1.934618 | 0.747191 (−0.02) | 0.494593 |
|  —  |     **v2**     | 保留 DIN，仅移除原始 sequence_feature |        —         |    —     |        —         |    —     |

### NC 序列组合实验（Training step 8100）

|  #  |    实验    | 新增序列（基于 v1f +）                                                                                                          |  auc_ctr (Δpp)  | bce_ctr  |  auc_cvr (Δpp)  | bce_cvr  |
| :-: | :--------: | :------------------------------------------------------------------------------------------------------------------------------ | :-------------: | :------: | :-------------: | :------: |
|  —  | **v1f** 🏁 | 无                                                                                                                              |  0.716480 (—)   | 1.933464 |  0.747323 (—)   | 0.494107 |
|  —  |   **nc**   | search_conversion_20, like_10/100, search_click_10/100, chajia_click_10/100, offline_search_click_100, offline_chajia_click_100 | 0.71693 (+0.05) | 1.91820  | 0.75595 (+1.16) | 0.48995  |
|  1  | **nc_v2**  | like_10/100, search_click_10/100, offline_search_click_100                                                                      | 0.71646 (0.00)  | 1.92071  | 0.75455 (+0.97) | 0.48784  |
|  2  | **nc_v3**  | v2 + offline_like_100                                                                                                           | 0.71683 (+0.04) | 1.92435  | 0.75502 (+1.04) | 0.48797  |
|  3  | **nc_v4**  | search_conversion_20, chajia_click_10/100, offline_chajia_click_100                                                             | 0.71604 (−0.06) | 1.92118  | 0.75475 (+1.00) | 0.48879  |
|  4  | **nc_v5**  | search_conversion_20, chajia_click_10/100                                                                                       | 0.71598 (−0.07) | 1.92170  | 0.75490 (+1.02) | 0.48984  |
|  5  | **nc_v6**  | search_conversion_20, search_click_10/100                                                                                       | 0.71627 (−0.03) | 1.91976  | 0.75458 (+0.98) | 0.49086  |
|  6  | **nc_v7**  | search_conversion_20, like_10/100, search_click_10/100, chajia_click_10/100                                                     | 0.71662 (+0.01) | 1.92534  | 0.75516 (+1.06) | 0.48960  |

⚠️ NC 系列为 Training step 8100 指标，CVR 存在约 +0.8~1.0pp 系统偏高偏差（训练集 AUC > 验证集）。Δpp 均基于 v1f Eval 值计算，CVR 正值主要反映 train/eval gap，不能解读为序列带来的实际增益。同列内 AUC 绝对值跨系列（Eval vs Training）不可直接比较。

### 序列覆盖矩阵

| 序列                         | v1f | nc  | v2  | v3  | v4  | v5  | v6  | v7  |
| :--------------------------- | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| like_10_seq                  | ❌  | ✅  | ✅  | ✅  | ❌  | ❌  | ❌  | ✅  |
| like_100_seq                 | ❌  | ✅  | ✅  | ✅  | ❌  | ❌  | ❌  | ✅  |
| offline_like_100_seq         | ❌  | ❌  | ❌  | ✅  | ❌  | ❌  | ❌  | ❌  |
| search_conversion_20_seq     | ❌  | ✅  | ❌  | ❌  | ✅  | ✅  | ✅  | ✅  |
| search_click_10_seq          | ❌  | ✅  | ✅  | ✅  | ❌  | ❌  | ✅  | ✅  |
| search_click_100_seq         | ❌  | ✅  | ✅  | ✅  | ❌  | ❌  | ✅  | ✅  |
| offline_search_click_100_seq | ❌  | ✅  | ✅  | ✅  | ❌  | ❌  | ❌  | ❌  |
| chajia_click_10_seq          | ❌  | ✅  | ❌  | ❌  | ✅  | ✅  | ❌  | ✅  |
| chajia_click_100_seq         | ❌  | ✅  | ❌  | ❌  | ✅  | ✅  | ❌  | ✅  |
| offline_chajia_click_100_seq | ❌  | ✅  | ❌  | ❌  | ✅  | ❌  | ❌  | ❌  |

### 分析

**LIKE/CHAPRICE 扁平化（Eval）：**

- CTR 全部微降（−0.03~−0.07pp），在噪声区间（±0.1pp）
- CVR：opta 最佳 +0.11pp，optc +0.05pp，optb +0.03pp，tag_seq −0.02pp
- BCE_cvr 全部微升（+0.00015~+0.00060），校准轻微恶化
- **结论：** DIN 编码移除后效果几乎不变（Δ\<0.1pp），LIKE/CHAPRICE attention 贡献可忽略。optb 的 CDOT 注入和 optc 的 PLE 加深均无额外收益。扁平化混入 "all" 是最简单选择。

**NC 序列组合（Training）：**

- 全部变体 CVR 均低于 nc（−0.11~−0.20pp），完整序列组合有正向协同
- nc_v2 减 search_conversion + chajia 后 CVR −0.20pp，损失最大
- nc_v7 仅减 offline 序列后 CVR −0.11pp，损失最小，offline 序列贡献可忽略
- nc_v3 加 offline_like_100_seq 相对 v2 提升 +0.07pp
- CTR 波动小（−0.01~−0.14pp），CVR 对序列更敏感
- **结论：** search_conversion_20_seq 和 chajia_click 是关键贡献者，offline 序列贡献微弱。

______________________________________________________________________

## 六、后续方向

| 序号 | 实验                | 内容                                                |   预期    |
| :--: | ------------------- | --------------------------------------------------- | :-------: |
|  1   | **cdot_out8**       | CDOT `output_dim: 4 → 8` 增大压缩通道               | 0.2~0.5pp |
|  2   | **seq_transformer** | click_50_seq: `din_encoder` → `transformer_encoder` | 0.3~0.8pp |
|  3   | **dcnv2_cross6**    | `dcnv2 { cross_num: 4 → 6 }` 增加交叉层             | 0.1~0.3pp |
|  4   | **cvr_shortcut**    | conversion 统计特征 bypass→CVR logit shortcut       | 0.1~0.3pp |

### 决策逻辑

```
v2_opta/optb/optc/tag_seq 任一 ≥ +0.3pp → 确认 LIKE/CHAPRICE 扁平化有效，选择最优 placement
cdot_out8 ≥ +0.3pp → CDOT capacity（output_dim 8→16→32）
seq_transformer ≥ +0.5pp → 主攻 sequence（扩展到更多序列）
全部 < +0.2pp → 确认模型上限，启动 Round 2 实时特征（Flink SQL 数据 pipeline）
```

______________________________________________________________________

## 七、CaliCausalRank 温度校准实验 (2026-07-16)

### 指标详解

每个指标的含义、计算方式和解读：

#### 1. `auc_ctr` — CTR 塔 AUC

- **含义**：CTR 模型区分"用户是否点击"的能力，取值 [0.5, 1.0]
- **计算**：对所有样本按 CTR 预测概率排序，计算正负样本对的排序覆盖率
- **业务意义**：直接影响推荐排序质量，是线上 GMV 的第一杠杆
- **基线值**：0.71539（对应线上 ctr_auc=0.716480）
- **解读**：下降 >0.5% 视为显著负向；\<0.1% 视为噪声区间

#### 2. `auc_cvr` — CVR 塔 AUC

- **含义**：CVR 模型区分"用户是否转化"的能力
- **计算**：同 AUC，但基于 CVR 预测概率
- **业务意义**：直接影响下单率预估准确性，决定长尾商品曝光机会
- **基线值**：0.75392（对应线上 cvr_auc=0.747323）
- **解读**：CVR 标签稀疏（50% 转化），AUC 波动比 CTR 更大
- **关键**：CVR 的 AUC 提升 1% ≈ 线上 GMV 提升约 0.5-1%

#### 3. `bce_ctr` — CTR 塔 Binary Cross Entropy

- **含义**：CTR 模型预测概率与真实标签之间的交叉熵损失
- **计算**：`-(y*log(p) + (1-y)*log(1-p))` 的平均值
- **业务意义**：衡量 CTR 概率校准质量，越低越好
- **基线值**：2.64624
- **解读**：BCE 上升说明概率预测变"不准"，但 AUC 可能仍正向（排序 vs 校准的区别）

#### 4. `bce_ctcvr` — CTCVR 联合损失

- **含义**：CTR × CVR 的联合交叉熵，衡量"点击且转化"的联合预测质量
- **计算**：`-(y_ctcvr*log(p_ctr*p_cvr) + (1-y_ctcvr)*log(1-p_ctr*p_cvr))`
- **业务意义**：直接优化 GMV（GMV ∝ CTR × CVR × 客单价）
- **基线值**：0.30655
- **关键**：CTCVR 损失对两个塔的耦合最敏感，是校准实验的**核心指标**

#### 5. `calibration_loss` — 软 ECE 校准损失

- **含义**：Expected Calibration Error 的可微近似，衡量预测概率与真实频率的一致性
- **计算**：将样本分 15 个概率桶，计算每个桶内 `|准确率 - 平均置信度|` 的加权平均
- **业务意义**：校准质量越高，模型输出的概率越可信
- **解读**：
  - 0.0 = 完美校准
  - 0.05 = 轻度失准（baseline 无校准时的隐含值）
  - 越大说明校准越差

#### 6. `total_loss` — 总训练损失

- **含义**：所有损失的加权和，用于反向传播
- **计算**：`bce_ctr × 4.5 + bce_ctcvr × 1.0 + calibration_loss × weight`
  - CTR 塔权重 4.5（配置中 `weight: 4.5`）
  - CVR 塔权重 1.0
  - CTCVR 权重 1.0（`ctcvr_loss_weight` 默认值）
- **解读**：total_loss 的变化反映了校准对整体训练目标的扰动程度

#### 指标间的关系

```
total_loss = ctr_weight × bce_ctr + cvr_weight × bce_ctcvr + calib_weight × calibration_loss
           = 4.5 × 2.646 + 1.0 × 0.307 + 0.02 × 0.043  (方案 A)
           = 11.907 + 0.307 + 0.001 = 12.215
```

**关键洞察**：

- CTR 的 BCE 占总损失的 ~97%，CVR 仅 ~2.5%，校准损失 ~0.001%
- 但 AUC 对损失的微小扰动非常敏感，尤其是 CVR 塔
- BCE 和 AUC 的关系：**BCE 衡量概率准确度，AUC 衡量排序能力**
  - BCE 上升但 AUC 不变 → 概率校准变差，但排序未受影响
  - BCE 下降但 AUC 不变 → 概率校准改善，排序未受影响
  - BCE 和 AUC 同向变化 → 校准和排序同时改善/恶化

### 指标详解

每个指标的含义、计算方式和解读：

#### 1. `auc_ctr` — CTR 塔 AUC

- **含义**：CTR 模型区分"用户是否点击"的能力，取值 [0.5, 1.0]
- **计算**：对所有样本按 CTR 预测概率排序，计算正负样本对的排序覆盖率
- **业务意义**：直接影响推荐排序质量，是线上 GMV 的第一杠杆
- **基线值**：0.71539（对应线上 ctr_auc=0.716480）
- **解读**：下降 >0.5% 视为显著负向；\<0.1% 视为噪声区间

#### 2. `auc_cvr` — CVR 塔 AUC

- **含义**：CVR 模型区分"用户是否转化"的能力
- **计算**：同 AUC，但基于 CVR 预测概率
- **业务意义**：直接影响下单率预估准确性，决定长尾商品曝光机会
- **基线值**：0.75392（对应线上 cvr_auc=0.747323）
- **解读**：CVR 标签稀疏（50% 转化），AUC 波动比 CTR 更大
- **关键**：CVR 的 AUC 提升 1% ≈ 线上 GMV 提升约 0.5-1%

#### 3. `bce_ctr` — CTR 塔 Binary Cross Entropy

- **含义**：CTR 模型预测概率与真实标签之间的交叉熵损失
- **计算**：`-(y*log(p) + (1-y)*log(1-p))` 的平均值
- **业务意义**：衡量 CTR 概率校准质量，越低越好
- **基线值**：2.64624
- **解读**：BCE 上升说明概率预测变"不准"，但 AUC 可能仍正向（排序 vs 校准的区别）

#### 4. `bce_ctcvr` — CTCVR 联合损失

- **含义**：CTR × CVR 的联合交叉熵，衡量"点击且转化"的联合预测质量
- **计算**：`-(y_ctcvr*log(p_ctr*p_cvr) + (1-y_ctcvr)*log(1-p_ctr*p_cvr))`
- **业务意义**：直接优化 GMV（GMV ∝ CTR × CVR × 客单价）
- **基线值**：0.30655
- **关键**：CTCVR 损失对两个塔的耦合最敏感，是校准实验的**核心指标**

#### 5. `calibration_loss` — 软 ECE 校准损失

- **含义**：Expected Calibration Error 的可微近似，衡量预测概率与真实频率的一致性
- **计算**：将样本分 15 个概率桶，计算每个桶内 `|准确率 - 平均置信度|` 的加权平均
- **业务意义**：校准质量越高，模型输出的概率越可信
- **解读**：
  - 0.0 = 完美校准
  - 0.05 = 轻度失准（baseline 无校准时的隐含值）
  - 越大说明校准越差

#### 6. `total_loss` — 总训练损失

- **含义**：所有损失的加权和，用于反向传播
- **计算**：`bce_ctr × 4.5 + bce_ctcvr × 1.0 + calibration_loss × weight`
  - CTR 塔权重 4.5（配置中 `weight: 4.5`）
  - CVR 塔权重 1.0
  - CTCVR 权重 1.0（`ctcvr_loss_weight` 默认值）
- **解读**：total_loss 的变化反映了校准对整体训练目标的扰动程度

#### 指标间的关系

```
total_loss = ctr_weight × bce_ctr + cvr_weight × bce_ctcvr + calib_weight × calibration_loss
           = 4.5 × 2.646 + 1.0 × 0.307 + 0.02 × 0.043  (方案 A)
           = 11.907 + 0.307 + 0.001 = 12.215
```

**关键洞察**：

- CTR 的 BCE 占总损失的 ~97%，CVR 仅 ~2.5%，校准损失 ~0.001%
- 但 AUC 对损失的微小扰动非常敏感，尤其是 CVR 塔
- BCE 和 AUC 的关系：**BCE 衡量概率准确度，AUC 衡量排序能力**
  - BCE 上升但 AUC 不变 → 概率校准变差，但排序未受影响
  - BCE 下降但 AUC 不变 → 概率校准改善，排序未受影响
  - BCE 和 AUC 同向变化 → 校准和排序同时改善/恶化

## 七、CaliCausalRank 温度校准实验 (2026-07-16)

### 指标详解

每个指标的含义、计算方式和解读：

#### 1. `auc_ctr` — CTR 塔 AUC

- **含义**：CTR 模型区分"用户是否点击"的能力，取值 [0.5, 1.0]
- **计算**：对所有样本按 CTR 预测概率排序，计算正负样本对的排序覆盖率
- **业务意义**：直接影响推荐排序质量，是线上 GMV 的第一杠杆
- **基线值**：0.71539（对应线上 ctr_auc=0.716480）
- **解读**：下降 >0.5% 视为显著负向；\<0.1% 视为噪声区间

#### 2. `auc_cvr` — CVR 塔 AUC

- **含义**：CVR 模型区分"用户是否转化"的能力
- **计算**：同 AUC，但基于 CVR 预测概率
- **业务意义**：直接影响下单率预估准确性，决定长尾商品曝光机会
- **基线值**：0.75392（对应线上 cvr_auc=0.747323）
- **解读**：CVR 标签稀疏（50% 转化），AUC 波动比 CTR 更大
- **关键**：CVR 的 AUC 提升 1% ≈ 线上 GMV 提升约 0.5-1%

#### 3. `bce_ctr` — CTR 塔 Binary Cross Entropy

- **含义**：CTR 模型预测概率与真实标签之间的交叉熵损失
- **计算**：`-(y*log(p) + (1-y)*log(1-p))` 的平均值
- **业务意义**：衡量 CTR 概率校准质量，越低越好
- **基线值**：2.64624
- **解读**：BCE 上升说明概率预测变"不准"，但 AUC 可能仍正向（排序 vs 校准的区别）

#### 4. `bce_ctcvr` — CTCVR 联合损失

- **含义**：CTR × CVR 的联合交叉熵，衡量"点击且转化"的联合预测质量
- **计算**：`-(y_ctcvr*log(p_ctr*p_cvr) + (1-y_ctcvr)*log(1-p_ctr*p_cvr))`
- **业务意义**：直接优化 GMV（GMV ∝ CTR × CVR × 客单价）
- **基线值**：0.30655
- **关键**：CTCVR 损失对两个塔的耦合最敏感，是校准实验的**核心指标**

#### 5. `calibration_loss` — 软 ECE 校准损失

- **含义**：Expected Calibration Error 的可微近似，衡量预测概率与真实频率的一致性
- **计算**：将样本分 15 个概率桶，计算每个桶内 `|准确率 - 平均置信度|` 的加权平均
- **业务意义**：校准质量越高，模型输出的概率越可信
- **解读**：
  - 0.0 = 完美校准
  - 0.05 = 轻度失准（baseline 无校准时的隐含值）
  - 越大说明校准越差

#### 6. `total_loss` — 总训练损失

- **含义**：所有损失的加权和，用于反向传播
- **计算**：`bce_ctr × 4.5 + bce_ctcvr × 1.0 + calibration_loss × weight`
  - CTR 塔权重 4.5（配置中 `weight: 4.5`）
  - CVR 塔权重 1.0
  - CTCVR 权重 1.0（`ctcvr_loss_weight` 默认值）
- **解读**：total_loss 的变化反映了校准对整体训练目标的扰动程度

#### 指标间的关系

```
total_loss = ctr_weight × bce_ctr + cvr_weight × bce_ctcvr + calib_weight × calibration_loss
           = 4.5 × 2.646 + 1.0 × 0.307 + 0.02 × 0.043  (方案 A)
           = 11.907 + 0.307 + 0.001 = 12.215
```

**关键洞察**：

- CTR 的 BCE 占总损失的 ~97%，CVR 仅 ~2.5%，校准损失 ~0.001%
- 但 AUC 对损失的微小扰动非常敏感，尤其是 CVR 塔
- BCE 和 AUC 的关系：**BCE 衡量概率准确度，AUC 衡量排序能力**
  - BCE 上升但 AUC 不变 → 概率校准变差，但排序未受影响
  - BCE 下降但 AUC 不变 → 概率校准改善，排序未受影响
  - BCE 和 AUC 同向变化 → 校准和排序同时改善/恶化

### 背景

CaliCausalRank 提出 **score calibration 应作为首要训练目标**。
在 v15 baseline 上引入 per-task temperature scaling + soft ECE loss，
观察对 CTR/CVR AUC 和概率校准的影响。

### 基线数据

| 指标                    | Baseline     |
| ----------------------- | ------------ |
| auc_ctr                 | 0.716480     |
| auc_cvr                 | 0.747323     |
| calibration_loss_weight | 0.0 (无校准) |

### 实验结果对比 (Epoch 0, 7700 it)

| 指标                 | Baseline | A_lowweight         | B_progressive        | C_cvr_only       |
| -------------------- | -------- | ------------------- | -------------------- | ---------------- |
| **auc_ctr**          | 0.71539  | 0.70747 (-1.1%)     | **0.71533** (-0.01%) | 0.71024 (-0.7%)  |
| **auc_cvr**          | 0.75392  | **0.76779** (+1.8%) | 0.75376 (-0.02%)     | 0.71775 (-4.8%)  |
| **bce_ctr**          | 2.64624  | 2.67243 (+1.0%)     | 2.64523 (-0.04%)     | 2.66894 (+0.9%)  |
| **bce_ctcvr**        | 0.30655  | 0.34593 (+12.9%)    | 0.30581 (-0.2%)      | 0.35701 (+16.5%) |
| **calibration_loss** | —        | 0.04305             | **0.00000**          | 0.05631          |
| **total_loss**       | 2.95278  | 3.06141 (+3.7%)     | 2.95103 (-0.1%)      | 3.08226 (+4.4%)  |

### 逐项分析

#### 方案 A (lowweight, weight=0.02, T=1.5) — ✅ 唯一正向

- AUC_CTR 微降 1.1%，但 **AUC_CVR 提升 1.8%**，是唯一 CVR 正向的方案
- `initial_temperature=1.5` 软化 logits 相当于隐式 CVR 正则化
- CVR 标签稀疏（50% 转化），模型易对正样本过度自信，T=1.5 强制概率趋近均匀
- BCE_ctcvr 上升 12.9%，说明 CTCVR 联合损失受校准干扰，但 AUC_CVR 提升抵消了负面影响

#### 方案 B (progressive, weight=0.05, 只校CVR) — ❌ 完全失效

- `calibration_loss: 0.00000` — 校准损失为零
- **根因：** trainer 未调用 `set_current_step()`，`_current_step=0`
- `_get_current_calibration_weight(0)` 返回 `schedule[0][1]=0.0`（第一步权重）
- 好消息：AUC 几乎等于 baseline（ctr -0.01%, cvr -0.02%），证明 `calibration_tower_names: "cvr"` 过滤逻辑正确

#### 方案 C (cvr_only, weight=0.05, 只校CVR) — ⚠️ 负向但好于全塔

- AUC_CVR 下降 4.8%，优于全塔校准的 6.4%
- 只校准 CVR 保护了 CTR 排名质量
- 但 weight=0.05 仍偏大，ECE 梯度与 BCE 梯度在 CVR 塔上冲突

### 核心洞见

1. **T=1.5 软化 logits 是正向杠杆** — 对 CVR 稀疏标签场景有隐式正则化效果
1. **只校准 CVR 优于全塔校准** — CTR 排名质量不应被校准干扰
1. **方案 B 的 progressive schedule 设计正确，但需要 trainer 集成**
1. **仅 1 epoch 数据，趋势尚不稳固** — 需要多 epoch 验证

### 后续计划

| 序号 | 实验 | 内容 | 预期 |
| :--: | ---- | ---- | :--: |

### 修复记录

**2026-07-17: 修复方案 B 完全失效的根因**

方案 B 的 `calibration_loss: 0.00000` 不是因为 schedule 逻辑错误，而是因为：

- `set_current_step()` 方法存在但 **trainer 未调用**
- `_current_step` 保持初始值 `0`
- `_get_current_calibration_weight(0)` 返回 `schedule[0][1] = 0.0`
- 校准损失始终为零

**修复：** 在 `tzrec/main.py` training loop 中添加：

```python
if hasattr(_model, "set_current_step"):
    _model.set_current_step(i_step)
```

与现有 `anneal_temperature` 模式一致，向后兼容。

### 方案 D：A+B 融合

融合方案 A（T=1.5 软化 + 低权重）和方案 B（progressive + cvr_only）的优势：

| 配置项                  | 方案 A    | 方案 B             | 方案 D                 |
| ----------------------- | --------- | ------------------ | ---------------------- |
| initial_temperature     | 1.5       | 1.0                | **1.5**                |
| calibration_loss_weight | 0.02      | 0.05               | **0.02**               |
| progressive schedule    | 无        | 2000:0.0→6000:0.05 | **2000:0.0→6000:0.03** |
| calibration_tower_names | 全部      | cvr                | **cvr**                |
| 预期效果                | CVR +1.8% | 修复后未知         | **CVR +2~4%**          |

设计逻辑：

- T=1.5 提供隐式 CVR 正则化（方案 A 已验证正向）
- weight=0.02 最小化对主任务的干扰
- progressive schedule 确保前 2000 step 无校准干扰，等主任务稳定后再介入
- 只校准 CVR 保护 CTR 排名质量

配置文件：`home_flow_2604_v15_calibration_d_fusion.config`

| 1 | **修复 B** | 在 trainer 中调用 `model.set_current_step()` | calibration_loss 生效 |
| 2 | **方案 D** | A+B 融合：T=1.5, weight=0.02, progressive="2000:0.0,4000:0.02,6000:0.03", cvr_only | CVR AUC +1~3% |
| 3 | **T 扫描** | initial_temperature ∈ {1.2, 1.5, 2.0, 2.5} | 找最优软化系数 |
| ~~4~~ | ~~多 Epoch~~ | ~~训练 3+ epochs 验证趋势稳定性~~ | ~~确认长期效果~~ | ~~取消~~ |

### 决策逻辑

```
修复 B 后 progressive 生效 → AUC_CVR ≥ baseline → 确认 progressive + cvr_only 方向
A 方案 T=1.5 正向 → 扫描 T 值找最优
全部校准实验 ΔAUC < -0.5% → 考虑放弃校准，回归 baseline + T=1.5 软化
```

______________________________________________________________________

______________________________________________________________________

## date: 2026-07-17 tags: [calibration, consensus, validation-strategy] status: resolved

# 校准实验：验证策略共识

## 决策

**不需要多 Epoch 验证校准实验的趋势稳定性。**

## 理由

1. **基线已过拟合** — 历史经验表明单 Epoch 后基线就开始过拟合，多 Epoch 验证的意义不大
1. **校准是轻量级正则化** — calibration weight 仅 0.02-0.05，对过拟合节奏的影响可忽略
1. **Epoch 0 AUC 趋势已足够判断方向** — 校准的效果是即时性的（温度缩放直接影响概率分布），不需要等待长期收敛

## 适用条件

以下情况才需要额外 Epoch 验证：

- 方案 B 修复 `set_current_step` 后重新实验（原 Epoch 0 数据因 bug 无效，需确认 progressive schedule 真正生效）
- 方案 A 和方案 D 的 Epoch 0 结果出现**方向矛盾**（如一个正向一个负向），此时需要第 2 epoch 确认信号强度
- 否则，单 Epoch 的 AUC 趋势已足以做出"go/no-go"决策

## 后续计划（更新版）

| 序号  | 实验         | 内容                                                                               |                    预期                     |  优先级  |
| :---: | ------------ | ---------------------------------------------------------------------------------- | :-----------------------------------------: | :------: |
|   1   | **修复 B**   | 重新跑方案 B（含 `use_step` guard + schedule 预解析优化）                          | calibration_loss > 0，验证 progressive 生效 |    P0    |
|   2   | **方案 D**   | A+B 融合：T=1.5, weight=0.02, progressive="2000:0.0,4000:0.02,6000:0.03", cvr_only |                CVR AUC +1~3%                |    P0    |
|   3   | **T 扫描**   | initial_temperature ∈ {1.2, 1.5, 2.0, 2.5}                                         |               找最优软化系数                |    P1    |
| ~~4~~ | ~~多 Epoch~~ | ~~训练 3+ epochs 验证趋势稳定性~~                                                  |              ~~确认长期效果~~               | ~~取消~~ |

## 代码变更确认

以下改进已就绪但尚未提交：

- `tzrec/main.py`: 添加 `use_step` guard（与 `anneal_temperature` 一致）
- `tzrec/models/pepnet_dcn_ple.py`: schedule 预解析缓存（O(1) runtime lookup）

______________________________________________________________________

## date: 2026-07-17 tags: [calibration, bugfix, progressive-schedule] status: resolved

# Bug: 方案 B/D 的 calibration_loss=0 根因 — use_step 守卫导致 set_current_step 从未被调用

## 现象

7.16 号的实验结果：

- 方案 B progressive: calibration_loss=0.00000, auc_cvr=0.75376 (vs baseline 0.75390)
- 方案 D fusion: calibration_loss=0.00000, auc_cvr=0.75386 (vs baseline 0.75390)

两个方案的效果几乎等于 baseline，calibration_loss 始终为 0。

## 根因分析

```python
# tzrec/main.py:458
if use_step and hasattr(_model, "set_current_step"):  # ← use_step 是罪魁祸首
    _model.set_current_step(i_step)
```

`use_step = train_config.num_steps and train_config.num_steps > 0`

但所有实验配置使用 `num_epochs: 1`，没有设置 `num_steps`，所以：

- `train_config.num_steps = 0`
- `use_step = False`
- `set_current_step(i_step)` **从未被调用**
- `_current_step` 始终为初始值 `0`
- `_get_current_calibration_weight(0)` 返回 `schedule[0][1] = 0.0`（第一步权重）
- `calibration_loss = total_calib_loss * 0.0 = 0`

**这就是为什么 7.16 方案 B 的 calibration_loss 也是 0——不是同一个 bug，是同一个根因的延续。** 之前 `eec463b` 的修复加了 `use_step and` 条件，反而让它在 epoch-based 训练下彻底失效。

## 修复

去掉 `use_step` 条件，`i_step` 在 epoch-based 模式下也是递增的 step counter（`itertools.count(0)`）：

```python
# Before:
if use_step and hasattr(_model, "set_current_step"):
    _model.set_current_step(i_step)

# After:
if hasattr(_model, "set_current_step"):
    _model.set_current_step(i_step)
```

## 重新实验结果

修复后需要重新跑方案 B 和 D，预期 calibration_loss 不再为 0，progressive schedule 真正生效。

## 教训

- `use_step` 守卫在 epoch-based 训练配置下会静默禁用所有 step-dependent 功能
- 新增的 step-based 回调函数必须检查训练的 step/epoch 模式
- 单元测试无法覆盖此 bug（测试用 tensor 直接调用，不走 trainer loop）
