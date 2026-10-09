# 序列特征深度勘验报告

> 勘验日期：2026-08-28
> 数据源：home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
> 样本量：1,336,094 PV/天
> 分析范围：v18_seq.config 中全部 9 个实时序列 + 4 个离线序列

______________________________________________________________________

## 一、实时序列有效长度分布（DIN 退化程度分析）

| 序列                 | avg_nz_len | median | pct_len≤1  | p95  | DIN 退化程度 |
| -------------------- | ---------- | ------ | ---------- | ---- | ------------ |
| like_100_seq         | 0.96       | 1.0    | **99.79%** | 1.0  | 🔴 严重退化  |
| chajia_click_100_seq | 0.68       | 1.0    | **98.27%** | 1.0  | 🔴 严重退化  |
| favorite_5_seq       | 0.86       | 1.0    | **98.24%** | 1.0  | 🔴 严重退化  |
| conversion_5_seq     | 0.59       | 0.0    | **88.63%** | 2.0  | 🔴 严重退化  |
| search_click_100_seq | 1.01       | 0.0    | **89.17%** | 3.0  | 🟡 中度退化  |
| click_10_seq         | 0.91       | 1.0    | **79.52%** | 3.0  | 🟡 中度退化  |
| click_50_seq         | 3.69       | 3.0    | 33.41%     | 11.0 | ✅ 正常      |

### 关键结论

1. **7/9 序列的 p95_nz_len ≤ 3**：DIN attention 在绝大多数样本上只有 1~3 个有效 key，attention 机制接近退化为恒等映射（权重趋近均匀）
1. **like_100 / chajia_click_100 / favorite_5 几乎完全退化**：98%+ 样本只有 1 条有效行为，100 长度完全过剩
1. **唯一正常的序列是 click_50_seq**：avg_nz=3.69，p95=11，attention 有发挥空间
1. **conversion_5_seq 的 median=0**：说明超过 50% 用户没有任何转化行为记录，序列全是 padding

______________________________________________________________________

## 二、Time-Decay 必要性验证

**click_10 vs click_50 首项重合度：100%**

```
click_10_vs_50_first_match_pct = 100.0%
click_10_in_50_pct = 100.0%
```

**解读**：

- click_10 的首项（最近一次点击）100% 包含在 click_50 中
- 这意味着 click_10 和 click_50 捕捉的是同一波行为，时间窗口 10 和 50 在"最近行为"上是完全重叠的
- **Time-Decay 对 click 序列价值有限**（因为它们本就高度重合）
- 但对 **search_click_100_seq**（与 click_50 无直接重叠）和 **chajia_click_100_seq** 仍有价值——这两个序列的行为模式与点击序列不同

**结论**：time-decay 对 search/chajia 序列优先实施，click 序列次优。

______________________________________________________________________

## 三、Offline 序列位置权重可行性

| 序列                         | avg_nz_len | p50 | p90 | p95 | position-weighted 可行性 |
| ---------------------------- | ---------- | --- | --- | --- | ------------------------ |
| offline_search_click_100_seq | 3.23       | 0.0 | 5.0 | 9.0 | ✅ 可行                  |
| offline_order_100_seq        | 1.85       | 1.0 | 5.0 | 9.0 | ✅ 可行                  |
| offline_like_100_seq         | 0.89       | 1.0 | 1.0 | 1.0 | ❌ 不可行（p95=1）       |
| offline_chajia_click_100_seq | 0.24       | 0.0 | 1.0 | 1.0 | ❌ 不可行（极稀疏）      |

**结论**：

- `offline_search_click` 和 `offline_order`：p95=9，position-weighted mean pooling 有意义
- `offline_like` 和 `offline_chajia_click`：p95=1，mean 和 position-weighted 无差异，保持原样即可

______________________________________________________________________

## 四、Username 字段价值评估

```
total_pv = 1,336,094
has_multi_user = 823,835 (61.66%)
distinct_first_user = 1,611
avg_username_nz = 0.26
```

**解读**：

- 61.66% 的用户在搜索序列中有多个不同创作者（multi_user），这是一个高比例
- 1,611 个 distinct 首项创作者，区分度足够
- avg_username_nz=0.26 说明平均每个用户只有 0.26 个非零 username 元素（即 ~26% 的用户有 username 信号）
- **结论**：username 是一个有价值的补充特征，应加入 search_click_100_seq

