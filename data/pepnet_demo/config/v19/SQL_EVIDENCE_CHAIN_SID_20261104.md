# SQL 取证链追踪（SID 线）：语义ID应用的立项前置取证（20261104 起）

> **目的**：[SID_APPLICATION_PLAN_20261104.md](SID_APPLICATION_PLAN_20261104.md) 的 P0 取证。原链（SQL-1~6，"4 路打分形态值钱"）已收档于 [SQL_EVIDENCE_CHAIN_20261103.md](SQL_EVIDENCE_CHAIN_20261103.md)（其约定"后续新问题另起文档"）；SID 线 SQL 自 **SQL-7** 起在本追踪。
> **纪律**：SQL 一条一条给，基于上一条结果出下一条（2026-11-03 用户确立）；原文 + 原始结果表 + 读数/判定随到随归档于本文档。
> **口径**（沿用原链定谳）：`mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set`，`dt='20261030'`；探针序列 `click_50_seq`；分隔符 `;`；pos0=最新；点击过采样口径，**只解读相对差**。

## 0. 待验假设（机制层）

| 编号    | 假设                                                                                                         | 对应 SQL | 状态                                                                        |
| ------- | ------------------------------------------------------------------------------------------------------------ | -------- | --------------------------------------------------------------------------- |
| H-SID-1 | 长尾问题成立：样本\<50 的 item 在数量上占绝对多数、在样本上占比不可忽略                                      | SQL-7    | **成立**（78.64% item / 11.18% 样本）                                       |
| H-SID-2 | 尾部低 CTR（−3.7pp vs d 桶）归因：缺行为借力（→3B 簇匹配特征优先）vs 商品固有/曝光不足（→3C 簇嵌入借力优先） | SQL-8    | **判定②触发 → 3C 优先、3B 条件化**；机制修正=匹配粒度×活跃度交互（见 §2.3） |
| H-SID-3 | 3_hit_cate3 弱证据带内剂量效应（候选 B eval 覆盖预估推后）                                                   | SQL-9    | **判定①触发：剂量全桶单调，3B=强度形态+尾部阈值≥3**（见 §3.4）              |

## 1. SQL-7：item 活跃度分位普查（✅ 完成 2026-11-04）

### 1.1 SQL 原文（v2）

```sql
-- SQL-7 (v2): item 侧活跃度（样本数）分位普查 —— SID/长尾立项前置
-- v2 修复：ODPS-0130252 笛卡尔积禁令 —— v1 的 CROSS JOIN total（无 join key）被拒，
--   占比改用窗口函数 SUM(...) OVER ()；MAPJOIN hint 方案弃用（纯窗口更干净）
SET odps.sql.type.system.odps2=true;

WITH item_stat AS (
    SELECT
        item_id,
        COUNT(1)           AS samples,
        SUM(is_click)      AS clicks,
        SUM(is_conversion) AS convs
    FROM mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE dt = '20261030'
    GROUP BY item_id
),
bucketed AS (
    SELECT
        CASE
            WHEN samples < 10   THEN 'a_01_lt10'
            WHEN samples < 50   THEN 'b_02_10_50'
            WHEN samples < 200  THEN 'c_03_50_200'
            WHEN samples < 1000 THEN 'd_04_200_1000'
            ELSE                     'e_05_ge1000'
        END AS item_activity_bucket,
        samples,
        clicks
    FROM item_stat
),
agg AS (
    SELECT
        item_activity_bucket,
        COUNT(1)     AS n_items,
        SUM(samples) AS samples,
        SUM(clicks)  AS clicks
    FROM bucketed
    GROUP BY item_activity_bucket
)
SELECT
    item_activity_bucket,
    n_items,
    ROUND(n_items / SUM(n_items) OVER (), 4) AS item_ratio,
    samples,
    ROUND(samples / SUM(samples) OVER (), 4) AS sample_ratio,
    ROUND(clicks / samples, 5)               AS ctr
FROM agg
ORDER BY item_activity_bucket;
```

### 1.2 原始结果（2026-11-04 用户回贴）

