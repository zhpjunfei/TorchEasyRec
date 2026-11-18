# SQL 取证链追踪：「4 路打分形态值钱」的内在因素（20261103 起）

> **📌 分流提示（20261105）**：SID（语义ID）线的 SQL-7/8/9（长尾普查 / 活跃度×匹配交叉 / 剂量效应）**不在本文档**，已按"后续新问题另起文档"约定归档于 **[SQL_EVIDENCE_CHAIN_SID_20261104.md](SQL_EVIDENCE_CHAIN_SID_20261104.md)**（含全部结果表与读数）。本文档仍是 SQL-1~6（T0-T3 消融取证线）的唯一追踪处，已收档。

> **目的**：T0-T3 消融读数给出两个经验事实——①T2−T0=+0.074pp（DIN 式 4 路打分读出是唯一方向正的因子）；②T0−F1b≈0（target 通路本身不值钱）。本链用训练样本（SQL）从数据分布层找内在因素。
> **纪律**：SQL 一条一条给，基于上一条结果出下一条（2026-11-03 用户明确要求，已入用户级 MEMORY.md）。
> **本文档**：SQL 链唯一落盘追踪处；每条 SQL 的原文、原始结果表、分层读数都在此归档，随链推进滚动更新。

## 0. 待验假设（机制层）

| 编号 | 假设                                                                                | 对应 SQL | 状态                                                                   |
| ---- | ----------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------- |
| H1   | 「target 在序列里、匹配多细」是 CTR 强信号 → DIN 打分要捕捉的东西真实存在           | SQL-2    | **成立**（2.35× 梯度）                                                 |
| H3   | 大量样本是「部分匹配」（cate 命中但 item 未命中）→ `q−s`/`q⊙s` 残差模式有巨大工作面 | SQL-2    | **成立**（72.3% 样本）                                                 |
| H5   | 远端命中仍带 lift → attention「检索」有活干（逐位置打分 > 等权平均）                | SQL-3+4  | **成立且干净**（控长度后远端 +14.0pp/1.38×，与未分层一致）             |
| 混淆 | 命中率/位置 lift 部分是用户活跃度（序列长度）效应                                   | SQL-4    | **已拆解：混淆可忽略**（同带基线随长度微降而非上升，远端 lift 无水分） |
| F-B  | 「target 通路不值钱」是因为下游 `user__kv_*` 统计特征已供给同类信息                 | SQL-6    | **kv 版证伪**（带内梯度不消失 k0 2.92×）；改判"下游网络合成"【推断】   |

## 1. 口径定谳（SQL-1 样本勘察，20261103）

20 行样本勘察 + 列名核对（`item_id`/`spu_id` STRING，`first/second/third_cate_id` BIGINT）：

1. **分隔符 = `;`**（不是逗号/竖线）——`598171730;598942986;…`，后续全部 `SPLIT(x, ';')`，注意尾部 `;` 产生空元素需 `REGEXP_REPLACE(x, ';+$', '')` 清理；
1. **顺序语义 = pos 0 是最新**——`ts` 列是近因秒数差（now − event，5 秒 ~ 15 天量级）逐行递增，序列头部=最近点击；`POSEXPLODE` 的 pos=0 即最近；
1. **序列列**：`click_50_seq__item_id` 等为 STRING 分号拼接；真实长度用 `SIZE(SPLIT(...))`；
1. **口径警示（对全链有效）**：样本是点击过采样/负例欠采样口径（is_click 均值≈0.3667），**绝对 CTR ≈0.3-0.4 不是大盘 CTR**，只解读桶间**相对差**（case-control 抽样下相对量有效，假设抽样与特征无关）。

- 表：`mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set`，`dt='20261030'`
- 命中分析探针序列：`click_50_seq`（与 T0-T3 消融探针同位，可直接对账）

## 2. SQL-2：匹配层级 × CTR（验 H1/H3）

### 2.1 SQL 原文

```sql
-- SQL-2: target 与 click_50_seq 的匹配层级分桶 × CTR
-- 依赖 SQL-1 实测：分隔符=';'，pos0=最新，ts=近因秒数
SET odps.sql.type.system.odps2=true;

WITH base AS (
    SELECT
        mmb_id,
        item_id,
        spu_id,
        CAST(third_cate_id  AS STRING) AS cate3,
        CAST(second_cate_id AS STRING) AS cate2,
        CAST(first_cate_id  AS STRING) AS cate1,
        click_50_seq__item_id    AS seq_item,
        click_50_seq__spu_id     AS seq_spu,
        click_50_seq__third_cate_id  AS seq_cate3,
        click_50_seq__second_cate_id AS seq_cate2,
        click_50_seq__first_cate_id  AS seq_cate1,
        is_click,
        is_conversion
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
),
flagged AS (
    SELECT
        *,
        SIZE(SPLIT(REGEXP_REPLACE(seq_item, ';+$', ''), ';')) AS seq_len,
        CASE
            WHEN seq_item IS NULL OR seq_item = ''              THEN '0_no_seq'
            WHEN ARRAY_CONTAINS(SPLIT(seq_item,  ';'), item_id) THEN '1_hit_item'
            WHEN ARRAY_CONTAINS(SPLIT(seq_spu,   ';'), spu_id)  THEN '2_hit_spu'
            WHEN ARRAY_CONTAINS(SPLIT(seq_cate3, ';'), cate3)   THEN '3_hit_cate3'
            WHEN ARRAY_CONTAINS(SPLIT(seq_cate2, ';'), cate2)   THEN '4_hit_cate2'
            WHEN ARRAY_CONTAINS(SPLIT(seq_cate1, ';'), cate1)   THEN '5_hit_cate1'
            ELSE '6_no_hit'
        END AS match_bucket
    FROM base
)
SELECT
    match_bucket,
    samples,
    ROUND(samples / SUM(samples) OVER (), 4)                        AS sample_ratio,
    clicks,
    ROUND(clicks  / samples, 5)                                     AS ctr,
    ROUND(convs   / NULLIF(clicks, 0), 5)                           AS cvr_given_click,
    avg_seq_len
FROM (
    SELECT
        match_bucket,
        COUNT(1)              AS samples,
        SUM(is_click)         AS clicks,
        SUM(is_conversion)    AS convs,
        ROUND(AVG(seq_len), 1) AS avg_seq_len
    FROM flagged
    GROUP BY match_bucket
) t
ORDER BY match_bucket;
```