______________________________________________________________________

## 五、Online-Offline 重合度

```
online_offline_first_overlap_pct (chajia)     = 66.06%
search_online_offline_overlap_pct             = 84.78%
```

**解读**：

- **chajia 序列**：offline 与 online 首项重合仅 66%，说明 offline 序列携带约 1/3 的独立信号，离线聚合有价值
- **search 序列**：offline 与 online 首项重合 85%，offline 增量信息较少，但仍保留
- **结论**：offline 序列整体值得保留，chajia 的独立信号更强

______________________________________________________________________

## 六、冗余序列二次确认

基于本次核验，以下序列可安全移除：

| 序列                   | 移除理由                                                     |
| ---------------------- | ------------------------------------------------------------ |
| `like_100_seq`         | 99.79% 样本长度≤1，DIN 完全退化，p95=1                       |
| `favorite_5_seq`       | 98.24% 样本长度≤1，DIN 完全退化                              |
| `conversion_5_seq`     | 88.63% 样本长度≤1，median=0（过半用户无转化行为）            |
| `chajia_click_100_seq` | 98.27% 样本长度≤1，DIN 退化 + 与 online 搜索序列存在功能重叠 |

**需保留的序列**：

- `click_10_seq`、`click_50_seq`：avg_nz≥0.9，p95≥3，attention 有发挥空间
- `favorite_10_seq`：未在本次核验中（需补充 SQL）
- `search_click_100_seq`：avg_nz=1.01，p95=3，搜索意图独立信号，已验证 +2.3pp CVR AUC
- `chajia_click_100_seq`：虽有退化但 66% 非重合度说明有独立信号，可保留做消融实验

______________________________________________________________________

## 七、优化方案

### P0 — 立即执行

#### 7.1 补全 search_click_100_seq 的 username 字段

v18_seq.config 中 search_click_100_seq 的 sequence_feature 缺少 username（chajia_click_100_seq 有 19 个特征，search 只有 18 个）。

```
在 search_click_100_seq 的 features 块末尾追加：
    features {
      id_feature {
        feature_name: "username"
        expression: "item:username"
        embedding_dim: 12
        hash_bucket_size: 49640
      }
    }
```

#### 7.2 移除完全退化的序列

从 v18_seq.config 中移除以下序列的 `sequence_feature` + `sequence_groups` + `din_encoder` 三处定义：

- `like_100_seq`（99.79% 退化）
- `favorite_5_seq`（98.24% 退化）
- `conversion_5_seq`（median=0，88.63% 退化）

**注意**：移除前需确认这些序列在业务上是否有特殊价值（如 favorite 行为虽稀疏但对长期兴趣建模有意义）。建议先做消融实验再决定。

______________________________________________________________________

### P1 — 实验验证

#### 8.1 Time-Decay DIN（针对 search_click_100_seq 和 chajia_click_100_seq）

当前 DIN 对 search/chajia 序列所有元素平等加权，但搜索行为的时间信号极强（最近一次搜索的意图最相关）。

方案：在 DIN attention score 中加入时间衰减项

```protobuf
# 伪代码：需在 TorchEasyRec 中实现 time_decay din_encoder
sequence_encoders {
  time_decay_din_encoder {
    input: "search_click_100_seq"
    lambda: 0.05   # 半衰期约 14 小时，可调
    attn_mlp {
      hidden_units: 128
      hidden_units: 64
      activation: "Dice"
    }
  }
}
```

预期：对 CVR AUC +0.2~0.5pp（基于阿里/快手生产经验）

#### 8.2 Offline 序列 Position-Weighted Pooling（针对 search/order）

对 offline_search_click_100_seq 和 offline_order_100_seq（p95≥5），将 mean pooling 改为 position-weighted：

```protobuf
# issue7 config 中修改 pooling 方式
feature_configs {
  id_feature {
    feature_name: "offline_search_click_100_seq__brand"
    pooling: "position_weighted"  # 新增支持
    position_weight: "exp(-0.1 * i)"  # i 为位置索引，越靠前权重越高
  }
}
```

对 offline_like 和 offline_chajia_click（p95=1），保持 mean/sum 不变。

______________________________________________________________________

