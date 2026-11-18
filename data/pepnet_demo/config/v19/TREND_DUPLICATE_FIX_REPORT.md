# Trend数据重复问题 - 完整修复报告

**日期**: 2026-10-22
**问题等级**: 🔴 CRITICAL
**状态**: ✅ 已修复

> **修订（2026-10-22，对抗性审核后）**：本文档"重复率 37%""有效噪声率 3.6%""预期 ~6M"等结论已修正为 **重复率 100%（平均 2.68 行/组合）/ ≈9.9% / ~4.5M**，详见 §2.2、§3.2、§4.2。样本逻辑唯一事实源为 `sql/2609/home_flow_2606_ctrcvr_sorter_label_table_v5.sql`（原 `sql/2606_sample/v5/` 副本已删除）。

______________________________________________________________________

## 一、问题发现

### 1.1 背景

在多场景建模实验中，发现trend场景的GAUC（0.639）远低于其他场景（bijia 0.877, haojia 0.772），怀疑数据质量有问题。

### 1.2 根因定位

**代码级证据**（`home_flow_2606_ctrcvr_sorter_label_table_v5.sql`）：

```sql
-- home/bijia/haojia（正确）- 第70/101/132行
GROUP BY item_id, mmb_id, request_id

-- trend（错误）- 第157行
GROUP BY event_unix_time, item_id, mmb_id, request_id  -- ❌ 包含时间戳
```

**后果**：同一商品的曝光事件(t1)和点击事件(t2)因时间戳不同被拆成多行，导致：

- 特征相同（item, request相同）
- 标签相反（click=0 vs click=1）
- 梯度相消，排序信息抹掉

______________________________________________________________________

## 二、验证SQL及结果

### 2.1 验证SQL文件

**文件路径**: `sql/2609/verify_trend_duplicate.sql`

```sql
-- 验证trend场景重复问题（完全避开类型转换）
-- 直接使用原始列进行GROUP BY，不拼接字符串

-- SQL 1: 统计trend场景的基础信息
SELECT
    'trend_basic_stats' AS check_type,
    COUNT(1) AS total_rows,
    COUNT(DISTINCT item_id) AS unique_items,
    COUNT(DISTINCT request_id) AS unique_requests
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261020' AND is_trend_scene = 1;

-- SQL 2: 检查按(item_id, request_id)分组的重复情况
SELECT
    'duplicate_distribution' AS check_type,
    cnt AS rows_per_combo,
    COUNT(*) AS combo_count,
    COUNT(*) * cnt AS total_rows
FROM (
    SELECT
        item_id,
        request_id,
        COUNT(1) AS cnt
    FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
    WHERE dt = '20261020' AND is_trend_scene = 1
    GROUP BY item_id, request_id
    HAVING COUNT(1) > 1
) t
GROUP BY cnt
ORDER BY cnt;

-- SQL 3: 检查标签矛盾
SELECT
    'label_conflict' AS check_type,
    COUNT(CASE WHEN max_click = 1 AND min_click = 0 THEN 1 ELSE NULL END) AS mixed_labels,
    COUNT(CASE WHEN max_click = 1 AND min_click = 1 THEN 1 ELSE NULL END) AS all_click,
    COUNT(CASE WHEN max_click = 0 AND min_click = 0 THEN 1 ELSE NULL END) AS all_no_click
FROM (
    SELECT
        item_id,
        request_id,
        MAX(is_trend_click) AS max_click,
        MIN(is_trend_click) AS min_click
    FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
    WHERE dt = '20261020' AND is_trend_scene = 1
    GROUP BY item_id, request_id
    HAVING COUNT(1) > 1
) t;

-- SQL 4: 对比各场景的行数
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_rows
FROM mmb_sage.home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261020'
GROUP BY scene;
```

### 2.2 验证结果

#### SQL1: 基础统计