| item_activity_bucket | n_items | item_ratio | samples   | sample_ratio | ctr     |
| -------------------- | ------- | ---------- | --------- | ------------ | ------- |
| a_01_lt10            | 30,313  | 0.5775     | 72,676    | 0.0236       | 0.35415 |
| b_02_10_50           | 10,962  | 0.2089     | 271,513   | 0.0882       | 0.36156 |
| c_03_50_200          | 7,786   | 0.1483     | 782,549   | 0.2542       | 0.37995 |
| d_04_200_1000        | 3,052   | 0.0581     | 1,187,757 | 0.3859       | 0.39076 |
| e_05_ge1000          | 373     | 0.0071     | 763,493   | 0.2480       | 0.36398 |

### 1.3 读数与判定

1. **对账【事实读数】**：samples 合计 3,077,988，与 SQL-2 总量**逐位一致** ✓；items 合计 52,486。
1. **H-SID-1 成立【判定，对照预注册两条】**：a+b item_ratio = 78.64%（>20% ✓）、sample_ratio = 11.18%（>10% ✓，压线）→ **长尾问题成立，3C（CGAE-lite）优先级上调**。
1. 头部集中度【事实读数】：d+e 仅 6.52% item 承载 63.39% 样本；a 桶平均 2.4 样本/item，item_id embedding 基本学不动。
1. CTR 梯度【事实读数】：a→d 单调升（0.354→0.391，+3.66pp），e 桶回落（0.364，vs d −2.68pp）。长尾桶 CTR 低与"尾部 embedding 噪声"假设**相容不证明**——标签率混合商品固有质量与模型打分质量，非模型排序读数【推断边界】。
1. 异常记录【事实读数】：e 桶回落（373 个超头部 item CTR 反低）——疑运营坑位/大流量稀释，同 SQL-2 `0_no_seq` 级异常备忘，不过度解读。
1. 稀释面【推断】：3C 受益面（a+b）仅 11.2% 样本 → 效应进整体 AUC 必被稀释，评估必须以**尾部桶为主判据**、整体 AUC 为护栏。

## 2. SQL-8：活跃度 × 匹配层级交叉（尾部低 CTR 机制诊断）——✅ 完成 2026-11-05

```sql
-- SQL-8: item 活跃度 × 序列匹配层级 交叉分桶 × CTR
-- 目的（基于 SQL-7 结果转向）：尾部 a+b 桶 CTR 低 3.7pp——是"缺行为借力"还是"商品固有"？
--   借力代理 = SQL-2 的 click_50_seq 匹配层级；活跃度桶 = SQL-7 同口径（item 样本数）
SET odps.sql.type.system.odps2=true;

WITH item_stat AS (
    SELECT item_id, COUNT(1) AS item_samples
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
    GROUP BY item_id
),
flagged AS (
    SELECT
        CASE
            WHEN s.item_samples < 10   THEN 'a_01_lt10'
            WHEN s.item_samples < 50   THEN 'b_02_10_50'
            WHEN s.item_samples < 200  THEN 'c_03_50_200'
            WHEN s.item_samples < 1000 THEN 'd_04_200_1000'
            ELSE                            'e_05_ge1000'
        END AS item_activity_bucket,
        CASE
            WHEN t.click_50_seq__item_id IS NULL OR t.click_50_seq__item_id = '' THEN '0_no_seq'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__item_id, ';'), t.item_id)  THEN '1_hit_item'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__spu_id,  ';'), t.spu_id)   THEN '2_hit_spu'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__third_cate_id, ';'),
                                CAST(t.third_cate_id AS STRING))                 THEN '3_hit_cate3'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__second_cate_id, ';'),
                                CAST(t.second_cate_id AS STRING))                THEN '4_hit_cate2'
            WHEN ARRAY_CONTAINS(SPLIT(t.click_50_seq__first_cate_id, ';'),
                                CAST(t.first_cate_id AS STRING))                 THEN '5_hit_cate1'
            ELSE '6_no_hit'
        END AS match_bucket,
        t.is_click
    FROM mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set t
    JOIN item_stat s ON t.item_id = s.item_id
    WHERE t.dt = '20261030'
)
SELECT
    item_activity_bucket,
    match_bucket,
    COUNT(1)                           AS samples,
    SUM(is_click)                      AS clicks,
    ROUND(SUM(is_click) / COUNT(1), 5) AS ctr
FROM flagged
GROUP BY item_activity_bucket, match_bucket
HAVING COUNT(1) >= 2000          -- 小格防噪声（a 桶 × 细匹配桶可能很小），阈值可调
ORDER BY item_activity_bucket, match_bucket;
```