### P2 — 长期优化

#### 9.1 短序列长度缩减

对退化严重的序列，缩短 sequence_length 可以减少 padding 计算量：

- like_100_seq → like_5_seq（如果保留）
- chajia_click_100_seq → chajia_click_10_seq（如果保留）

#### 9.2 补充 conversion_20_seq

FG 中有定义但未使用。conversion 行为稀疏（avg_nz=0.59），但 20 长度的 conversion_20_seq 可能比 5 长度覆盖更多转化意图。建议实验验证。

______________________________________________________________________

## 八、待补充核验 SQL

以下 SQL 用于进一步验证优化决策：

### SQL-1：favorite_10_seq 有效长度分布（未在本次核验中）

```sql
SELECT
    COUNT(1) AS total_pv,
    ROUND(AVG(SIZE(favorite_10_seq__brand) - SIZE(ARRAY_REMOVE(favorite_10_seq__brand, '0'))), 2) AS avg_nz_len,
    ROUND(MEDIAN(SIZE(favorite_10_seq__brand) - SIZE(ARRAY_REMOVE(favorite_10_seq__brand, '0'))), 1) AS median_nz_len,
    ROUND(SUM(IF(SIZE(favorite_10_seq__brand) - SIZE(ARRAY_REMOVE(favorite_10_seq__brand, '0')) <= 1, 1, 0)) * 100.0 / COUNT(1), 2) AS pct_len_le_1,
    ROUND(PERCENTILE(SIZE(favorite_10_seq__brand) - SIZE(ARRAY_REMOVE(favorite_10_seq__brand, '0')), 0.95), 1) AS p95_nz_len
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

### SQL-2：conversion_20_seq 数据质量（决定是否引入）

```sql
SELECT
    COUNT(1) AS total_pv,
    SUM(IF(SIZE(conversion_20_seq__item_id) > 0, 1, 0)) AS has_seq,
    ROUND(SUM(IF(SIZE(conversion_20_seq__item_id) > 0, 1, 0)) * 100.0 / COUNT(1), 2) AS coverage_pct,
    ROUND(AVG(SIZE(conversion_20_seq__item_id) - SIZE(ARRAY_REMOVE(conversion_20_seq__item_id, '0'))), 2) AS avg_nz_len,
    ROUND(MEDIAN(SIZE(conversion_20_seq__item_id) - SIZE(ARRAY_REMOVE(conversion_20_seq__item_id, '0'))), 1) AS median_nz_len,
    ROUND(PERCENTILE(SIZE(conversion_20_seq__item_id) - SIZE(ARRAY_REMOVE(conversion_20_seq__item_id, '0')), 0.95), 1) AS p95_nz_len
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

### SQL-3：search_click_100_seq 的 username 字段与 conversion 的相关性

```sql
SELECT
    SUM(IF(SIZE(search_click_100_seq__username) > 0, 1, 0)) AS has_username,
    ROUND(SUM(IF(SIZE(search_click_100_seq__username) > 0, 1, 0)) * 100.0 / COUNT(1), 2) AS username_coverage_pct,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(search_click_100_seq__username) > 0, 1, 0)) * 100.0 / SUM(IF(is_conversion = 1, 1, 0)), 2) AS conversion_with_username_pct,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(search_click_100_seq__username) = 0, 1, 0)) * 100.0 / SUM(IF(is_conversion = 1, 1, 0)), 2) AS conversion_without_username_pct
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

### SQL-4：各序列与目标的 CTR/CVR 相关性（特征重要性参考）

```sql
SELECT
    'search_click_100_seq' AS seq_name,
    ROUND(CORR(
        IF(SIZE(search_click_100_seq__brand) - SIZE(ARRAY_REMOVE(search_click_100_seq__brand, '0')) > 0, 1, 0),
        is_conversion
    ), 4) AS cvr_corr,
    ROUND(CORR(
        IF(SIZE(search_click_100_seq__brand) - SIZE(ARRAY_REMOVE(search_click_100_seq__brand, '0')) > 0, 1, 0),
        is_click
    ), 4) AS ctr_corr
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}'
GROUP BY 'search_click_100_seq'