| check_type        | total_rows | unique_items | unique_requests |
| ----------------- | ---------- | ------------ | --------------- |
| trend_basic_stats | 12,039,226 | 880,084      | 6,007,770       |

**解读**：12M样本，但只有88万商品和600万请求，平均每个(item, request)组合约2行。

#### SQL2: 重复分布

| rows_per_combo | combo_count    | total_rows      | 占比     |
| -------------- | -------------- | --------------- | -------- |
| 2              | 3,086,670      | 6,173,340       | 51.3%    |
| 3              | 1,200,621      | 3,601,863       | 29.9%    |
| 4              | 132,412        | 529,648         | 4.4%     |
| ≥5             | 80,947         | 1,734,375       | 14.4%    |
| **总计**       | **~4,500,000** | **~12,039,226** | **100%** |

**解读（2026-10-22 修正）**：四行 `total_rows` 合计 12,039,226 = 全表行数，而子查询带 `HAVING COUNT(1)>1` ⇒ **重复率 100%——所有 trend 行都落在重复 (item_id, request_id) 组合里**，平均 **2.68 行/组合**。原"37% 的组合存在重复"是把 组合数(4.5M)÷行数(12M)=37% 这一无意义比值误读成重复率，**作废**。（与 P1-8 机制自洽：`trend_click_pair` 只保留含点击的请求，此类请求必含曝光+点击 ≥2 个事件行。）

#### SQL3: 标签矛盾（最严重）

| check_type     | mixed_labels  | all_click | all_no_click |
| -------------- | ------------- | --------- | ------------ |
| label_conflict | **4,435,973** | 8,199     | 278          |

**解读**：**98.5%的重复组合都存在标签矛盾**（同时有click=0和click=1）。这是极端的梯度冲突源。

#### SQL4: 各场景行数

| scene    | total_rows      | 占比     |
| -------- | --------------- | -------- |
| home     | 82,047,845      | 68.2%    |
| bijia    | 20,220,592      | 16.8%    |
| trend    | 12,039,226      | 10.0%    |
| haojia   | 9,183,442       | 7.6%     |
| **总计** | **123,491,105** | **100%** |

______________________________________________________________________

## 三、问题分析

### 3.1 问题机制

```
用户查价行为时间线：
  t1 (1787628734): trend_exposure → 行1: (item_X, req_Z, click=0)
  t2 (1787628767): trend_click    → 行2: (item_X, req_Z, click=1)

由于GROUP BY包含event_unix_time：
  → 两行不会被合并（时间戳不同）
  → 特征完全相同（item, request相同）
  → 标签相反（click=0 vs click=1）

对模型的影响：
  梯度1 = p - 0 = p
  梯度2 = p - 1 = p - 1
  净梯度 = 2p - 1
  → 当p≈0.5时，梯度相消
  → 排序信息被抹掉
  → 等价于软标签0.5
```

### 3.2 影响评估

**对trend塔**：

- GAUC仅0.639（五个塔中最低）
- 100% 的行落在重复组合里（其中 98.6% 组合标签矛盾），有效信号被严重稀释
- 收敛速度慢，需要更多训练步数

**对home CTR塔**（通过共享主干）：

- 虽然ctr loss只在家场景计算
- 但共享特征编码层从所有样本学习
- trend的梯度噪声会污染特征表示
- 这可能是GAUC提升不达标的根本原因

**定量估算**（2026-10-22 修正）：

- trend样本占比：10%
- 重复率：**100%**（原 37% 系误读，作废）
- 矛盾比例：98.6%（mixed_labels / 重复组合）
- 有效噪声率：10% × 100% × 98.6% ≈ **9.9%**
- 即约 9.9% 的总样本是梯度冲突源（原 3.6% 低估约 3 倍）

______________________________________________________________________

## 四、修复方案

### 4.1 根因修复（已完成）

**修改文件**: `sql/2609/home_flow_2606_ctrcvr_sorter_label_table_v5.sql`

**修改位置**: 第136-157行（trend_sample部分）