### 2.2 原始结果（20261103 用户回贴）

| match_bucket | samples   | sample_ratio | clicks  | ctr     | cvr_given_click | avg_seq_len |
| ------------ | --------- | ------------ | ------- | ------- | --------------- | ----------- |
| 0_no_seq     | 100,709   | 0.0327       | 41,625  | 0.41332 | 0.44615         | 0.0         |
| 1_hit_item   | 75,351    | 0.0245       | 44,677  | 0.59292 | 0.47022         | 39.3        |
| 2_hit_spu    | 264,534   | 0.0859       | 155,024 | 0.58603 | 0.41363         | 37.3        |
| 3_hit_cate3  | 1,424,681 | 0.4629       | 579,258 | 0.40659 | 0.37060         | 39.3        |
| 4_hit_cate2  | 377,072   | 0.1225       | 119,381 | 0.31660 | 0.31360         | 42.0        |
| 5_hit_cate1  | 424,718   | 0.1380       | 119,822 | 0.28212 | 0.31276         | 39.1        |
| 6_no_hit     | 410,923   | 0.1335       | 103,470 | 0.25180 | 0.33609         | 27.1        |

### 2.3 读数

1. **H1 成立【事实读数】**：CTR 梯度单调陡，hit_item 0.593 → no_hit 0.252，**2.35× lift**——「target 在不在序列里、匹配多细」是 CTR 强信号。
1. **H3 成立【事实读数】**：部分匹配三桶（cate3/cate2/cate1）合计 **72.3%**（46.3%+12.3%+13.8%），精确命中（item/spu）只占 11%；部分匹配内部梯度依然陡（0.407→0.317→0.282）。**绝大多数样本坐在「同品类、不同商品」区域**——恰是 4 路打分 `q−s`（残差视图）/`q⊙s`（共现视图）与单点积拉开差距的地方。【推断：T2−T0=+0.074pp 与该分布形状吻合】
1. **异常记录【事实读数】**：`0_no_seq`（3.27%）CTR 0.413 > `6_no_hit` 0.252——有序列但全不命中的用户最冷；两桶合计 16.6% 是「打分形态无关区」。
1. **混淆警示【事实读数】**：`6_no_hit` avg_seq_len 仅 27.1 vs 命中桶 37~42——命中率部分是活跃度效应（点得多→序列长→易碰巧命中）。（⚠ 此条的"活跃度→CTR 正向"方向预判后被 SQL-4 证伪，见 §4.3 ③。）

## 3. SQL-3：item 级命中位置 × CTR（验 H5：检索 vs 近因）

### 3.1 SQL 原文

```sql
-- SQL-3: click_50_seq 中 item 级命中位置远近 × CTR（pos0=最新，依赖 SQL-1/2 定谳）
-- 每行取"最近一次命中"位置 hit_pos_min 分桶；无命中/空序列作参照桶
SET odps.sql.type.system.odps2=true;

WITH base AS (
    SELECT
        mmb_id,
        item_id,
        click_50_seq__item_id AS seq_item,
        is_click,
        is_conversion
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
),
exploded AS (
    SELECT  mmb_id, item_id, seq_item, is_click, is_conversion, pos, elem
    FROM    base
    LATERAL VIEW POSEXPLODE(
        SPLIT(REGEXP_REPLACE(COALESCE(seq_item, ''), ';+$', ''), ';')
    ) t AS pos, elem
),
row_hits AS (
    -- 唯一键=(mmb_id, item_id, seq_item, labels)；完全相同的重复行会合并，量级可忽略
    SELECT
        mmb_id, item_id, seq_item, is_click, is_conversion,
        MIN(CASE WHEN elem = item_id THEN pos END)      AS hit_pos_min,
        SUM(CASE WHEN elem = item_id THEN 1 ELSE 0 END) AS hit_cnt,
        CASE WHEN REGEXP_REPLACE(COALESCE(seq_item, ''), ';+$', '') = ''
             THEN 0 ELSE MAX(pos) + 1 END               AS seq_len
    FROM   exploded
    GROUP BY mmb_id, item_id, seq_item, is_click, is_conversion
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN seq_len = 0         THEN '0_no_seq'
            WHEN hit_pos_min IS NULL THEN '6_no_item_hit'
            WHEN hit_pos_min <= 4    THEN '1_hit_pos_0_4'
            WHEN hit_pos_min <= 9    THEN '2_hit_pos_5_9'
            WHEN hit_pos_min <= 19   THEN '3_hit_pos_10_19'
            ELSE                          '4_hit_pos_20_plus'
        END AS pos_bucket
    FROM row_hits
)
SELECT
    pos_bucket,
    samples,
    ROUND(samples / SUM(samples) OVER (), 4)        AS sample_ratio,
    clicks,
    ROUND(clicks / samples, 5)                      AS ctr,
    ROUND(convs / NULLIF(clicks, 0), 5)             AS cvr_given_click,
    avg_seq_len,
    avg_hit_cnt
FROM (
    SELECT
        pos_bucket,
        COUNT(1)                            AS samples,
        SUM(is_click)                       AS clicks,
        SUM(is_conversion)                  AS convs,
        ROUND(AVG(seq_len), 1)              AS avg_seq_len,
        ROUND(AVG(COALESCE(hit_cnt, 0)), 2) AS avg_hit_cnt
    FROM flagged
    GROUP BY pos_bucket
) t
ORDER BY pos_bucket;
```

### 3.2 原始结果（20261103 用户回贴）