### 2.1 预注册判读（结果到手即对照）

| 观察                                                                                    | 判定                                                              |
| --------------------------------------------------------------------------------------- | ----------------------------------------------------------------- |
| ① 尾部桶（a/b）内 match lift（3_hit_cate3 或 2_hit_spu vs 6_no_hit）**≥ 头部桶**（d/e） | 借力面对尾部有效 → **3B（簇匹配特征）优先**                       |
| ② 尾部桶内 match 梯度明显更平                                                           | 低 CTR 主因是商品固有/曝光不足 → **3C（簇嵌入共享统计强度）优先** |
| ③ 尾部 lift 反而更大                                                                    | 3B+3C 双双有据，按工作量 3B 先行                                  |

### 2.2 原始结果（2026-11-05 用户回贴）

| item_activity_bucket | match_bucket | samples | clicks  | ctr     |
| -------------------- | ------------ | ------- | ------- | ------- |
| a_01_lt10            | 0_no_seq     | 3,939   | 1,748   | 0.44377 |
| a_01_lt10            | 1_hit_item   | 3,644   | 2,107   | 0.57821 |
| a_01_lt10            | 2_hit_spu    | 3,763   | 1,740   | 0.46240 |
| a_01_lt10            | 3_hit_cate3  | 37,727  | 12,510  | 0.33159 |
| a_01_lt10            | 4_hit_cate2  | 7,589   | 2,419   | 0.31875 |
| a_01_lt10            | 5_hit_cate1  | 7,618   | 2,410   | 0.31636 |
| a_01_lt10            | 6_no_hit     | 8,396   | 2,804   | 0.33397 |
| b_02_10_50           | 0_no_seq     | 7,213   | 3,156   | 0.43754 |
| b_02_10_50           | 1_hit_item   | 8,570   | 5,026   | 0.58646 |
| b_02_10_50           | 2_hit_spu    | 19,225  | 10,105  | 0.52562 |
| b_02_10_50           | 3_hit_cate3  | 152,890 | 56,524  | 0.36970 |
| b_02_10_50           | 4_hit_cate2  | 31,758  | 9,589   | 0.30194 |
| b_02_10_50           | 5_hit_cate1  | 28,302  | 7,639   | 0.26991 |
| b_02_10_50           | 6_no_hit     | 23,555  | 6,130   | 0.26024 |
| c_03_50_200          | 0_no_seq     | 17,708  | 7,760   | 0.43822 |
| c_03_50_200          | 1_hit_item   | 21,592  | 12,633  | 0.58508 |
| c_03_50_200          | 2_hit_spu    | 67,737  | 37,927  | 0.55992 |
| c_03_50_200          | 3_hit_cate3  | 422,282 | 166,052 | 0.39323 |
| c_03_50_200          | 4_hit_cate2  | 99,599  | 30,753  | 0.30877 |
| c_03_50_200          | 5_hit_cate1  | 87,453  | 24,667  | 0.28206 |
| c_03_50_200          | 6_no_hit     | 66,178  | 17,538  | 0.26501 |
| d_04_200_1000        | 0_no_seq     | 32,060  | 13,886  | 0.43313 |
| d_04_200_1000        | 1_hit_item   | 28,529  | 16,816  | 0.58944 |
| d_04_200_1000        | 2_hit_spu    | 123,999 | 73,881  | 0.59582 |
| d_04_200_1000        | 3_hit_cate3  | 549,573 | 228,388 | 0.41557 |
| d_04_200_1000        | 4_hit_cate2  | 154,706 | 49,245  | 0.31831 |
| d_04_200_1000        | 5_hit_cate1  | 167,434 | 47,690  | 0.28483 |
| d_04_200_1000        | 6_no_hit     | 131,456 | 34,221  | 0.26032 |
| e_05_ge1000          | 0_no_seq     | 39,789  | 15,075  | 0.37887 |
| e_05_ge1000          | 1_hit_item   | 13,016  | 8,095   | 0.62193 |
| e_05_ge1000          | 2_hit_spu    | 49,810  | 31,371  | 0.62981 |
| e_05_ge1000          | 3_hit_cate3  | 262,209 | 115,784 | 0.44157 |
| e_05_ge1000          | 4_hit_cate2  | 83,420  | 27,375  | 0.32816 |
| e_05_ge1000          | 5_hit_cate1  | 133,911 | 37,416  | 0.27941 |
| e_05_ge1000          | 6_no_hit     | 181,338 | 42,777  | 0.23590 |