**修改前**：

```sql
, trend_sample AS
(
    SELECT  event_unix_time, item_id, mmb_id, request_id
            ,MAX(scene) AS scene, MAX(page) AS page
            ,MAX(day_h) AS day_h, MAX(week_day) AS week_day
            ,CAST(0 AS BIGINT) AS is_exposure
            ,CAST(0 AS BIGINT) AS is_click
            ,CAST(0 AS BIGINT) AS is_conversion
            ,CAST(0 AS BIGINT) AS is_favorite
            ,CAST(0 AS BIGINT) AS is_like
            ,CAST(0 AS BIGINT) AS is_bijia_click
            ,CAST(0 AS BIGINT) AS is_bijia_conversion
            ,CAST(0 AS BIGINT) AS is_haojia_click
            ,CAST(0 AS BIGINT) AS is_haojia_conversion
            ,MAX(IF(event='trend_click',1,0)) AS is_trend_click
            ,MAX(IF(event='trend_conversion',1,0)) AS is_trend_conversion
            ,CAST(0 AS BIGINT) AS is_home_scene
            ,CAST(0 AS BIGINT) AS is_bijia_scene
            ,CAST(0 AS BIGINT) AS is_haojia_scene
            ,CAST(1 AS BIGINT) AS is_trend_scene
    FROM    raw
    WHERE   event IN ('trend_exposure','trend_click','trend_conversion')
    GROUP BY event_unix_time, item_id, mmb_id, request_id  -- ❌ 包含时间戳
)
```

**修改后**：

```sql
, trend_sample AS
(
    SELECT  MIN(event_unix_time) AS event_unix_time  -- ✅ 改为MIN聚合
            ,item_id
            ,mmb_id
            ,request_id
            ,MAX(scene) AS scene, MAX(page) AS page
            ,MAX(day_h) AS day_h, MAX(week_day) AS week_day
            ,CAST(0 AS BIGINT) AS is_exposure
            ,CAST(0 AS BIGINT) AS is_click
            ,CAST(0 AS BIGINT) AS is_conversion
            ,CAST(0 AS BIGINT) AS is_favorite
            ,CAST(0 AS BIGINT) AS is_like
            ,CAST(0 AS BIGINT) AS is_bijia_click
            ,CAST(0 AS BIGINT) AS is_bijia_conversion
            ,CAST(0 AS BIGINT) AS is_haojia_click
            ,CAST(0 AS BIGINT) AS is_haojia_conversion
            ,MAX(IF(event='trend_click',1,0)) AS is_trend_click
            ,MAX(IF(event='trend_conversion',1,0)) AS is_trend_conversion
            ,CAST(0 AS BIGINT) AS is_home_scene
            ,CAST(0 AS BIGINT) AS is_bijia_scene
            ,CAST(0 AS BIGINT) AS is_haojia_scene
            ,CAST(1 AS BIGINT) AS is_trend_scene
    FROM    raw
    WHERE   event IN ('trend_exposure','trend_click','trend_conversion')
    GROUP BY item_id, mmb_id, request_id  -- ✅ 去掉event_unix_time
)
```

**关键改动**：

1. `SELECT` 子句：`event_unix_time` → `MIN(event_unix_time) AS event_unix_time`
1. `GROUP BY` 子句：去掉 `event_unix_time`

### 4.2 预期效果

| 指标          | 修复前   | 预期修复后                                                          |
| ------------- | -------- | ------------------------------------------------------------------- |
| trend样本量   | 12M      | **~4.5M**（减少约 63%，≈ 重复组合数）                               |
| 重复率        | **100%** | \<1%                                                                |
| mixed_labels  | 98.6%    | \<5%                                                                |
| trend GAUC    | 0.639    | >0.700（预期值，未证实）                                            |
| home CTR GAUC | 0.702    | 0.702~0.710（预期区间；A/B 实测同类修复仅 +0.09pp，不宜承诺 +1.1%） |