| pos_bucket        | samples   | sample_ratio | clicks    | ctr     | cvr_given_click | avg_seq_len | avg_hit_cnt |
| ----------------- | --------- | ------------ | --------- | ------- | --------------- | ----------- | ----------- |
| 1_hit_pos_0_4     | 22,909    | 0.0077       | 16,218    | 0.70793 | 0.55685         | 25.4        | 1.0         |
| 2_hit_pos_5_9     | 12,496    | 0.0042       | 7,460     | 0.59699 | 0.47788         | 38.1        | 1.0         |
| 3_hit_pos_10_19   | 16,102    | 0.0054       | 8,898     | 0.55260 | 0.43403         | 45.2        | 1.0         |
| 4_hit_pos_20_plus | 23,844    | 0.0080       | 12,101    | 0.50751 | 0.37600         | 49.3        | 1.0         |
| 6_no_item_hit     | 2,901,928 | 0.9747       | 1,076,955 | 0.37112 | 0.36072         | 37.7        | 0.0         |

（`0_no_seq` 空序列 100,709 行在 POSEXPLODE 中产生零行被丢，不影响位置分析；表内分母为剔除后的 2.98M。）

### 3.3 读数

1. **对账通过【事实读数】**：命中桶合计 75,351 样本 / 44,677 clicks 与 SQL-2 `1_hit_item` 逐位一致。
1. **H5 成立但含混淆【事实读数】**：ctr 单调衰减 0.708 → 0.597 → 0.553 → 0.508，但 **pos 20+ 仍比 `6_no_item_hit`(0.371) 高 +13.6pp（1.37×）**——不是纯「刚点过的再触达」，远端检索有真实价值（与 T2 唯一正向、F1b mean pooling 最差同向）【推断】。
1. **长度混淆存在且方向明确【事实读数】**：avg_seq_len 25.4→49.3 随位置递增。（⚠ 此处"活跃度混淆在推高远端桶 CTR、真实近因效应可能更陡"的推断后被 SQL-4 证伪，见 §4.3 ③。）
1. **无剂量混淆【事实读数】**：avg_hit_cnt 全 = 1.0（item 命中几乎都唯一一次）。
1. **副发现【事实读数】**：cvr|click 衰减远比 ctr 陡（0.557→0.376 ≈ 混合基线 0.361）——远端命中对「会不会点」有预测力、对「点后会不会买」在混合口径下几乎归零。（⚠ 同带口径下修正为 +4.1pp，见 §4.3 副发现。）

## 4. SQL-4：seq_len 分层 × 命中位置（拆活跃度混淆）——✅ 完成

### 4.1 SQL 原文（已给，20261103）

```sql
-- SQL-4: seq_len 分层 × item 命中位置 → CTR（拆"活跃度/长度"混淆）
-- 依赖 SQL-3：位置桶定义不变；新增 seq_len 分带；同带内比位置、并带 x_no_hit 同层基线
SET odps.sql.type.system.odps2=true;

WITH base AS (
    SELECT
        mmb_id,
        item_id,
        click_50_seq__item_id AS seq_item,
        is_click,
        is_conversion
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
),
exploded AS (
    SELECT  mmb_id, item_id, seq_item, is_click, is_conversion, pos, elem
    FROM    base
    LATERAL VIEW POSEXPLODE(
        SPLIT(REGEXP_REPLACE(COALESCE(seq_item, ''), ';+$', ''), ';')
    ) t AS pos, elem
),
row_hits AS (
    SELECT
        mmb_id, item_id, seq_item, is_click, is_conversion,
        MIN(CASE WHEN elem = item_id THEN pos END) AS hit_pos_min,
        CASE WHEN REGEXP_REPLACE(COALESCE(seq_item, ''), ';+$', '') = ''
             THEN 0 ELSE MAX(pos) + 1 END         AS seq_len
    FROM   exploded
    GROUP BY mmb_id, item_id, seq_item, is_click, is_conversion
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN seq_len >= 41 THEN 'E_41_50'
            WHEN seq_len >= 31 THEN 'D_31_40'
            WHEN seq_len >= 21 THEN 'C_21_30'
            WHEN seq_len >= 11 THEN 'B_11_20'
            WHEN seq_len >= 1  THEN 'A_1_10'
            ELSE                    'Z_empty'
        END AS len_band,
        CASE
            WHEN hit_pos_min IS NULL THEN 'x_no_hit'
            WHEN hit_pos_min <= 4    THEN 'p0_0_4'
            WHEN hit_pos_min <= 9    THEN 'p1_5_9'
            WHEN hit_pos_min <= 19   THEN 'p2_10_19'
            ELSE                          'p3_20_plus'
        END AS pos_bucket
    FROM row_hits
    WHERE seq_len > 0
)
SELECT
    len_band,
    pos_bucket,
    samples,
    ROUND(samples / SUM(samples) OVER (PARTITION BY len_band), 4) AS ratio_in_band,
    clicks,
    ROUND(clicks / samples, 5)                                     AS ctr,
    ROUND(convs / NULLIF(clicks, 0), 5)                            AS cvr_given_click
FROM (
    SELECT
        len_band,
        pos_bucket,
        COUNT(1)           AS samples,
        SUM(is_click)      AS clicks,
        SUM(is_conversion) AS convs
    FROM flagged
    GROUP BY len_band, pos_bucket
) t
ORDER BY len_band, pos_bucket;
```

### 4.2 原始结果（20261103 用户回贴）

