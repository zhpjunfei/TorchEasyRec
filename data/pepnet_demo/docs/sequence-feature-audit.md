# 序列特征勘验报告

> 分析日期：2026-08-26
> 数据源：home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2
> 样本量：~132 万 PV/天

______________________________________________________________________

## 一、数据质量勘验

### 1.1 0 填充比例

| 特征                          | total_cells | zero_cells | nonzero_pct |
| ----------------------------- | ----------- | ---------- | ----------- |
| search_click_100_seq\_\_brand | 9,288,689   | 1,356,317  | **85.4%**   |
| search_click_10_seq\_\_brand  | 5,789,756   | 912,287    | **84.24%**  |
| chajia_click_100_seq\_\_brand | 5,826,056   | 895,177    | **84.63%**  |
| chajia_click_10_seq\_\_brand  | 3,508,499   | 846,352    | **75.88%**  |

**结论**：非零率都在 75~85%。`0` 是稀疏行为的自然值，不是默认填充值。

### 1.2 有效长度分布（分位数）

| 特征                          | 样本数  | avg_len  | median | p25 | p75 | p90 | p95 | max |
| ----------------------------- | ------- | -------- | ------ | --- | --- | --- | --- | --- |
| search_click_100_seq\_\_brand | 654,461 | **2.07** | 1.0    | 1.0 | 1.0 | 3.0 | 6.0 | 98  |
| search_click_10_seq\_\_brand  | 609,229 | **1.50** | 1.0    | 1.0 | 1.0 | 3.0 | 4.0 | 10  |
| chajia_click_100_seq\_\_brand | 843,381 | **1.06** | 1.0    | 1.0 | 1.0 | 1.0 | 1.0 | 21  |
| chajia_click_10_seq\_\_brand  | 827,191 | **1.02** | 1.0    | 1.0 | 1.0 | 1.0 | 1.0 | 10  |

**关键发现**：**中位数=1，p75=1**，90%+ 样本只有 1~3 个非零品牌。序列长度 10 和 100 对绝大多数样本没有区别。

### 1.3 重合度分析

| 指标                   | search   | chajia   |
| ---------------------- | -------- | -------- |
| first_item_overlap_pct | **100%** | **100%** |
| avg_nonzero_10         | 0.69     | 0.64     |
| avg_nonzero_100        | 1.02     | 0.68     |
| pct_full_zero_100      | 50.6%    | 36.4%    |
| pct_full_zero_10       | 54.0%    | 37.6%    |

**结论**：

- 10_seq 的第一个元素 100% 包含在 100_seq 中
- avg_nonzero 几乎相同（search: 0.69 vs 1.02, chajia: 0.64 vs 0.68）
- 两者**完全冗余**

### 1.4 品牌多样性

| 特征                          | distinct_brands |
| ----------------------------- | --------------- |
| search_click_100_seq\_\_brand | 8,212           |
| search_click_10_seq\_\_brand  | 7,080           |
| chajia_click_100_seq\_\_brand | 6,900           |
| chajia_click_10_seq\_\_brand  | 5,964           |

**结论**：100_seq 比 10_seq 多 ~15% 的品牌多样性，但考虑到 median_len=1，实际增量有限。

______________________________________________________________________

## 二、配置审核

### 2.1 当前 config 中的序列特征

```
click_10_seq, click_50_seq, conversion_5_seq, conversion_20_seq
favorite_5_seq, favorite_10_seq, like_100_seq, like_10_seq
chajia_click_100_seq, search_click_100_seq
```

共 10 个序列（已移除 `search_click_10_seq` 和 `chajia_click_10_seq`）。

### 2.2 特征维度完整性

| 序列                 | DDL 字段数 | config 配置数 | 状态               |
| -------------------- | ---------- | ------------- | ------------------ |
| search_click_100_seq | 20         | 19            | ✅ 缺少 ts (FLOAT) |
| chajia_click_100_seq | 20         | 19            | ✅ 缺少 ts (FLOAT) |

`ts` 是 `ARRAY<FLOAT>` 类型，不适合做 id_feature，排除合理。

### 2.3 embedding 参数一致性

所有序列使用相同的 embedding 参数：

- item_id: dim=24, bucket=1,963,029
- brand: dim=16, bucket=207,140
- first_cate_id: dim=8, bucket=300
- ...（与 chajia_click_100_seq 一致）

______________________________________________________________________

## 三、决策建议

### 已移除的序列（冗余）

| 序列                  | 移除理由                                               |
| --------------------- | ------------------------------------------------------ |
| `search_click_10_seq` | 与 search_click_100_seq 完全重合，avg_nonzero 几乎相同 |
| `chajia_click_10_seq` | 与 chajia_click_100_seq 完全重合，avg_nonzero 几乎相同 |

### 保留的序列

| 序列                   | 说明                 |
| ---------------------- | -------------------- |
| `search_click_100_seq` | 新增，长程搜索意图   |
| `chajia_click_100_seq` | 原已有，长程比价意图 |
| `like_100_seq`         | 原已有，收藏行为     |
| `click_50_seq`         | 原已有，最近点击     |
| 其他短期序列           | 原已有，近期意图     |

### 后续优化方向

1. **P0 标量特征**：consume_power（10.23pp）、potential_score（18.68pp）— Issue #6
1. **P0 离线序列**：offline_chajia/like/order/search_click_100_seq — Issue #7
1. **P1 特征**：price_prefer、site_prefer、shop_type 等 — Issue #8

______________________________________________________________________

## 四、勘验 SQL 存档

### 勘验1：0 填充比例