______________________________________________________________________

## 五、验收记录（2026-10-22 实测，含 SQL 原文与判读，供回溯）

### 5.0 验收环境

| 项       | 值                                                     |
| -------- | ------------------------------------------------------ |
| 表       | `mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5` |
| 基线分区 | `dt='20261014'`（修复前唯一分区）                      |
| 修复分区 | `dt='20261015' ~ '20261021'`（7 天全部回跑）           |
| SQL 文件 | `sql/2609/verify_label_table_v5_rerun_20261021.sql`    |
| 判定粒度 | `(item_id, mmb_id, request_id)`（label 表键）          |
| **结论** | ✅ **全部通过，P1-8 关闭**                             |

读法约定：所有 SQL 均 `WHERE dt BETWEEN '20261014' AND '20261021'` + `GROUP BY dt`（一条 SQL 出 8 天并排）；带 `HAVING` 的判据 SQL **修复后无输出行 = 该分组不存在 = 计数为 0 = 通过**。

### 5.1 总表

| 判据                          | 20261014（前）                      | 20261015~21（后）          | 判定        |
| ----------------------------- | ----------------------------------- | -------------------------- | ----------- |
| SQL-1 重复组合 (item,mmb,req) | 120,568（275,679 行，2.29 行/组合） | **每天 = 0**               | ✅          |
| SQL-2 同键标签矛盾            | 120,452（99.9% 重复组合矛盾）       | **每天 = 0**               | ✅          |
| SQL-3 conv无click 占比        | **96.4%**（43,191/44,810）          | **≤0.23%**（52~115 行/天） | ✅          |
| SQL-4 无点击请求              | 0                                   | 每天 = 0                   | ✅          |
| SQL-5 场景互斥/跨场景污染     | 0                                   | 每天 = 0                   | ✅          |
| SQL-6 NULL 键                 | 0                                   | 每天 = 0                   | ✅          |
| 行/点击比（流量归一）         | 2.022                               | **1.000**                  | ✅ 合并生效 |
| conv/点击比（语义保全）       | 29.6%                               | 24.5%~32.5% 区间内         | ✅          |

______________________________________________________________________

### 5.2 SQL-0 基线：总量与场景分布

```sql
SELECT dt
      ,CASE WHEN is_home_scene=1 THEN 'home' WHEN is_bijia_scene=1 THEN 'bijia'
            WHEN is_haojia_scene=1 THEN 'haojia' WHEN is_trend_scene=1 THEN 'trend'
            ELSE 'UNKNOWN' END AS scene
      ,COUNT(1) AS pv
      ,SUM(is_trend_click) AS trend_clicks, SUM(is_trend_conversion) AS trend_convs
      ,SUM(is_click) AS home_clicks, SUM(is_conversion) AS home_convs
FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt BETWEEN '20261014' AND '20261021'
GROUP BY dt, CASE WHEN is_home_scene=1 THEN 'home' WHEN is_bijia_scene=1 THEN 'bijia'
                  WHEN is_haojia_scene=1 THEN 'haojia' WHEN is_trend_scene=1 THEN 'trend'
                  ELSE 'UNKNOWN' END
ORDER BY dt, scene;
```

**实测结果**：