| len_band | pos_bucket | samples   | ratio_in_band | clicks  | ctr     | cvr_given_click |
| -------- | ---------- | --------- | ------------- | ------- | ------- | --------------- |
| A_1_10   | p0_0_4     | 7,233     | 0.0173        | 5,191   | 0.71768 | 0.57503         |
| A_1_10   | p1_5_9     | 669       | 0.0016        | 407     | 0.60837 | 0.46192         |
| A_1_10   | x_no_hit   | 411,135   | 0.9811        | 157,680 | 0.38352 | 0.43051         |
| B_11_20  | p0_0_4     | 4,218     | 0.0162        | 2,927   | 0.69393 | 0.56372         |
| B_11_20  | p1_5_9     | 1,730     | 0.0067        | 985     | 0.56936 | 0.48731         |
| B_11_20  | p2_10_19   | 690       | 0.0027        | 362     | 0.52464 | 0.44475         |
| B_11_20  | x_no_hit   | 253,301   | 0.9745        | 95,134  | 0.37558 | 0.40730         |
| C_21_30  | p0_0_4     | 2,490     | 0.0120        | 1,698   | 0.68193 | 0.57008         |
| C_21_30  | p1_5_9     | 1,533     | 0.0074        | 879     | 0.57339 | 0.50512         |
| C_21_30  | p2_10_19   | 1,223     | 0.0059        | 616     | 0.50368 | 0.45292         |
| C_21_30  | p3_20_plus | 251       | 0.0012        | 114     | 0.45418 | 0.51754         |
| C_21_30  | x_no_hit   | 202,072   | 0.9735        | 75,187  | 0.37208 | 0.39104         |
| D_31_40  | p0_0_4     | 1,727     | 0.0095        | 1,228   | 0.71106 | 0.53420         |
| D_31_40  | p1_5_9     | 1,230     | 0.0068        | 723     | 0.58780 | 0.50484         |
| D_31_40  | p2_10_19   | 1,332     | 0.0073        | 701     | 0.52628 | 0.45792         |
| D_31_40  | p3_20_plus | 568       | 0.0031        | 288     | 0.50704 | 0.37847         |
| D_31_40  | x_no_hit   | 176,643   | 0.9732        | 65,326  | 0.36982 | 0.37870         |
| E_41_50  | p0_0_4     | 7,241     | 0.0038        | 5,174   | 0.71454 | 0.53576         |
| E_41_50  | p1_5_9     | 7,334     | 0.0038        | 4,466   | 0.60894 | 0.46753         |
| E_41_50  | p2_10_19   | 12,857    | 0.0067        | 7,219   | 0.56148 | 0.42956         |
| E_41_50  | p3_20_plus | 23,025    | 0.0121        | 11,699  | 0.50810 | 0.37456         |
| E_41_50  | x_no_hit   | 1,858,777 | 0.9736        | 683,628 | 0.36778 | 0.33309         |

### 4.3 读数（按 §4.3 原判读标准四点逐一）

**〇、对账【事实读数】**：按带拆分后与 SQL-3 逐位吻合——p0 7,233+4,218+2,490+1,727+7,241=**22,909** ✓；p1 合计 **12,496** ✓；p2 合计 **16,102** ✓；p3 251+568+23,025=**23,844** ✓；x_no_hit 合计 **2,901,928** ✓。两表同源一致，读数可信。

**① 带内梯度（核心）【事实读数】：全部带内单调，斜率与未分层几乎相同 → 近因衰减是真实位置效应，不是长度构成效应。**

| 带      | p0    | p1    | p2    | p3      | p0→p3 落差         |
| ------- | ----- | ----- | ----- | ------- | ------------------ |
| E_41_50 | 0.715 | 0.609 | 0.561 | 0.508   | **−20.6pp**        |
| D_31_40 | 0.711 | 0.588 | 0.526 | 0.507   | **−20.4pp**        |
| C_21_30 | 0.682 | 0.573 | 0.504 | (0.454) | −22.8pp（p3 稀疏） |
| B_11_20 | 0.694 | 0.569 | 0.525 | —       | −16.9pp（至 p2）   |
| A_1_10  | 0.718 | 0.608 | —     | —       | −10.9pp（至 p1）   |

SQL-3 未分层落差 −20.0pp（0.708→0.508），与 E/D 带内 −20.6/−20.4pp 吻合。**「近因主导」定稿为真实效应**（若主要是长度构成效应，带内梯度会大幅塌缩——没有）。

**② p3_20_plus vs 同带 x_no_hit（干净检索价值）【事实读数】：+13.7~14.0pp / 1.37~1.38×，与未分层 +13.6pp/1.37× 几乎一致 → SQL-3 的远端 lift 不含活跃度水分。**

| 带      | p3 ctr | 同带 x_no_hit | 差值        | 倍数                      |
| ------- | ------ | ------------- | ----------- | ------------------------- |
| E_41_50 | 0.5081 | 0.3678        | **+14.0pp** | 1.38×                     |
| D_31_40 | 0.5070 | 0.3698        | **+13.7pp** | 1.37×                     |
| C_21_30 | 0.4542 | 0.3721        | +8.2pp      | 1.22×（n=251 稀疏，忽略） |

固定活跃度后远端命中仍带 ~37% 相对 lift——**「检索价值」的干净估计 ≈ +14pp**。H5 定稿：attention 在长序列里捞远端命中有真实、无水分的价值；逐位置打分（DIN/T2）相对等权平均（F1b）的用武之地坐实。

**③ x_no_hit 随带变化【事实读数】：基线随长度微降（0.384→0.368，−1.6pp），不是上升——此前"活跃度混淆在推高远端桶 CTR"的方向预判证伪。**

A→E：0.38352 → 0.37558 → 0.37208 → 0.36982 → 0.36778。在点击过采样口径下，长序列（重度点击）用户的基线 CTR 反而略低。由此：

- SQL-3 的 −20pp 近因衰减**不需要上修**（混淆≈0，甚至方向相反、若校正衰减略更缓）；
- 远端 +13.6pp lift **不需要下修**（同带 +13.7~14.0pp 证实）；
- 「命中率部分是活跃度效应」（SQL-2 ④）仍然成立（长序列更易碰巧命中），但活跃度**不带正向 CTR 基线**，只是命中概率的混淆，不污染位置梯度。

**④ 样本量【事实读数】**：A/B 带结构性缺失 p2/p3（长度不够，符合预期）；C 带 p3 仅 251 行稀疏忽略；**D/E 带是干净对照**（设计预期内）。E 带承载 p3 的 96.6%（23,025/23,844），E 带单带结论已足够代表远端命中。

**副发现（修正 SQL-3 ⑤ 的混合口径读数）【事实读数】**：