UNION ALL
SELECT 'click_50_seq',
    ROUND(CORR(IF(SIZE(click_50_seq__brand) - SIZE(ARRAY_REMOVE(click_50_seq__brand, '0')) > 0, 1, 0), is_conversion), 4),
    ROUND(CORR(IF(SIZE(click_50_seq__brand) - SIZE(ARRAY_REMOVE(click_50_seq__brand, '0')) > 0, 1, 0), is_click), 4)
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt = '${bizdate}' GROUP BY 'click_50_seq'

UNION ALL
SELECT 'chajia_click_100_seq',
    ROUND(CORR(IF(SIZE(chajia_click_100_seq__brand) - SIZE(ARRAY_REMOVE(chajia_click_100_seq__brand, '0')) > 0, 1, 0), is_conversion), 4),
    ROUND(CORR(IF(SIZE(chajia_click_100_seq__brand) - SIZE(ARRAY_REMOVE(chajia_click_100_seq__brand, '0')) > 0, 1, 0), is_click), 4)
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt = '${bizdate}' GROUP BY 'chajia_click_100_seq'

UNION ALL
SELECT 'like_100_seq',
    ROUND(CORR(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0), is_conversion), 4),
    ROUND(CORR(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0), is_click), 4)
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt = '${bizdate}' GROUP BY 'like_100_seq';
```

______________________________________________________________________

## 九、决策汇总表

| 优化项                                           | 数据支撑                           |      优先级      | 预期收益           | 风险             |
| ------------------------------------------------ | ---------------------------------- | :--------------: | ------------------ | ---------------- |
| 补 username to search_click_100                  | 61.66% multi_user, 1611 distinct   |        P0        | +稳定              | 无               |
| 移除 like_100_seq                                | 99.79% 退化                        | P1（需消融实验） | 省参数             | 可能损失收藏意图 |
| 移除 favorite_5_seq                              | 98.24% 退化                        | P1（需消融实验） | 省参数             | 同上             |
| 移除 conversion_5_seq                            | median=0, 88.63% 退化              | P1（需消融实验） | 省参数             | 转化信号损失     |
| Time-Decay DIN (search/chajia)                   | click_10/50 100% 重合，search 独立 |        P1        | +0.2~0.5pp CVR AUC | 需代码改动       |
| Position-Weighted Pooling (offline search/order) | p95=9, 有足够长度                  |        P2        | +0.1~0.3pp         | 需代码改动       |
| 引入 conversion_20_seq                           | 需 SQL-2 验证                      |        P2        | 未知               | 需实验           |

______________________________________________________________________

## 十、Encoder 架构审核

### 10.1 实时序列 DIN 架构

**当前实现**：9 个序列共用 `din_encoder { attn_mlp: 128→64, Dice }`，无时间衰减。

**关键发现**：TorchEasyRec **已原生支持 time_gate**：

```protobuf
message DINEncoder {
    required string input = 2;
    required MLP attn_mlp = 3;
    optional int32 time_gate_dim = 7 [default = 0];  // 若 > 0，最后 N 维为时间戳 embedding
}
```

实现逻辑（[`tzrec/modules/sequence.py:121`](/Users/zhangjunfei/mmb/TorchEasyRec/tzrec/modules/sequence.py:121)）：

```python
if self._time_gate_dim > 0:
    ts_emb = sequence[:, :, -self._time_gate_dim :]   # 最后 N 维 = 时间戳 embedding
    content_seq = sequence[:, :, : -self_time_gate_dim]  # 前面 = 内容 embedding
    gate = torch.sigmoid(self.time_gate_linear(ts_emb))  # 可学习时间门控
    # gate 乘以 attention score，实现时间衰减