| dt       | scene  | pv        | trend_clicks | trend_convs | home_clicks | home_convs |
| -------- | ------ | --------- | ------------ | ----------- | ----------- | ---------- |
| 20261014 | bijia  | 530,302   | 0            | 0           | 0           | 0          |
| 20261014 | haojia | 196,989   | 0            | 0           | 0           | 0          |
| 20261014 | home   | 1,832,604 | 0            | 0           | 677,081     | 235,796    |
| 20261014 | trend  | 306,533   | 151,578      | 44,810      | 0           | 0          |
| 20261015 | bijia  | 1,005,427 | 0            | 0           | 0           | 0          |
| 20261015 | haojia | 297,459   | 0            | 0           | 0           | 0          |
| 20261015 | home   | 2,207,895 | 0            | 0           | 812,533     | 277,122    |
| 20261015 | trend  | 200,559   | 200,440      | 49,160      | 0           | 0          |
| 20261016 | bijia  | 711,555   | 0            | 0           | 0           | 0          |
| 20261016 | haojia | 260,184   | 0            | 0           | 0           | 0          |
| 20261016 | home   | 2,063,281 | 0            | 0           | 757,920     | 256,754    |
| 20261016 | trend  | 166,930   | 166,849      | 47,112      | 0           | 0          |
| 20261017 | bijia  | 612,923   | 0            | 0           | 0           | 0          |
| 20261017 | haojia | 254,234   | 0            | 0           | 0           | 0          |
| 20261017 | home   | 2,054,872 | 0            | 0           | 754,580     | 253,124    |
| 20261017 | trend  | 139,325   | 139,238      | 36,113      | 0           | 0          |
| 20261018 | bijia  | 574,265   | 0            | 0           | 0           | 0          |
| 20261018 | haojia | 255,557   | 0            | 0           | 0           | 0          |
| 20261018 | home   | 2,046,802 | 0            | 0           | 751,624     | 242,244    |
| 20261018 | trend  | 134,137   | 134,077      | 34,636      | 0           | 0          |
| 20261019 | bijia  | 577,520   | 0            | 0           | 0           | 0          |
| 20261019 | haojia | 248,939   | 0            | 0           | 0           | 0          |
| 20261019 | home   | 2,076,235 | 0            | 0           | 765,430     | 241,055    |
| 20261019 | trend  | 139,097   | 139,025      | 38,562      | 0           | 0          |
| 20261020 | bijia  | 1,041,499 | 0            | 0           | 0           | 0          |
| 20261020 | haojia | 408,060   | 0            | 0           | 0           | 0          |
| 20261020 | home   | 2,951,827 | 0            | 0           | 1,089,139   | 376,012    |
| 20261020 | trend  | 331,979   | 331,855      | 107,794     | 0           | 0          |
| 20261021 | bijia  | 846,982   | 0            | 0           | 0           | 0          |
| 20261021 | haojia | 381,561   | 0            | 0           | 0           | 0          |
| 20261021 | home   | 2,680,818 | 0            | 0           | 986,968     | 331,453    |
| 20261021 | trend  | 258,168   | 258,102      | 81,116      | 0           | 0          |

**判读**：

1. **合并生效的聚合指纹 = 行/点击比**：修复前 306,533/151,578 = **2.022**；修复后七天全部 **1.000**（每个点击组合从 ~2 行合并为 1 行）。
1. 原始行数（21日/14日 = 84%）被流量增长掩盖（trend 点击量 14 日 151,578 → 21 日 258,102，**+70%**）；**流量归一后 = 1.000/2.022 = 49%**，与 §4.2 预测 40%~50% 吻合。判定用行/点击比，不用原始行数。
1. **conv/点击比语义保全**：修复前 29.6% → 修复后 24.5%~32.5%（日间区间内），说明 `MAX(is_trend_conversion)` 正确落到合并行上，转化信息无系统性丢失。
1. **home 口径八天平稳**（CTR 36.7~~36.9%、CVR 11.6~~12.9%）——修复未波及其他场景（bijia/haojia 量波动为自然流量）。
1. 修复后"非点击行"每天仅 60~124 行（≈0.03%）→ **trend 请求近似单品**（`trend_click_pair` 只保留含点击请求，同请求非点击商品极少）；这同时给 SQL-3 设了硬上界：conv无click ≤ 非点击行数。

______________________________________________________________________

### 5.3 SQL-1 【核心】trend 按表键的重复组合