- **p0 跨带极稳（0.68~0.72）**：近位命中强度与活跃度无关；
- **同带内 cvr|click 梯度仍陡于 ctr，但远端不再"归零"**：E 带 0.536→0.375，p3 对同带基线 0.333 仍有 **+4.1pp** lift（混合口径下读到的 +1.5pp 是构成效应压低的假象）。【推断】近因确实携带更强购买意图（p0 cvr 0.54~0.58），但远端命中对 CVR 并非零信息；
- **长序列用户 cvr|click 基线陡降**：x_no_hit 的 cvr 0.431(A)→0.333(E)，−9.7pp——重度点击者点后转化率低，与「远端命中=品类兴趣残留」画像一致。

**对链结论的影响**：H1/H3（SQL-2）+ H5 干净版（SQL-4）共同支撑「4 路打分形态值钱」的数据面（匹配梯度 2.35×、残差工作面 72.3%、检索价值 +14pp）；近因真实且被 ts 桶部分编码 → 与 T1−T0≈0 相容。剩余缺口=F-B（kv 是否已供给匹配信息）→ SQL-6 验。

## 5. SQL-5（下一步，已给）：kv 列格式勘察 → SQL-6 控 kv 验 F-B

### 5.1 背景（从 config 核实的 kv 特征事实）

- v6f_kv_fusion 的 285 个 `user__kv_*` 全是 `lookup_feature`：`map: "user:user__kv_<实体>_<行为>_<窗口>"`，`key: "item:<实体>"`——即**用户对 target 同属性实体的历史行为量**（如 `user__kv_third_cate_id_click_15d` = 用户对 target 所在三级类目的 15d 点击量），恰是「target 通路不值钱（下游已供给）」假说里 F-B 的主角；
- 关键列（F-B 检验用）：`user__kv_item_id_click_15d`（用户对 target 商品的历史点击）、`user__kv_third_cate_id_click_15d`（用户对 target 三级类目的历史点击）；另有标量列 `user__cnt_click_15d`/`item__cnt_click_15d`（活跃度控制用）；
- **格式未知**：kv 列在训练表里是 STRING 序列化还是原生 MAP、键值分隔符是什么，文档（sample-v3-pipeline.md）没写——SQL-1 的教训（预设分隔符不中）要求先勘察再解析。

### 5.2 SQL-5 原文（kv 列格式勘察，同 SQL-1 角色）

```sql
-- SQL-5: user__kv_* 列在训练表中的存储格式勘察（为 SQL-6 控 kv 的 F-B 检验做解析准备）
-- 依赖 SQL-1 教训：分隔符/格式必须实测，不预设
SET odps.sql.type.system.odps2=true;

SELECT
    mmb_id,
    item_id,
    third_cate_id,
    -- 目标侧参照：key 应该就是这些值
    user__kv_item_id_click_15d,        -- 用户对 target 商品的 15d 历史点击（kv）
    user__kv_third_cate_id_click_15d,  -- 用户对 target 三级类目的 15d 历史点击（kv）
    user__cnt_click_15d,               -- 用户总点击（标量，活跃度控制）
    item__cnt_click_15d                -- 商品被点击量（标量）
FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE  dt = '20261030'
LIMIT 20;
```

（若个别列名不存在，报错信息即是清单校正——SQL-6 前按实际列名调整。）

### 5.3 SQL-5 读数（20261104 用户回贴 20 行，三点定谳）

**① kv 列格式 = 原生 `MAP<STRING,FLOAT>`【事实读数，20261104 修正】**：客户端把 MAP 渲染成 `{"<id>":<float>}` 形态，首判"JSON 串"被 SQL-6 执行报错证伪——`GET_JSON_OBJECT` 报 `cannot match any overloaded functions with (MAP<STRING,FLOAT>, STRING)`，类型是原生 MAP（key=STRING，value=FLOAT）。→ 解析用 **MAP 下标** `col[CAST(id AS STRING)]`；缺键/整列 `\N`（NULL map）→ NULL → COALESCE 归 0。（教训：列类型以执行报错/DESC 为准，客户端渲染不可作定谳依据。）

**② key 形态 = 实体 id 原值字符串【事实读数】**：`user__kv_item_id_click_15d` 的键如 `"596499415"` 与行内 `item_id` 逐字一致；`user__kv_third_cate_id_click_15d` 的键如 `"1825"` 与行内 `third_cate_id`（BIGINT 1825）一致 → 取值需 `CAST(third_cate_id AS STRING)` 对齐。样例里 3/20 行的 item kv 含 target 自身键（值 1.0/2.0）——与 `1_hit_item` 部分重叠但窗口不同（15d vs 50 条），非同一信号；cate kv 含 `"1825"` 的行值 1~9。

**③ 标量列都在且量级合理【事实读数】**：`user__cnt_click_15d` = 9~369（含 1 行 `\N`）；`item__cnt_click_15d` = 1059 常数（同 target item，行间不变）。

### 5.4 SQL-6 原文（F-B 正式检验，已给 20261104）