### 2.3 读数与判定

**对账【事实读数】**：行小计与 SQL-7 桶样本数逐位一致 ✓；列小计与 SQL-2 各 match_bucket 逐位一致（0_no_seq 100,709 / 1_hit_item 75,351 / 2_hit_spu 264,534 等）✓。

**桶内 match lift（vs 6_no_hit，倍数）**：

| 桶            | 1_hit_item ctr | 2_hit_spu ctr | 3_hit_cate3 ctr | 6_no_hit ctr | item lift | spu lift | cate3 lift |
| ------------- | -------------- | ------------- | --------------- | ------------ | --------- | -------- | ---------- |
| a_01_lt10     | 0.578          | 0.462         | 0.332           | 0.334        | 1.73×     | 1.38×    | **0.99×**  |
| b_02_10_50    | 0.586          | 0.526         | 0.370           | 0.260        | 2.25×     | 2.02×    | 1.42×      |
| c_03_50_200   | 0.585          | 0.560         | 0.393           | 0.265        | 2.21×     | 2.11×    | 1.48×      |
| d_04_200_1000 | 0.589          | 0.596         | 0.416           | 0.260        | 2.26×     | 2.29×    | 1.60×      |
| e_05_ge1000   | 0.622          | 0.630         | 0.442           | 0.236        | 2.64×     | 2.67×    | 1.87×      |

读数：

1. **H-SID-2 判定【对照预注册】**：① 不成立（尾部 lift 0.99×~1.73× ≪ 头部 1.87×~2.67×）；③ 不成立；**② 触发 → 3C（簇嵌入借力）优先，3B 降级为条件项**。
1. **机制修正【事实读数 + 推断边界】**：预注册②的归因措辞（"商品固有/曝光不足"）**被读数修正**——尾部不是商品固有差：`1_hit_item` 绝对 CTR 尾部 0.578 ≈ 头部 d 0.589（强证据下尾部追平头部）。真实机制 = **匹配粒度 × 活跃度交互**：尾部只有 item/spu 级强证据才起作用（1.38~1.73×），cate3 级弱证据完全无效（0.99×，且 cate2/cate1 0.319/0.316 反低于 no_hit 0.334——粗品类证据对尾部略负）；头部各级证据全有效（梯度 0.236→0.442→0.630 单调）。
1. 弱证据带占比【事实读数】：尾部 a 桶 72.8% 样本坐在 cate3/2/1 弱证据带（37,727+7,589+7,618）——尾部的低 CTR 集中在"弱证据无效区"；强证据带（item+spu）仅占 10.2%，但一旦命中 CTR 与头部同水平。
1. 设计启示【推断，进 P1/P3 设计输入】：
   - **SID 语义簇粒度红线：必须细于 cate3、对齐 spu 级**——尾部 cate3 级簇≈无效（0.99×），spu 级 1.38× 起跳。量化器码本叶子层的碰撞粒度按此定（直接约束 RQKMeans 簇数/RQVAE 码本大小选择）。
   - **3B（簇匹配特征）条件化**：仅当簇匹配细于 cate3 且带强度（剂量）信息时才可能对尾部有效；二值粗匹配特征价值有限。剂量形态先由 SQL-9 验证。
   - **3C 的价值路径**：不改标签率（商品真实 CTR），而是让模型在弱证据带里靠簇共享统计强度把"尾部强证据命中"（0.578 的可学习面）识别出来——评估主判据=尾部桶 AUC/GAUC。