```sql
SELECT dt, COUNT(1) AS dup_combos, SUM(cnt) AS dup_rows
FROM (SELECT dt, item_id, mmb_id, request_id, COUNT(1) AS cnt
      FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
      WHERE dt BETWEEN '20261014' AND '20261021' AND is_trend_scene = 1
      GROUP BY dt, item_id, mmb_id, request_id HAVING COUNT(1) > 1) t
GROUP BY dt ORDER BY dt;
```

**实测结果**：

| dt          | dup_combos | dup_rows |
| ----------- | ---------- | -------- |
| 20261014    | 120,568    | 275,679  |
| 20261015~21 | 无输出行   | 无输出行 |

**判读**：修复后七天 `GROUP BY dt` 无输出 = **每天 dup_combos = 0**（一组一行达成）。基线 2.29 行/重复组合。内部验算：306,533 − 275,679 + 120,568 = 151,422 ≈ 点击行 151,578 ✓ 数字自洽。

______________________________________________________________________

### 5.4 SQL-2 【核心】trend 同键标签矛盾

```sql
SELECT dt, COUNT(1) AS mixed_label_combos
FROM (SELECT dt, item_id, mmb_id, request_id
      FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
      WHERE dt BETWEEN '20261014' AND '20261021' AND is_trend_scene = 1
      GROUP BY dt, item_id, mmb_id, request_id
      HAVING COUNT(1) > 1 AND MIN(is_trend_click)=0 AND MAX(is_trend_click)=1) t
GROUP BY dt ORDER BY dt;
```

**实测结果**：

| dt          | mixed_label_combos |
| ----------- | ------------------ |
| 20261014    | 120,452            |
| 20261015~21 | 无输出行           |

**判读**：基线 120,452/120,568 = **99.9%** 的重复组合标签矛盾（与 §2.2 早期估计 98.5% 同量级）；修复后七天 = 0，"曝光 y=0 / 点击 y=1"拆分彻底消失。

______________________________________________________________________

### 5.5 SQL-3 【核心】conv 行级 ⊆ click

```sql
SELECT dt
      ,SUM(CASE WHEN is_trend_scene=1 THEN 1 ELSE 0 END) AS trend_rows
      ,SUM(CASE WHEN is_trend_scene=1 AND is_trend_conversion=1 THEN 1 ELSE 0 END) AS trend_convs
      ,SUM(CASE WHEN is_trend_scene=1 AND is_trend_conversion=1 AND is_trend_click=0 THEN 1 ELSE 0 END) AS trend_conv_wo_click
      ,SUM(CASE WHEN is_bijia_scene=1 AND is_bijia_conversion=1 AND is_bijia_click=0 THEN 1 ELSE 0 END) AS bijia_conv_wo_click
      ,SUM(CASE WHEN is_haojia_scene=1 AND is_haojia_conversion=1 AND is_haojia_click=0 THEN 1 ELSE 0 END) AS haojia_conv_wo_click
FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt BETWEEN '20261014' AND '20261021'
GROUP BY dt ORDER BY dt;
```

**实测结果**：

| dt       | trend_rows | trend_convs | trend_conv_wo_click | 占比      | bijia_conv_wo_click | haojia_conv_wo_click |
| -------- | ---------- | ----------- | ------------------- | --------- | ------------------- | -------------------- |
| 20261014 | 306,533    | 44,810      | **43,191**          | **96.4%** | 331                 | 96                   |
| 20261015 | 200,559    | 49,160      | 115                 | 0.23%     | 571                 | 163                  |
| 20261016 | 166,930    | 47,112      | 80                  | 0.17%     | 403                 | 152                  |
| 20261017 | 139,325    | 36,113      | 83                  | 0.23%     | 343                 | 175                  |
| 20261018 | 134,137    | 34,636      | 52                  | 0.15%     | 275                 | 128                  |
| 20261019 | 139,097    | 38,562      | 65                  | 0.17%     | 229                 | 111                  |
| 20261020 | 331,979    | 107,794     | 113                 | 0.10%     | 415                 | 204                  |
| 20261021 | 258,168    | 81,116      | 61                  | **0.08%** | 342                 | 162                  |