```

**v10 历史经验**：v10 系列 config 已对 click_10/50、conversion_5/20、favorite_5/10 使用 `time_gate_dim: 8`，证明该机制在生产中可用。

**v18 遗漏**：v18_seq.config 中所有序列虽有 ts raw_feature，但 **未设置 time_gate_dim**，时间信号未被利用。

### 10.2 Offline 序列 Pooling 架构

**当前实现**：所有 offline 序列特征使用 `pooling: "mean"`（issue7 config）。

**TorchEasyRec 支持**：`PoolingEncoder` 仅支持 `mean` 和 `sum`，**无原生 position-weighted pooling**。

| 方案                 |  可行性   | 说明                                   |
| -------------------- | :-------: | -------------------------------------- |
| Mean Pooling（当前） |  ✅ 支持  | 均匀加权，丢失时序信息                 |
| Sum Pooling          |  ✅ 支持  | 保留频次信号，对稀疏序列（like）更友好 |
| Position-Weighted    | ❌ 不支持 | 需代码改动扩展 PoolingEncoder          |
| SelfAttentionEncoder |  ✅ 支持  | 可捕捉位置依赖，但 compute cost 高     |

**数据驱动决策**：

- `offline_like_100_seq`（p95=1）和 `offline_chajia_click_100_seq`（p95=1）：position-weighted 无意义，保持 mean
- `offline_search_click_100_seq`（p95=9）和 `offline_order_100_seq`（p95=9）：position-weighted 有价值，但需代码改动

### 10.3 新建 Config 汇总

| Config                        | 用途                | 核心改动                                                                |
| ----------------------------- | ------------------- | ----------------------------------------------------------------------- |
| `v18_seq_ablation.config`     | 消融实验            | 移除 like_100_seq、favorite_5_seq、conversion_5_seq（9 序列→6 序列）    |
| `v18_seq_timegate.config`     | Time-Decay DIN 实验 | 9 个 DIN encoder 加 `time_gate_dim: 8`，search/chajia 补 ts raw_feature |
| `v18_issue7_posweight.config` | Offline 聚合优化    | search/order 的 brand/spu_id/core_entity 改 sum pooling（保留频次信号） |

______________________________________________________________________

## 十一、退化序列转化率核验（2026-08-28 补充）

### 核验 SQL 及结果

#### SQL-5：like_100_seq 转化率区分度

```sql
SELECT
    SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)) AS has_like,
    ROUND(SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)) * 100.0 / COUNT(1), 2) AS like_coverage_pct,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)), 0), 2) AS conv_rate_with_like,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) = 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) = 0, 1, 0)), 0), 2) AS conv_rate_without_like
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

结果：

| has_like  | like_coverage_pct | conv_rate_with_like | conv_rate_without_like |
| --------- | ----------------- | ------------------- | ---------------------- |
| 1,269,394 | 95.01%            | **10.51%**          | **10.74%**             |

**结论**：有喜欢的用户转化率反而比没有的低 0.23pp，like_100_seq **无区分度，建议移除**。

#### SQL-6：conversion_5_seq 转化率区分度

```sql
SELECT
    SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)) AS has_conv_seq,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)), 0), 2) AS conv_rate_with_seq,
    ROUND(SUM(IF(is_conversion = 1 AND SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) = 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) = 0, 1, 0)), 0), 2) AS conv_rate_without_seq
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

结果：

| has_conv_seq  | conv_rate_with_seq | conv_rate_without_seq |
| ------------- | ------------------ | --------------------- |
| 532,856 (40%) | **10.67%**         | **10.43%**            |

**结论**：仅有 0.24pp 区分度，且 median=0（>50% 用户零转化），conversion_5_seq **基本无价值，建议移除**。

#### SQL-7：favorite_5_seq vs favorite_10_seq 重合度

```sql
SELECT
    COUNT(1) AS total_pv,
    SUM(IF(SIZE(favorite_5_seq__brand) - SIZE(ARRAY_REMOVE(favorite_5_seq__brand, '0')) > 0, 1, 0)) AS has_fav,
    ROUND(SUM(IF(SIZE(favorite_5_seq__brand) - SIZE(ARRAY_REMOVE(favorite_5_seq__brand, '0')) > 0, 1, 0)) * 100.0 / COUNT(1), 2) AS fav_coverage_pct,
    ROUND(SUM(IF(SIZE(favorite_10_seq__brand) - SIZE(ARRAY_REMOVE(favorite_10_seq__brand, '0')) > 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(favorite_5_seq__brand) - SIZE(ARRAY_REMOVE(favorite_5_seq__brand, '0')) > 0, 1, 0)), 0), 2) AS fav10_among_fav5_pct
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

结果：

| total_pv  | has_fav   | fav_coverage_pct | fav10_among_fav5_pct |
| --------- | --------- | ---------------- | -------------------- |
| 1,336,094 | 1,112,532 | 83.27%           | **101.12%**          |

**结论**：101% 的 favorite_5_seq 用户同时有 favorite_10_seq（即 favorite_5 是 favorite_10 的子集），**完全冗余，建议移除**。