1. 异常备忘【事实读数】：① a 桶 cate2/cate1 略负（0.319/0.316 < no_hit 0.334）；② `0_no_seq` 全桶高位（0.43~0.44，e 桶 0.379）——无序列用户 CTR 反高，与 SQL-2 异常同源（疑新/未登录人群构成），记档不解读。

## 3. SQL-9：3_hit_cate3 桶内剂量效应 × 活跃度——✅ 完成 2026-11-05

SQL-8 后按候选 A（剂量效应）给本条；候选 B（eval 覆盖预估）推后。

### 3.1 SQL 原文

```sql
-- SQL-9: 3_hit_cate3 桶内"同 cate3 命中剂量" × 活跃度 × CTR
-- 目的（基于 SQL-8 结果）：尾部弱证据带 cate3 lift≈0.99×（无效）、spu 级才起效
--   → 验弱证据带内"强度/剂量"能否救尾部（决定 3B 簇匹配特征形态：二值 vs 计数/强度）
-- 口径沿用 SQL-1/2/7/8；限定纯 3_hit_cate3 样本（排除 item/spu 命中，与 SQL-2 桶定义一致）
SET odps.sql.type.system.odps2=true;

WITH item_stat AS (
    SELECT item_id, COUNT(1) AS item_samples
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
    GROUP BY item_id
),
flagged AS (
    SELECT
        CASE
            WHEN s.item_samples < 10   THEN 'a_01_lt10'
            WHEN s.item_samples < 50   THEN 'b_02_10_50'
            WHEN s.item_samples < 200  THEN 'c_03_50_200'
            WHEN s.item_samples < 1000 THEN 'd_04_200_1000'
            ELSE                            'e_05_ge1000'
        END AS item_activity_bucket,
        SIZE(FILTER(
            SPLIT(REGEXP_REPLACE(t.click_50_seq__third_cate_id, ';+$', ''), ';'),
            x -> x = CAST(t.third_cate_id AS STRING)
        )) AS cate3_hit_cnt,
        t.is_click
    FROM mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set t
    JOIN item_stat s ON t.item_id = s.item_id
    WHERE t.dt = '20261030'
      AND t.click_50_seq__item_id IS NOT NULL
      AND t.click_50_seq__item_id <> ''
      AND NOT ARRAY_CONTAINS(SPLIT(t.click_50_seq__item_id, ';'), t.item_id)
      AND NOT ARRAY_CONTAINS(SPLIT(t.click_50_seq__spu_id,  ';'), t.spu_id)
      AND ARRAY_CONTAINS(SPLIT(t.click_50_seq__third_cate_id, ';'), CAST(t.third_cate_id AS STRING))
)
SELECT
    item_activity_bucket,
    CASE
        WHEN cate3_hit_cnt =  1 THEN 'd1_single'
        WHEN cate3_hit_cnt =  2 THEN 'd2_double'
        WHEN cate3_hit_cnt <=  5 THEN 'd3_3to5'
        WHEN cate3_hit_cnt <= 10 THEN 'd4_6to10'
        ELSE                         'd5_gt10'
    END AS dose_bucket,
    COUNT(1)                           AS samples,
    SUM(is_click)                      AS clicks,
    ROUND(SUM(is_click) / COUNT(1), 5) AS ctr
FROM flagged
GROUP BY item_activity_bucket, CASE
        WHEN cate3_hit_cnt =  1 THEN 'd1_single'
        WHEN cate3_hit_cnt =  2 THEN 'd2_double'
        WHEN cate3_hit_cnt <=  5 THEN 'd3_3to5'
        WHEN cate3_hit_cnt <= 10 THEN 'd4_6to10'
        ELSE                         'd5_gt10'
    END
HAVING COUNT(1) >= 2000          -- 小格防噪声，阈值可调
ORDER BY item_activity_bucket, dose_bucket;
```