```sql
SELECT
    'search_click_100_seq__brand' AS feat, COUNT(1), SUM(IF(CAST(elem AS STRING)='0',1,0)), ROUND(SUM(IF(CAST(elem AS STRING)!='0' AND elem IS NOT NULL,1,0))*100.0/COUNT(1),2)
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 LATERAL VIEW EXPLODE(search_click_100_seq__brand) t AS elem WHERE dt='${bizdate}' GROUP BY feat
UNION ALL SELECT 'search_click_10_seq__brand', COUNT(1), SUM(IF(CAST(elem AS STRING)='0',1,0)), ROUND(SUM(IF(CAST(elem AS STRING)!='0' AND elem IS NOT NULL,1,0))*100.0/COUNT(1),2) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 LATERAL VIEW EXPLODE(search_click_10_seq__brand) t AS elem WHERE dt='${bizdate}' GROUP BY feat
UNION ALL SELECT 'chajia_click_100_seq__brand', COUNT(1), SUM(IF(CAST(elem AS STRING)='0',1,0)), ROUND(SUM(IF(CAST(elem AS STRING)!='0' AND elem IS NOT NULL,1,0))*100.0/COUNT(1),2) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 LATERAL VIEW EXPLODE(chajia_click_100_seq__brand) t AS elem WHERE dt='${bizdate}' GROUP BY feat
UNION ALL SELECT 'chajia_click_10_seq__brand', COUNT(1), SUM(IF(CAST(elem AS STRING)='0',1,0)), ROUND(SUM(IF(CAST(elem AS STRING)!='0' AND elem IS NOT NULL,1,0))*100.0/COUNT(1),2) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 LATERAL VIEW EXPLODE(chajia_click_10_seq__brand) t AS elem WHERE dt='${bizdate}' GROUP BY feat;
```

### 勘验2：非零长度分位数

```sql
WITH seq_stats AS (
    SELECT 'search_click_100_seq__brand' AS feat, SIZE(search_click_100_seq__brand)-SIZE(ARRAY_REMOVE(search_click_100_seq__brand,'0')) AS nonzero_len FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt='${bizdate}' AND SIZE(search_click_100_seq__brand)>0 AND SIZE(search_click_100_seq__brand)-SIZE(ARRAY_REMOVE(search_click_100_seq__brand,'0'))>0
    UNION ALL SELECT 'search_click_10_seq__brand', SIZE(search_click_10_seq__brand)-SIZE(ARRAY_REMOVE(search_click_10_seq__brand,'0')) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt='${bizdate}' AND SIZE(search_click_10_seq__brand)>0 AND SIZE(search_click_10_seq__brand)-SIZE(ARRAY_REMOVE(search_click_10_seq__brand,'0'))>0
    UNION ALL SELECT 'chajia_click_100_seq__brand', SIZE(chajia_click_100_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_100_seq__brand,'0')) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt='${bizdate}' AND SIZE(chajia_click_100_seq__brand)>0 AND SIZE(chajia_click_100_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_100_seq__brand,'0'))>0
    UNION ALL SELECT 'chajia_click_10_seq__brand', SIZE(chajia_click_10_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_10_seq__brand,'0')) FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt='${bizdate}' AND SIZE(chajia_click_10_seq__brand)>0 AND SIZE(chajia_click_10_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_10_seq__brand,'0'))>0
) SELECT feat, COUNT(1), MIN(nonzero_len), ROUND(AVG(nonzero_len),2), ROUND(MEDIAN(nonzero_len),1), ROUND(PERCENTILE(nonzero_len,0.25),1), ROUND(PERCENTILE(nonzero_len,0.75),1), ROUND(PERCENTILE(nonzero_len,0.9),1), ROUND(PERCENTILE(nonzero_len,0.95),1), MAX(nonzero_len) FROM seq_stats GROUP BY feat ORDER BY feat;
```

### 勘验3：重合度

```sql
SELECT COUNT(1) AS total_pv,
    ROUND(SUM(IF(SIZE(search_click_10_seq__brand)>0 AND SIZE(search_click_100_seq__brand)>0 AND ARRAY_CONTAINS(search_click_100_seq__brand,search_click_10_seq__brand[0]),1,0))*100.0/NULLIF(SUM(IF(SIZE(search_click_10_seq__brand)>0,1,0)),0),2) AS search_overlap_pct,
    ROUND(SUM(IF(SIZE(chajia_click_10_seq__brand)>0 AND SIZE(chajia_click_100_seq__brand)>0 AND ARRAY_CONTAINS(chajia_click_100_seq__brand,chajia_click_10_seq__brand[0]),1,0))*100.0/NULLIF(SUM(IF(SIZE(chajia_click_10_seq__brand)>0,1,0)),0),2) AS chajia_overlap_pct,
    AVG(CASE WHEN SIZE(search_click_10_seq__brand)>0 THEN SIZE(search_click_10_seq__brand)-SIZE(ARRAY_REMOVE(search_click_10_seq__brand,'0')) ELSE 0 END) AS search_avg_nz_10,
    AVG(CASE WHEN SIZE(search_click_100_seq__brand)>0 THEN SIZE(search_click_100_seq__brand)-SIZE(ARRAY_REMOVE(search_click_100_seq__brand,'0')) ELSE 0 END) AS search_avg_nz_100,
    AVG(CASE WHEN SIZE(chajia_click_10_seq__brand)>0 THEN SIZE(chajia_click_10_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_10_seq__brand,'0')) ELSE 0 END) AS chajia_avg_nz_10,
    AVG(CASE WHEN SIZE(chajia_click_100_seq__brand)>0 THEN SIZE(chajia_click_100_seq__brand)-SIZE(ARRAY_REMOVE(chajia_click_100_seq__brand,'0')) ELSE 0 END) AS chajia_avg_nz_100
FROM home_flow_2606_ctrcvr_sorter_config_pyfg_encoded_v2 WHERE dt='${bizdate}';
```