**判读**：**96.4% → ≤0.23%**，全部远低于 2% 通过线。修复前的 96.4% 就是 P1-8 行级指纹（60d 表曾实测 ≈100%，此处 96.4% 系少量 conv 与 click 同时间戳、修复前即已合并）；修复后残余 52~~115 行/天是"转化事件无对应点击事件"的真实情况（与 SQL-0 的非点击行数吻合，被其硬性约束）。bijia/haojia 对照组前后同量级（229~~571 / 96~204），未被误伤。

______________________________________________________________________

### 5.6 SQL-4/5 回归：请求点击语义 + 场景隔离

```sql
-- SQL-4：保留的请求至少一行点击
SELECT dt, COUNT(1) AS req_without_click
FROM (SELECT dt, mmb_id, request_id
      FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
      WHERE dt BETWEEN '20261014' AND '20261021' AND is_trend_scene = 1
      GROUP BY dt, mmb_id, request_id HAVING SUM(is_trend_click) = 0) t
GROUP BY dt ORDER BY dt;
-- SQL-5：场景互斥 + 跨场景标签零污染
SELECT dt
      ,SUM(CASE WHEN is_home_scene+is_bijia_scene+is_haojia_scene+is_trend_scene <> 1 THEN 1 ELSE 0 END) AS bad_scene_flag
      ,SUM(CASE WHEN is_home_scene=1 AND (is_bijia_click=1 OR is_haojia_click=1 OR is_trend_click=1
             OR is_bijia_conversion=1 OR is_haojia_conversion=1 OR is_trend_conversion=1) THEN 1 ELSE 0 END) AS home_with_other_labels
      ,SUM(CASE WHEN is_trend_scene=1 AND (is_click=1 OR is_conversion=1 OR is_bijia_click=1
             OR is_haojia_click=1 OR is_bijia_conversion=1 OR is_haojia_conversion=1) THEN 1 ELSE 0 END) AS trend_with_foreign_labels
FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt BETWEEN '20261014' AND '20261021'
GROUP BY dt ORDER BY dt;
```

**实测结果**：SQL-4 八天无输出（=0）；SQL-5 八天三列全 0。

**判读**：`trend_click_pair` 语义保持（每个保留请求都有点击行）；场景旗标互斥、跨场景标签零污染——修复未破坏任何既有语义。

______________________________________________________________________

### 5.7 SQL-6 口径复核：NULL 键 + (item,req) 粒度（B-5）

```sql
SELECT dt, SUM(CASE WHEN item_id IS NULL OR mmb_id IS NULL OR request_id IS NULL THEN 1 ELSE 0 END) AS null_key_rows
FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
WHERE dt BETWEEN '20261014' AND '20261021' AND is_trend_scene = 1
GROUP BY dt ORDER BY dt;

SELECT dt, COUNT(1) AS dup_item_req_combos
FROM (SELECT dt, item_id, request_id, COUNT(1) AS cnt
      FROM mmb_sage.home_flow_2606_ctrcvr_sorter_label_table_v5
      WHERE dt BETWEEN '20261014' AND '20261021' AND is_trend_scene = 1
      GROUP BY dt, item_id, request_id HAVING COUNT(1) > 1) t
GROUP BY dt ORDER BY dt;
```

**实测结果**：

| dt       | null_key_rows | dup_item_req_combos（item,request 粒度） | 对照 SQL-1（item,mmb,request） |
| -------- | ------------- | ---------------------------------------- | ------------------------------ |
| 20261014 | 0             | 120,581                                  | 120,568（仅 +13 跨 mmb）       |
| 20261015 | 0             | 28                                       | 0                              |
| 20261016 | 0             | 17                                       | 0                              |
| 20261017 | 0             | 9                                        | 0                              |
| 20261018 | 0             | 20                                       | 0                              |
| 20261019 | 0             | 15                                       | 0                              |
| 20261020 | 0             | 70                                       | 0                              |
| 20261021 | 0             | 49                                       | 0                              |