> 注：`FILTER(x -> ...)` 需 MaxCompute LAMBDA 支持（odps2 已开）；若引擎拒 lambda，回退 POSEXPLODE 聚合版可另给。

### 3.2 预注册判读（结果到手即对照）

| 观察                                 | 判定                                                                                  |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| ① 尾部桶内 ctr 随 cate3 剂量单调上升 | 弱证据带内强度信息有工作面 → **3B 特征做成计数/强度形态**（非二值），并带尾部专门设计 |
| ② 尾部剂量梯度平（头升尾平也算②）    | 弱证据带救不了尾部 → **3B 降级收档**，主力 = 3C + item/spu 强证据通路                 |

### 3.3 原始结果（2026-11-05 用户回贴）

| item_activity_bucket | dose_bucket | samples | clicks | ctr     |
| -------------------- | ----------- | ------- | ------ | ------- |
| a_01_lt10            | d1_single   | 10,232  | 3,206  | 0.31333 |
| a_01_lt10            | d2_double   | 5,999   | 1,900  | 0.31672 |
| a_01_lt10            | d3_3to5     | 9,336   | 3,141  | 0.33644 |
| a_01_lt10            | d4_6to10    | 6,075   | 2,100  | 0.34568 |
| a_01_lt10            | d5_gt10     | 5,470   | 1,963  | 0.35887 |
| b_02_10_50           | d1_single   | 38,730  | 12,611 | 0.32561 |
| b_02_10_50           | d2_double   | 24,399  | 8,520  | 0.34919 |
| b_02_10_50           | d3_3to5     | 38,990  | 14,319 | 0.36725 |
| b_02_10_50           | d4_6to10    | 25,474  | 10,165 | 0.39903 |
| b_02_10_50           | d5_gt10     | 23,164  | 10,259 | 0.44289 |
| c_03_50_200          | d1_single   | 116,413 | 39,571 | 0.33992 |
| c_03_50_200          | d2_double   | 69,006  | 25,454 | 0.36887 |
| c_03_50_200          | d3_3to5     | 103,649 | 40,814 | 0.39377 |
| c_03_50_200          | d4_6to10    | 63,383  | 27,375 | 0.43190 |
| c_03_50_200          | d5_gt10     | 62,447  | 30,294 | 0.48512 |
| d_04_200_1000        | d1_single   | 157,776 | 56,393 | 0.35742 |
| d_04_200_1000        | d2_double   | 84,806  | 32,874 | 0.38764 |
| d_04_200_1000        | d3_3to5     | 121,208 | 50,481 | 0.41648 |
| d_04_200_1000        | d4_6to10    | 74,751  | 34,303 | 0.45890 |
| d_04_200_1000        | d5_gt10     | 83,919  | 43,533 | 0.51875 |
| e_05_ge1000          | d1_single   | 61,141  | 23,094 | 0.37772 |
| e_05_ge1000          | d2_double   | 28,725  | 11,852 | 0.41260 |
| e_05_ge1000          | d3_3to5     | 38,268  | 17,465 | 0.45639 |
| e_05_ge1000          | d4_6to10    | 24,023  | 11,794 | 0.49095 |
| e_05_ge1000          | d5_gt10     | 30,863  | 17,160 | 0.55601 |

### 3.4 读数与判定