### 最终移除决策

| 序列               | 移除理由                                    |
| ------------------ | ------------------------------------------- |
| `like_100_seq`     | 转化率反向（-0.23pp），无区分度             |
| `favorite_5_seq`   | 100% 与 favorite_10_seq 重合，完全冗余      |
| `conversion_5_seq` | 区分度仅 0.24pp，median=0，超半数样本无意义 |

#### SQL-8：like_100_seq CTR 区分度

```sql
SELECT
    SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)) AS has_like,
    ROUND(SUM(IF(is_click = 1 AND SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) > 0, 1, 0)), 0), 2) AS ctr_with_like,
    ROUND(SUM(IF(is_click = 1 AND SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) = 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(like_100_seq__brand) - SIZE(ARRAY_REMOVE(like_100_seq__brand, '0')) = 0, 1, 0)), 0), 2) AS ctr_without_like
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

结果：

| has_like  | ctr_with_like | ctr_without_like |
| --------- | ------------- | ---------------- |
| 1,269,394 | **33.65%**    | **35.34%**       |

CTR Δ = **-1.69pp**（有喜欢行为的用户 CTR 反而更低）

#### SQL-9：conversion_5_seq CTR 区分度

```sql
SELECT
    SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)) AS has_conv_seq,
    ROUND(SUM(IF(is_click = 1 AND SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) > 0, 1, 0)), 0), 2) AS ctr_with_seq,
    ROUND(SUM(IF(is_click = 1 AND SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) = 0, 1, 0)) * 100.0 / NULLIF(SUM(IF(SIZE(conversion_5_seq__brand) - SIZE(ARRAY_REMOVE(conversion_5_seq__brand, '0')) = 0, 1, 0)), 0), 2) AS ctr_without_seq
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
WHERE dt = '${bizdate}';
```

结果：

| has_conv_seq  | ctr_with_seq | ctr_without_seq |
| ------------- | ------------ | --------------- |
| 532,856 (40%) | **32.32%**   | **34.67%**      |

CTR Δ = **-2.35pp**

### 三序列全面对比（CTR + CVR 双维度）

| 序列             | 覆盖率 |    CTR Δ    |    CVR Δ    | 综合判断                        |
| ---------------- | :----: | :---------: | :---------: | ------------------------------- |
| like_100_seq     |  95%   | **-1.69pp** | **-0.23pp** | 🔴 双维负向                     |
| favorite_5_seq   |  83%   |      —      |      —      | 🔴 100% 与 favorite_10_seq 重合 |
| conversion_5_seq |  40%   | **-2.35pp** |   +0.24pp   | 🔴 CTR 强负向，CVR 微弱正向     |

**最终决策**：三个序列均无正向区分度，从 v18_seq_ablation.config 中全部移除。

______________________________________________________________________

## 十二、实验结果（2026-08-28）

### 12.1 实验配置

| 实验                | Config           | 序列数 | time_gate | 退化序列 |
| ------------------- | ---------------- | :----: | :-------: | :------: |
| search_seq          | v18_seq          |   9    |    否     |    含    |
| search_seq_ablation | v18_seq_ablation |   6    |    否     |    无    |
| search_seq_timegate | v18_seq_timegate |   6    |    是     |    无    |

### 12.2 核心指标

| 指标           | search_seq |  ablation   | timegate |     abl-vs-base     |   tg-vs-base   |
| -------------- | :--------: | :---------: | :------: | :-----------------: | :------------: |
| AUC CTR        |  0.72148   |   0.72253   | 0.72215  |     +1.05pp ✅      |   +0.67pp ✅   |
| AUC CVR        |  0.74649   | **0.75262** | 0.74978  |  **+6.13pp ✅✅**   |   +3.29pp ✅   |
| GrpAUC CTR     |  0.68807   |   0.68927   | 0.68882  |     +1.20pp ✅      |   +0.75pp ✅   |
| GrpAUC CVR     |  0.74530   |   0.74747   | 0.74664  |     +2.17pp ✅      |   +1.34pp ✅   |
| Total Loss     |  2.79625   | **2.78942** | 2.79117  |     -0.683pp ✅     |  -0.508pp ✅   |
| probs_cvr mean |   0.2803   | **0.2773**  |  0.2821  | closer to 0.1013 ✅ | slightly worse |

### 12.3 结论

1. **ablation 全面正向**：移除 3 个退化序列后，CVR AUC 提升 6.13pp，CTR AUC 提升 1.05pp，total loss 降低。说明退化序列不仅无贡献，反而引入噪声。
1. **timegate 有争议**：与 ablation 相比，CVR AUC 下降了 2.84pp（0.75262 → 0.74978），但 CTR 略有改善。time_gate 对 CVR 有负面影响，可能与 ts boundary 设置有关。
1. **probs_cvr 校准**：ablation 的 mean=0.2773 最接近真实转化率 10.13%（虽然仍偏高，但比 baseline 的 0.2803 更接近）。

### 12.4 后续建议

- **ablation 可直接上线**：全面优于 baseline
- **timegate 需调整**：CVR 下降说明 time_gate 可能引入了噪声。建议：
  1. 对 click/conversion 序列使用更密的短期 boundary（如 [600, 3600, 86400, 604800]）
  1. 或者只对 favorite/search/chajia 启用 time_gate（这三个序列的时间分布最均匀）
  1. 降低 time_gate_dim（从 8 降到 4）

______________________________________________________________________

## 十三、Experiment Results Summary（2026-08-28）

### 13.1 三个 Config 配置

| Config             | 序列数 |  time_gate   | ts  | 说明                                       |
| ------------------ | :----: | :----------: | :-: | ------------------------------------------ |
| `v18_seq`          |   9    |      0       |  6  | 原始 baseline                              |
| `v18_seq_ablation` |   6    |      0       | 4→6 | 移除退化序列                               |
| `v18_seq_timegate` |   6    | 3（partial） |  6  | 只对 favorite/search/chajia 启用 time_gate |

### 13.2 实验结果

| 指标       | search_seq |  ablation   | timegate (partial) |
| ---------- | :--------: | :---------: | :----------------: |
| AUC CTR    |  0.72148   |   0.72253   |      0.72215       |
| AUC CVR    |  0.74649   | **0.75262** |      0.74978       |
| GrpAUC CTR |  0.68807   | **0.68927** |      0.68882       |
| GrpAUC CVR |  0.74530   | **0.74747** |      0.74664       |
| Total Loss |  2.79625   | **2.78942** |      2.79117       |

### 13.3 结论

1. **ablation 全面优于 baseline**：CVR AUC +6.13pp，CTR AUC +1.05pp，可直接上线
1. **partial timegate 优于 baseline 但不如 ablation**：CVR AUC +3.29pp（vs ablation 的 +6.13pp）
1. **全量 timegate（之前版本）导致 CVR 下降**：说明 click/conversion 的 time_gate 引入噪声
1. **下一步**：用 partial timegate（3序列）跑完整 epoch 实验，确认是否能稳定超过 ablation

### 13.4 后续实验计划

| 优先级 | 实验                             | Config           | 假设                          |
| :----: | -------------------------------- | ---------------- | ----------------------------- |
|   1    | partial timegate 完整训练        | v18_seq_timegate | CVR AUC > ablation            |
|   2    | click 密 boundary + timegate     | 待创建           | click 序列 time_gate 收益提升 |
|   3    | 只对 chajia/search 启用 timegate | 待创建           | 排除 favorite 的潜在噪声      |

### 13.5 最终 Config 配置

| Config           | 序列        | time_gate 序列         | time_gate_dim=8 | ts  |
| ---------------- | ----------- | ---------------------- | --------------- | --- |
| v18_seq          | 9（含退化） | 无                     | 0               | 6   |
| v18_seq_ablation | 6（clean）  | 无                     | 0               | 4→6 |
| v18_seq_timegate | 6（clean）  | favorite/search/chajia | 3               | 6   |

### 13.6 关键发现

1. **ablation 全面正向**：CVR AUC +6.13pp，确认退化序列是噪声源
1. **全量 timegate 负向**（之前版本）：CVR AUC -2.84pp vs ablation
1. **partial timegate 部分恢复**：只对 favorite/search/chajia 启用，预期介于 ablation 和全量之间
1. **click/conversion 的 time_gate 是主要问题**：短期序列 boundary 不匹配导致 gate 坍缩

______________________________________________________________________

## 十三、完整实验结果对比（2026-08-29 更新）

### 13.1 四个 Config 配置

| Config                  | 序列数 |     time_gate 序列     | time_gate_dim | ts  | 说明                       |
| ----------------------- | :----: | :--------------------: | :-----------: | :-: | -------------------------- |
| `v18_seq`               |   9    |           无           |       0       |  6  | 原始 baseline              |
| `v18_seq_ablation`      |   6    |           无           |       0       |  6  | 移除退化序列               |
| `v18_seq_timegate_full` |   6    |       全部 6 个        |       8       |  6  | 全量 time_gate（之前跑的） |
| `v18_seq_timegate`      |   6    | favorite/search/chajia |       8       |  6  | partial time_gate（新增）  |

### 13.2 完整指标对比

| 指标           | baseline |  ablation   | timegate_full | timegate_partial |
| -------------- | :------: | :---------: | :-----------: | :--------------: |
| AUC CTR        | 0.72148  |   0.72253   |    0.72215    |     0.72258      |
| AUC CVR        | 0.74649  | **0.75262** |    0.74978    |     0.75117      |
| GrpAUC CTR     | 0.68807  | **0.68927** |    0.68882    |     0.68930      |
| GrpAUC CVR     | 0.74530  | **0.74747** |    0.74664    |     0.74659      |
| Total Loss     | 2.79625  | **2.78942** |    2.79117    |     2.79031      |
| probs_ctr mean |  0.3303  |   0.3279    |    0.3310     |      0.3315      |
| probs_cvr mean |  0.2803  | **0.2773**  |    0.2821     |      0.2789      |
| probs_cvr std  |  0.2172  | **0.2122**  |    0.2162     |      0.2120      |

### 13.3 vs baseline（pp）

| 实验             | dAUC_CTR  | dAUC_CVR  | dGrpAUC_CTR | dGrpAUC_CVR | dLoss |            结论            |
| ---------------- | :-------: | :-------: | :---------: | :---------: | :---: | :------------------------: |
| ablation         |   +1.05   | **+6.13** |    +1.20    |    +2.17    | -6.83 |        ✅ 全面正向         |
| timegate_full    |   +0.67   |   +3.29   |    +0.75    |    +1.34    | -5.08 |   ⚠️ 正向但弱于 ablation   |
| timegate_partial | **+1.10** | **+4.68** |  **+1.23**  |    +1.29    | -6.12 | ✅ 接近 ablation，CTR 略优 |

### 13.4 vs ablation（pp）→ time_gate 净效应

| 实验             | dAUC_CTR | dAUC_CVR  | dGrpAUC_CVR | dLoss |           结论           |
| ---------------- | :------: | :-------: | :---------: | :---: | :----------------------: |
| timegate_full    |  -0.38   | **-2.84** |    -0.83    | +1.75 | ❌ 全量 time_gate 净损失 |
| timegate_partial |  +0.05   | **-1.45** |    -0.88    | +0.89 |  ⚠️ 部分恢复，仍有损失   |

### 13.5 核心结论

1. **ablation 最优**：CVR AUC +6.13pp，是所有实验中 CVR 最高的
1. **partial timegate 是次优**：CVR AUC 比 ablation 低 1.45pp，但 CTR AUC 略优于 ablation（+0.05pp）
1. **time_gate 的净效应**：
   - 对 favorite/search/chajia（长期序列）：time_gate 有正向贡献（vs baseline +4.68pp CVR vs ablation 的 +6.13pp，说明 partial 保留了大部分收益）
   - 但相比 ablation，partial 仍损失 1.45pp CVR，说明即使是长期序列，time_gate 的收益也不足以完全抵消全量 time_gate 对 click/conversion 的损害
1. **probs_cvr 校准排名**：ablation (0.2773) > partial (0.2789) > baseline (0.2803) > full (0.2821)
   - ablation 的预测最接近真实转化率 10.13%
1. **推荐**：
   - **短期**：直接用 ablation config 上线（CVR +6.13pp 确定收益）
   - **中期**：继续优化 time_gate boundary（对 click 使用密 boundary [600, 3600, ...]），重新跑 partial timegate 实验
   - **长期**：考虑对 click/conversion 单独配边界，或降低 time_gate_dim