```sql
-- SQL-6: F-B 检验 —— match_bucket × kv_cate3 档位
-- 控住"用户对 target 三级类目的 15d 历史点击"（user__kv_third_cate_id_click_15d[target_cate3]）后，
-- seq 匹配梯度还剩多少？→ 判 kv 是否已供给匹配信息（F-B）
-- 依赖 SQL-5 定谳（20261104 修正）：kv 列=原生 MAP<STRING,FLOAT>，下标取值，key=实体 id 原值字符串；缺键/NULL→0
SET odps.sql.type.system.odps2=true;

WITH base AS (
    SELECT
        mmb_id,
        item_id,
        spu_id,
        CAST(third_cate_id AS STRING) AS cate3,
        CAST(second_cate_id AS STRING) AS cate2,
        CAST(first_cate_id AS STRING) AS cate1,
        click_50_seq__item_id    AS seq_item,
        click_50_seq__spu_id     AS seq_spu,
        click_50_seq__third_cate_id  AS seq_cate3,
        click_50_seq__second_cate_id AS seq_cate2,
        click_50_seq__first_cate_id  AS seq_cate1,
        is_click,
        is_conversion,
        COALESCE(user__kv_third_cate_id_click_15d[CAST(third_cate_id AS STRING)], 0) AS kv_cate3,
        COALESCE(user__kv_item_id_click_15d[item_id], 0)                             AS kv_item,
        COALESCE(user__cnt_click_15d, 0) AS user_clk15d
    FROM   mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
    WHERE  dt = '20261030'
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN seq_item IS NULL OR seq_item = ''              THEN '0_no_seq'
            WHEN ARRAY_CONTAINS(SPLIT(seq_item,  ';'), item_id) THEN '1_hit_item'
            WHEN ARRAY_CONTAINS(SPLIT(seq_spu,   ';'), spu_id)  THEN '2_hit_spu'
            WHEN ARRAY_CONTAINS(SPLIT(seq_cate3, ';'), cate3)
              OR ARRAY_CONTAINS(SPLIT(seq_cate2, ';'), cate2)
              OR ARRAY_CONTAINS(SPLIT(seq_cate1, ';'), cate1)   THEN '3_hit_cate'
            ELSE '6_no_hit'
        END AS match_bucket,
        CASE
            WHEN kv_cate3 = 0   THEN 'k0_zero'
            WHEN kv_cate3 <= 1  THEN 'k1_0_1'
            WHEN kv_cate3 <= 5  THEN 'k2_1_5'
            WHEN kv_cate3 <= 20 THEN 'k3_5_20'
            ELSE                     'k4_20_plus'
        END AS kv_band
    FROM base
)
SELECT
    kv_band,
    match_bucket,
    samples,
    ROUND(samples / SUM(samples) OVER (PARTITION BY kv_band), 4) AS ratio_in_band,
    clicks,
    ROUND(clicks / samples, 5)                                    AS ctr,
    ROUND(convs / NULLIF(clicks, 0), 5)                           AS cvr_given_click,
    ROUND(kv_item_pos_rate, 4)                                    AS kv_item_pos_rate,
    avg_user_clk15d
FROM (
    SELECT
        kv_band,
        match_bucket,
        COUNT(1)                                       AS samples,
        SUM(is_click)                                  AS clicks,
        SUM(is_conversion)                             AS convs,
        AVG(CASE WHEN kv_item > 0 THEN 1.0 ELSE 0 END) AS kv_item_pos_rate,
        ROUND(AVG(user_clk15d), 1)                     AS avg_user_clk15d
    FROM flagged
    GROUP BY kv_band, match_bucket
) t
ORDER BY kv_band, match_bucket;
```

（match 桶在 SQL-2 六桶基础上把 cate3/cate2/cate1 合并为 `3_hit_cate`，交叉表 5×4=20 格可控；`kv_item_pos_rate`/`avg_user_clk15d` 是诊断列。）

### 5.5 SQL-6 判读标准（结果到手看四点）

1. **k0_zero 带内 match 梯度（核心）**：kv 对 target 类目零历史时，`1_hit_item / 2_hit_spu / 3_hit_cate` vs `6_no_hit` 的梯度还剩多少？仍接近 SQL-2 的 2.35× → **F-B 证伪**（匹配携带 kv 外信息，T0≈F1b 需另找解释）；塌平 → F-B 成立方向；
1. **梯度随 kv 档位的收敛速度**：k4_20_plus 带内梯度若消失、k0 陡 → kv 与 seq 匹配信息**部分冗余**（F-B 部分成立）——量化"已供给"程度；
1. **`6_no_hit` 行沿 kv 档位走势**：seq 完全不命中时 kv 自身的 lift（kv 供给偏好信号的直接测量，F-B 前提是否成立）；
1. **诊断列**：`kv_item_pos_rate`（与 hit_item 共线度）、`avg_user_clk15d`（各带活跃度是否均衡——SQL-4 教训：混淆要看方向）。

### 5.6 SQL-6 原始结果（20261104 用户回贴）

| kv_band    | match_bucket | samples | ratio_in_band | clicks  | ctr     | cvr_given_click | kv_item_pos_rate | avg_user_clk15d |
| ---------- | ------------ | ------- | ------------- | ------- | ------- | --------------- | ---------------- | --------------- |
| k0_zero    | 0_no_seq     | 100,709 | 0.0762        | 41,625  | 0.41332 | 0.44615         | 0.0              | 0.0             |
| k0_zero    | 1_hit_item   | 2,107   | 0.0016        | 1,546   | 0.73374 | 0.45602         | 0.0437           | 212.1           |
| k0_zero    | 2_hit_spu    | 11,131  | 0.0084        | 6,129   | 0.55062 | 0.46109         | 0.0              | 71.2            |
| k0_zero    | 3_hit_cate   | 831,735 | 0.6293        | 264,760 | 0.31832 | 0.33182         | 0.0001           | 110.6           |
| k0_zero    | 6_no_hit     | 376,077 | 0.2845        | 94,461  | 0.25117 | 0.33805         | 0.0              | 67.7            |
| k1_0_1     | 1_hit_item   | 7,753   | 0.0263        | 3,358   | 0.43312 | 0.42436         | 0.7143           | 73.9            |
| k1_0_1     | 2_hit_spu    | 27,501  | 0.0932        | 11,923  | 0.43355 | 0.38514         | 0.0001           | 49.1            |
| k1_0_1     | 3_hit_cate   | 247,872 | 0.8403        | 83,017  | 0.33492 | 0.36413         | 0.0008           | 76.2            |
| k1_0_1     | 6_no_hit     | 11,868  | 0.0402        | 2,834   | 0.23879 | 0.30452         | 0.0051           | 177.2           |
| k2_1_5     | 1_hit_item   | 18,588  | 0.0332        | 9,923   | 0.53384 | 0.47949         | 0.7264           | 97.7            |
| k2_1_5     | 2_hit_spu    | 63,870  | 0.1140        | 33,033  | 0.51719 | 0.43236         | 0.0005           | 67.3            |
| k2_1_5     | 3_hit_cate   | 462,218 | 0.8248        | 172,266 | 0.37269 | 0.37476         | 0.0021           | 124.4           |
| k2_1_5     | 6_no_hit     | 15,735  | 0.0281        | 4,087   | 0.25974 | 0.32420         | 0.0102           | 268.2           |
| k3_5_20    | 1_hit_item   | 25,014  | 0.0459        | 15,310  | 0.61206 | 0.48400         | 0.7194           | 113.6           |
| k3_5_20    | 2_hit_spu    | 85,294  | 0.1566        | 51,851  | 0.60791 | 0.43642         | 0.0013           | 88.0            |
| k3_5_20    | 3_hit_cate   | 428,083 | 0.7858        | 177,180 | 0.41389 | 0.37900         | 0.0041           | 171.1           |
| k3_5_20    | 6_no_hit     | 6,374   | 0.0117        | 1,806   | 0.28334 | 0.32558         | 0.0138           | 377.9           |
| k4_20_plus | 1_hit_item   | 21,889  | 0.0615        | 14,540  | 0.66426 | 0.46149         | 0.6653           | 172.3           |
| k4_20_plus | 2_hit_spu    | 76,738  | 0.2155        | 52,088  | 0.67878 | 0.38001         | 0.0031           | 163.2           |
| k4_20_plus | 3_hit_cate   | 256,563 | 0.7206        | 121,238 | 0.47255 | 0.32823         | 0.0074           | 261.8           |
| k4_20_plus | 6_no_hit     | 869     | 0.0024        | 282     | 0.32451 | 0.23404         | 0.0299           | 554.0           |