1. **对账警示【事实读数】**：行小计 vs SQL-8 各桶 `3_hit_cate3` 缺口 a 1.6%（615）/ b 1.4%（2,133）/ c 1.7%（7,384）/ d 4.9%（27,113）/ **e 30.2%（79,189）**。推断：SQL-8 CASE 的 NULL fall-through 与 SQL-9 `NOT ARRAY_CONTAINS` 的 NULL 三值语义差异（item_id/spu_id 为 NULL 的行在 SQL-8 可落入 3_hit_cate3、SQL-9 被 WHERE 剔除）；e 桶 30% 缺口提示超头部（疑运营/虚拟品）spu_id 缺失率高。**不影响桶内梯度结论**；如需坐实可给 9b 一行对账查询。
1. 剂量梯度【事实读数】：五桶**全单调升**。d1→d5：a +4.6pp / 1.15×、b +11.7pp / 1.36×、c +14.5pp / 1.43×、d +16.1pp / 1.45×、e +17.8pp / 1.47×。
1. **H-SID-3 判定【对照预注册】**：① 触发（尾部单调升，非平）→ **3B 保留，形态 = 计数/强度（非二值）**；但斜率随活跃度递减（1.15×→1.47×）→ **SQL-8"3C 优先"主线不变**，3B 为辅、带尾部专门设计。
1. **阈值发现【事实读数】**：尾部 d1_single 0.313 **低于** 6_no_hit 0.334（SQL-8）——单条 cate3 命中对尾部是**负**信号；d3（0.336）起才越过 no_hit 基线 → 3B 计数特征对尾部应设 **≥3 阈值/分段**，非线性。
1. 粒度效应延续【事实读数】：高剂量下尾部 d5 0.359 仍远低于头部 d5 0.556（−19.7pp）——SQL-8"尾部需强证据"不被剂量逆转，3C（细粒度簇借力）主线地位不变。
1. 形态设计输入【推断，进 P3B 设计】：3B = 用户侧同簇行为**计数/衰减强度** × 候选簇匹配，分段（0 / 1-2 / 3-5 / 6-10 / >10）+ 尾部阈值交互；簇粒度红线不变（细于 cate3、对齐 spu）。

## 4. 链状态一览

| 环节                             | 状态                    | 结论落点                                                                                                                                                                  |
| -------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SQL-7 活跃度分位普查             | ✅ **完成（20261104）** | H-SID-1 成立：78.64% item / 11.18% 样本（压线）→ 3C 上调；e 桶回落记异常；尾部桶主判据必要性坐实                                                                          |
| SQL-8 活跃度×匹配交叉            | ✅ **完成（20261105）** | ②触发 → 3C 优先、3B 条件化；机制修正=匹配粒度×活跃度交互（尾部 cate3 0.99× 无效、spu 1.38× 起效、item 命中尾部≈头部 0.578 vs 0.589）；SID 簇粒度红线=细于 cate3、对齐 spu |
| SQL-9 剂量效应（3_hit_cate3 内） | ✅ **完成（20261105）** | ①触发（五桶全单调）→ 3B=计数/强度形态+尾部阈值≥3（d1 对尾部为负信号）；斜率 1.15×→1.47× 随活跃度递增 → 3C 主线不变                                                        |

**P0 取证链结论（20261105 收档）**：立项三问全部落定——①长尾成立（78.6% item / 11.2% 样本，SQL-7）；②尾部低 CTR 机制 = 匹配粒度×活跃度交互（强证据尾部追平头部、弱证据无效，SQL-8）→ **3C 优先**；③弱证据带内剂量单调（1.15×~1.47×）且尾部需 ≥3 阈值（SQL-9）→ **3B 保留为强度形态**。执行序：3A config 臂先行 → 3C（CGAE-lite，簇嵌入借力）→ 3B（强度匹配特征，簇粒度红线=细于 cate3 对齐 spu）。可选遗留：9b 对账小查询（spu_id NULL 缺口，不影响结论）；候选 B（eval 覆盖预估）并入 3A 读数设计。

______________________________________________________________________

*创建：2026-11-05（补建；SQL-7 结果 2026-11-04 取得，此前误归档于 SID_APPLICATION_PLAN 附录、未按"另起文档"约定入链追踪——本文档即为补正）。更新记录：①20261105——SQL-7 全文归档（原文 v2 含 ODPS-0130252 修复记录、结果表、读数 6 条、判定）；SQL-8 已给入档（结果随后于②归档）。②20261105——SQL-8 结果归档（§2.2/2.3）：判定②触发（3C 优先）+ 机制修正（粒度×活跃度交互）；SQL-9（剂量版）已给入档（§3）。③20261105——SQL-9 结果归档（§3.3/3.4）：判定①触发（五桶全单调、尾部 1.15×、d1 负信号→阈值≥3）；**P0 链收档**。*