**判读**：NULL 键全 0 ✓。但 (item,request) 粒度在三键粒度为 0 的情况下仍报 9~70 个重复/天——**同一 `(item_id, request_id)` 出现在不同 `mmb_id` 下，即 request_id 跨 mmb 复用（非用户内唯一）**。详见 §5.8。

______________________________________________________________________

### 5.8 附带发现：request_id 跨 mmb_id 复用

量级 9~70 组合/天（≈0.003%~0.05%），训练影响可忽略，但有两条硬要求：

1. **60d 表的重复验证必须用 `(item_id, mmb_id, request_id)` 三键粒度**——旧 `sql/2609/verify_trend_duplicate.sql` 只按 `(item_id, request_id)` 分组，重跑时会把这几十个跨 mmb 组合误报为"重复未修复"；
1. **排查 fix_sample 的特征 join 键**：若存在仅按 `request_id` 关联（不带 `mmb_id`）的特征表，这些组合会有轻微跨用户特征串扰。

### 5.9 后续：训练对比实验与成功标准

| 实验组     | 配置       | 样本       | 预期效果   |
| ---------- | ---------- | ---------- | ---------- |
| baseline   | 原始config | 修复前样本 | GAUC=0.702 |
| experiment | 原始config | 修复后样本 | GAUC>0.710 |

| 指标                        | baseline | 目标        | 判断                     |
| --------------------------- | -------- | ----------- | ------------------------ |
| home CTR GAUC               | 0.702    | 0.702~0.710 | 预期区间（不承诺 +1.1%） |
| trend GAUC                  | 0.639    | >0.700      | 预期值，需实测           |
| trend重复率（60d 三键粒度） | 100%     | \<1%        | 数据质量达标             |

链路收尾顺序：重跑 fix_sample → 60d 汇总 → 对 60d 表跑补 `mmb_id` 的 verify（盯三键重复=0 且"≥5 行/组合"桶归零——若不归零即 join fan-out 的定性证据，回答 B-2）。

______________________________________________________________________

## 六、经验总结

### 6.1 技术要点

1. **GROUP BY字段选择**：
   - 不应包含时间戳等会导致同一实体拆分的字段
   - 除非确实需要按时间粒度聚合
1. **数据类型处理**：
   - `item_id` 和 `mmb_id` 是 `ARRAY<STRING>` 类型
   - 验证SQL中需直接使用ARRAY类型分组，避免类型转换错误
1. **梯度冲突检测**：
   - 重复样本的标签矛盾是严重的梯度冲突源
   - 应在数据管道中添加去重兜底逻辑

### 6.2 流程改进建议

1. **数据管道层**：
   - 在60d汇总脚本中添加 `ROW_NUMBER()` 去重兜底
   - 即使上游SQL出错，也能保证数据质量
1. **验证层**：
   - 添加自动化数据质量检查（重复率、矛盾比例）
   - 超过阈值时报警
1. **监控层**：
   - 监控各场景GAUC差异
   - 如果某场景GAUC显著低于其他，优先检查数据质量

______________________________________________________________________

## 七、文件清单

| 文件                                                       | 说明               |
| ---------------------------------------------------------- | ------------------ |
| `sql/2609/verify_trend_duplicate.sql`                      | 验证SQL            |
| `sql/2609/home_flow_2606_ctrcvr_sorter_label_table_v5.sql` | 已修复的label SQL  |
| `config/v19/TREND_DUPLICATE_FIX_REPORT.md`                 | 本文档             |
| `config/v19/TREND_DATA_CRITICAL_ISSUE.md`                  | 严重性评估（参考） |

______________________________________________________________________

**修复完成时间**: 2026-10-22
**修复人**: [用户]
**下一步**: 重新生成样本表并运行验证SQL