### 5.7 SQL-6 读数与 F-B 判决

**〇、对账【事实读数】**：五带合计 3,077,988 与 SQL-2 总行数一致；`1_hit_item` 跨带 2,107+7,753+18,588+25,014+21,889=**75,351** ✓、`2_hit_spu` **264,534** ✓、`3_hit_cate` **2,226,471**（=SQL-2 的 cate3+cate2+cate1 三桶和）✓、`6_no_hit` **410,923** ✓、`0_no_seq` 100,709 全部落在 k0（冷用户无 kv）✓。三表同源一致。

**① k0 带内梯度（核心）【事实读数】：kv 零历史区 match 梯度不消失，item 命中比未分层还陡。**

| k0_zero 内 | ctr   | vs 6_no_hit(0.251) | 倍数      |
| ---------- | ----- | ------------------ | --------- |
| 1_hit_item | 0.734 | **+48.3pp**        | **2.92×** |
| 2_hit_spu  | 0.551 | +29.9pp            | 2.19×     |
| 3_hit_cate | 0.318 | +6.7pp             | 1.27×     |

SQL-2 未分层 hit_item/no_hit=2.35×，k0 带内 2.92×——**控制 kv 后 match 梯度不降反升**。kv 完全没有供给"target 在不在序列里"的信息。

**② 梯度随 kv 档位的收敛【事实读数】：不收敛，全档位梯度持续存在。**

| kv 带      | hit_item vs no_hit | hit_cate vs no_hit |
| ---------- | ------------------ | ------------------ |
| k0_zero    | 2.92×              | 1.27×              |
| k1_0_1     | 1.81×              | 1.40×              |
| k2_1_5     | 2.05×              | 1.44×              |
| k3_5_20    | 2.16×              | 1.46×              |
| k4_20_plus | 2.05×              | 1.46×              |

kv 拉满（k4，对 target 类目 15d 点击 20+ 次）的带内 item 命中仍有 **2.05×**——**kv 与 seq 匹配信息不是替代关系**（部分冗余存在：k0 的 cate 命中 lift 1.27× 较未分层 1.62× 收窄，说明 cate 级粗匹配与 kv 有重叠，但 item/spu 级精细匹配独立于 kv）。

**③ `6_no_hit` 行沿 kv 走势【事实读数】：kv 自身有偏好 lift，但远小于 match 梯度。**

0.251 → 0.239 → 0.260 → 0.283 → 0.325（k0→k4 约 1.29×）——**F-B 的前提部分成立**（kv 确实供给"用户喜欢这个类目"的信号），但量级（+7~9pp）远小于带内 match 梯度（+19~48pp）。

**④ 诊断列【事实读数】**：

- `kv_item_pos_rate`：item 命中行约 0.67~0.73（k0 仅 0.044）——seq 命中与 kv item 统计**部分重叠但远非共线**（~30% 的 item 命中不在 15d kv 里：50 条序列可覆盖 15d 之外/更近的点击）；k0 的 hit_item 行 avg_user_clk 212（高活跃）但 kv 空——序列含 kv 快照未覆盖的新点击；
- `avg_user_clk15d`：随 kv 带单调上升（no_hit 行 67.7→554）——kv 带本身是活跃度代理，**带内比较控制住了它**（SQL-4 教训已内建）；
- 异常备忘：k4 带 `2_hit_spu`(0.679) 略高于 `1_hit_item`(0.664)——重度兴趣用户里 spu 级命中与 item 级几乎等强；k1 带 hit_item(0.433) 低于 k0(0.734)——k0 高活跃新点击人群构成特殊。

**F-B 判决：kv 版证伪【事实读数】**——控制 `user__kv_*` 后 match 梯度不消失（k0 带 2.92×、k4 带 2.05×），"target 通路不值钱是因为 kv 已供给"不成立。

**改判【推断】**：T0−F1b≈0 的替代解释=**下游网络合成**——F1b 的 mean pooling 输出仍含命中商品嵌入，下游 DCNv2（cross_num=4）+PLE 从 (target emb, seq 池化, kv) 的粗交叉中可合成 target-aware 信号，显式 cross-attn 通路的边际被下游容量吸收；而 T2 的 +0.074pp 是下游难以合成的部分（per-position 的 `q−s`/`q⊙s` 残差视图）。判决性验证属模型侧实验而非 SQL（候选：去 kv 臂 / DCN cross_num=0 臂下重跑 T0 vs F1b，若此时差距拉开即坐实"下游合成"）。

> \*\*【20261105 判决实验回写】\*\*上述"下游合成"改判被模型侧判决实验（JUDGE_EXP_DOWNSTREAM_SYNTH v2，四臂 seed-1，见 `READOUT_20261105_JUDGE_SYNTH.md`）**部分回收**：删 dcnv2（C1）后 Δ=−0.070pp、摘 203 条 target-keyed kv（K1）后 Δ=−0.037pp——坐实版预测（拆合成后 Δ≥+0.15pp）**未出现**，强版（DCN 交叉吸收 ≥0.2pp）未获支持【事实读数，单 seed 未过符号闸，正式判决=未决】。弱合成（PLE 深路）逃逸阀仍开（C1K1 组合臂未跑）。**主推断修正**【推断】：T0−F1b≈0 是骨架性质——target-aware 点积读出（单双线性）本身无增益，三种骨干（base/C1/K1）下一致；值钱的是 4 路打分形态（T2−T0=+0.074pp），target-awareness 配上表达性读出才兑现。"T2=下游难合成的残差视图"降级为候选解释（未经 T2×C1 检验）。

## 6. 与 T0-T3 消融读数的对账

| 消融读数（20261030 单 seed）             | SQL 取证对应                                                                                                                                                                                                               |
| ---------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| T2−T0 = +0.074pp（4 路打分读出唯一正向） | H1（2.35× 匹配梯度）+ H3（72.3% 残差工作面）支持「打分形态值钱」【推断链】                                                                                                                                                 |
| T0−F1b ≈ 0（target 通路不值钱）          | **F-B kv 版证伪**（SQL-6：控 kv 后 match 梯度 2.05~2.92× 仍在）→ 曾改判"下游 DCN/PLE 合成"；**20261105 判决实验回收该改判**（C1/K1 拆合成后 Δ 仍 ≈0，强版未获支持）→ 终判"T0−F1b≈0 是骨架性质，点积读出本身无增益"【推断】 |
| F1b（等权 mean pooling）最差             | H5 干净版（远端命中控长度后仍 1.38×）→ 逐位置打分有活干，等权平均浪费检索信号                                                                                                                                              |
| T1−T0 ≈ 0（pos 编码无边际）              | 近因衰减真实（SQL-4 ①）且 ts 桶已编码近因 → 正弦 PE 冗余【推断】                                                                                                                                                           |
| T3（din+time_gate）无正收益              | 同带 cvr/ctr 近因信息已被 ts 桶内容维携带，门控通路边际小【推断】                                                                                                                                                          |

## 7. 链状态一览

| 环节                      | 状态                    | 结论落点                                                                                                                         |
| ------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| SQL-1 口径勘察            | ✅ 完成                 | `;` 分隔、pos0=最新、ts=近因秒数、过采样口径只解读相对                                                                           |
| SQL-2 匹配层级 × CTR      | ✅ 完成                 | H1/H3 成立：2.35× 梯度、72.3% 部分匹配工作面                                                                                     |
| SQL-3 命中位置 × CTR      | ✅ 完成                 | H5 成立（远端 1.37×）；cvr\|click 衰减更陡（混合口径）                                                                           |
| SQL-4 seq_len 分层 × 位置 | ✅ **完成（20261103）** | 近因衰减真实（带内 −20pp 不变）；远端检索价值干净 +14pp/1.38×；活跃度混淆证伪（基线随长度微降）；同带 cvr 远端 +4.1pp 修正"归零" |
| SQL-5 kv 列格式勘察       | ✅ **完成（20261104）** | 列类型=原生 `MAP<STRING,FLOAT>`（首判 JSON 被报错修正）、key=实体 id 原值字符串、下标取值、\\N=冷用户；标量列在                  |
| SQL-6 控 kv 残余 lift     | ✅ **完成（20261104）** | **F-B kv 版证伪**：带内梯度不消失（k0 2.92× / k4 2.05×）；kv 有偏好 lift（1.29×）但远小于 match 梯度；改判"下游网络合成"【推断】 |

**链结论（20261104 收档，20261105 判决实验后修订）**：「4 路打分形态值钱」的内在因素已坐实于数据面——匹配信号浓度（2.35×，SQL-2）+ 残差工作面（72.3% 部分匹配，SQL-2）+ 干净检索价值（+14pp/1.38×，SQL-4）；「target 通路不值钱」**不是** kv 供给所致（SQL-6 证伪），也**不是**下游 DCN 交叉合成吸收所致（20261105 判决实验强版未获支持，单 seed；弱合成逃逸阀未关）——终判【推断】：target-aware 点积读出本身无增益是骨架性质（base/C1/K1 三骨干 Δ≈0 一致），target-awareness 配上 4 路打分读出才兑现（T2 +0.074pp）。样本侧 SQL 链 + 强版合成判决均已收档；可选后续（非必须）：C1K1 组合臂关弱合成逃逸（2 run）或 C1 补 2 seed 过符号闸（4 run）。

______________________________________________________________________

*创建：2026-11-03；更新记录：①20261103——SQL-4 结果归档（§4.2/4.3）、SQL-3 两处推断修正标注（§2.3④/§3.3③⑤）；②20261104——SQL-5 结果定谳（§5.3）、SQL-6 已给（§5.4/5.5）；③20261104 二次修正——SQL-6 首版 GET_JSON_OBJECT 报错，kv 列类型定谳为原生 MAP\<STRING,FLOAT>（§5.3①/§5.4 已改 MAP 下标版）；④20261104 收档——SQL-6 结果与 F-B 判决（§5.6/5.7）、链结论（§7）；⑤20261105——判决实验四臂 seed-1 读数回写（§5.7 引注/§6/§7 修订），"下游合成"强版未获支持，主推断改"骨架性质"，详见 READOUT_20261105_JUDGE_SYNTH.md。SQL 链关闭；后续新问题另起文档。*
