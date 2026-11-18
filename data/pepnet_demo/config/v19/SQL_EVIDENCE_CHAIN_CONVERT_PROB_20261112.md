# convert_probability 勘验链取证（SQL-12 → 17，2026-11-11 ~ 11-12）

> **定位**：convert_probability 特征完整取证链底稿（append-only）——每条 SQL 的**原文、原始结果、判决**收档于此。
> 最终结论与链接入口见 [MASTER.md](MASTER.md) §3；完整论证/判读图/变更单见 [PLAN_CTR_NEXT_20261107.md](PLAN_CTR_NEXT_20261107.md) §9.10–9.12。
> **口径纪律**（20261112 固化）：SQL-12/13/14（"模型所见"类）在**编码表** `home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5`（`WHERE dt='20261030'`，90,988,963 行）；SQL-15/16R/17（"源头语义/质量"类）在**源头表** `feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set`（`WHERE dt='20261030'`）。
> 转化链路：源头表 → pyfg101 + `home_flow_2608_ctrcvr_sorter_config_fg_v5.json`（1186 特征，convert_probability `default_value="0"`）→ 编码表 → 打散 60d 窗。

______________________________________________________________________

## 0. 链总览（最终结论一页）

| SQL | 问题                                             | 判决                                                                                               | 详录                                         |
| --- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| 12  | convert_probability 泄漏/校准勘验                | **泄漏排除**（无近完美校准桶）；但值域无界（g 桶 avg_cp=52.9）→ P1-6 as-is 暂停                    | [PLAN §9.10](PLAN_CTR_NEXT_20261107.md)      |
| 13  | 值域定标（H_scale 百分制 vs H_score 无界打分）   | **H_scale 百分制确认**（j+k=0）；非零段 b→i cvr 严格单调 → **P1-6r 重启**（分桶序信号）            | [PLAN §9.11–9.12](PLAN_CTR_NEXT_20261107.md) |
| 14  | 零点反转构成分解（item_type）                    | **cp>0 100% 单品**；非单品结构性 N/A 恒 0；构成效应解释 2.55× 断崖 → 1.30×                         | [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)      |
| 15  | 单品冷启动假说（历史深度代理）                   | 浅历史倾斜**证实**（深度 45%、无历史率 11.7×）；窄义冷启动**算术排除**                             | [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)      |
| 16R | 源头零值语义（NULL/0/值域定标）                  | **真实 0 分 0 行**（min=1.1）；源头 NULL 43.88% → **编码 0 桶 100% 缺省填充**，"真实 0 分"语义撤销 | [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)      |
| 17  | NULL 语义判别（(a) 未打分 vs (b) 打分为 0→NULL） | **(a) 未打分/覆盖不足坐实**；(b) 强烈拒绝（画像不同形）                                            | [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)      |

**终局结论**【事实读数→判决】：

1. **convert_probability = 百分制"预估出单概率"打分（0~100），但 0 桶语义 = 源头 NULL 填充（未打分/覆盖不足）**，不是真实 0 分；非单品一律 N/A。0 桶 = 单品缺分 + 非单品 N/A 的混合，编码后经 FG `default_value="0"` 与真实值碰撞不可分辨。
1. **打分器在有分段质量良好**：非零段 cvr 严格单调（b→i 0.058→0.127），泄漏排除；校准差（高分段 /100 高估 ~7×）→ **只作序信号不作概率**。
1. **"零点反转" = 缺分人群高转化**（单品 NULL 桶 cvr 0.1450 > 最高真分桶 0.1017，历史深度仅 42%、无历史率 6.2×）——覆盖缺口人群特征，打分器 bug 假说排除。
1. **P1-6r 落地形态**：分桶 raw_feature，boundaries **1e-08/1/5/10/20/40/60/80/100**，emb=8，10 buckets，入 all 组（`home_flow_2608_v19_multiscene_v6f_p02a_p16cpbucket.config`，对照 = p02a 新基线）。0 桶注释终稿："0 = 源头 NULL 填充（未打分/覆盖不足），缺分=高转化人群规则，注意漂移敏感"。
1. **FG 需求单（P3）**：① −1 越界哨兵**必须**（非单品 N/A 与单品缺分现共用填充值 0）；② 上游问询已答：NULL=未打分（SQL-17 画像证据）；③ 建议扩大打分覆盖（浅历史商品人群转化反而高 30%）。

______________________________________________________________________

## 1. SQL-12：泄漏/校准勘验（20261111，编码表 dt='20261030'）

### 1.1 SQL 原文

```sql
SELECT
  bucket,
  COUNT(1) AS samples,
  AVG(is_conversion) AS actual_cvr,
  AVG(is_click) AS actual_ctr,
  AVG(convert_probability) AS avg_cp
FROM (
  SELECT
    is_conversion, is_click, convert_probability,
    CASE
      WHEN convert_probability <= 0 THEN 'a_cp_zero'
      WHEN convert_probability <= 0.1 THEN 'b_cp_0_10'
      WHEN convert_probability <= 0.3 THEN 'c_cp_10_30'
      WHEN convert_probability <= 0.5 THEN 'd_cp_30_50'
      WHEN convert_probability <= 0.7 THEN 'e_cp_50_70'
      WHEN convert_probability <= 0.9 THEN 'f_cp_70_90'
      ELSE 'g_cp_90_100'
    END AS bucket
  FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
  WHERE dt = '20261030'
) t
GROUP BY bucket
ORDER BY bucket;
```

### 1.2 原始结果【原始证据】

查询返回逐字原样（TSV，不作任何改写）：

```text
bucket	samples	actual_cvr	actual_ctr	avg_cp
a_cp_zero	36412115	0.1480793137119335	0.38041758903595685	0.0
b_cp_00_10	1084	0.017527675276752766	0.4225092250922509	0.06630073779527222
c_cp_10_30	4907	0.06949256164662727	0.3961687385367842	0.19447931579733807
d_cp_30_50	11296	0.05240793201133145	0.3667669971671388	0.4196104871441555
e_cp_50_70	13312	0.061373197115384616	0.3517878605769231	0.5879604774751127
f_cp_70_90	37712	0.05213194739075096	0.3411115825201527	0.823125801016377
g_cp_90_100	54508537	0.10161294550980152	0.35676547326889363	52.927328929321774
```

格式化视图（四舍五入 + 占比派生列，仅供扫读，**不作证据**）：

| bucket      | samples              | actual_cvr | actual_ctr | avg_cp  |
| ----------- | -------------------- | ---------- | ---------- | ------- |
| a_cp_zero   | 36,412,115（40.02%） | 0.1481     | 0.3804     | 0.0     |
| b_cp_00_10  | 1,084（0.00%）       | 0.0175     | 0.4225     | 0.0663  |
| c_cp_10_30  | 4,907（0.01%）       | 0.0695     | 0.3962     | 0.1945  |
| d_cp_30_50  | 11,296（0.01%）      | 0.0524     | 0.3668     | 0.4196  |
| e_cp_50_70  | 13,312（0.01%）      | 0.0614     | 0.3518     | 0.5880  |
| f_cp_70_90  | 37,712（0.04%）      | 0.0521     | 0.3411     | 0.8231  |
| g_cp_90_100 | 54,508,537（59.91%） | 0.1016     | 0.3568     | 52.9273 |

### 1.3 判决【事实读数→判决】

- 计数闭合 90,988,963（与 SQL-8/9 同窗逐位一致）；加权 actual_cvr 0.1202 ≈ eval mean_target 0.1204。
- **泄漏排除**：无任何桶接近"预测≈实际"的近完美校准（预注册泄漏分支未命中）。
- **值域无界**：g 桶 avg_cp=52.9 → 不是 0~1 概率；三峰分布（40.02% 零 / 0.075% (0,0.9\] / 59.91% >0.9）。
- 判决：**P1-6 as-is 暂停**；风险性质"泄漏"→"语义不明"；两假说待 SQL-13 判别（H_scale 百分制 vs H_score 无界打分）。详录 [PLAN §9.10](PLAN_CTR_NEXT_20261107.md)。

______________________________________________________________________

## 2. SQL-13：值域定标（20261111 晚，编码表 dt='20261030'）

### 2.1 SQL 原文（判读图先于结果预注册，PLAN §9.11）

```sql
SELECT
  bucket,
  COUNT(1) AS samples,
  AVG(is_conversion) AS actual_cvr,
  AVG(convert_probability) AS avg_cp
FROM (
  SELECT
    is_conversion, convert_probability,
    CASE
      WHEN convert_probability <= 0 THEN 'a_zero'
      WHEN convert_probability <= 1 THEN 'b_00_01'
      WHEN convert_probability <= 5 THEN 'c_01_05'
      WHEN convert_probability <= 10 THEN 'd_05_10'
      WHEN convert_probability <= 20 THEN 'e_10_20'
      WHEN convert_probability <= 40 THEN 'f_20_40'
      WHEN convert_probability <= 60 THEN 'g_40_60'
      WHEN convert_probability <= 80 THEN 'h_60_80'
      WHEN convert_probability <= 100 THEN 'i_80_100'
      WHEN convert_probability <= 1000 THEN 'j_100_1000'
      ELSE 'k_gt_1000'
    END AS bucket
  FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
  WHERE dt = '20261030'
) t
GROUP BY bucket
ORDER BY bucket;
```

### 2.2 原始结果【原始证据】（j/k 桶 0 行未出现在返回中）

查询返回逐字原样（TSV，不作任何改写）：

```text
bucket	samples	actual_cvr	avg_cp
a_zero	36412115	0.1480793137119335	0.0
b_00_01	93936	0.058071452904104925	0.7397696397800996
c_01_05	1430827	0.07441710283633171	3.3230734992592676
d_05_10	2289328	0.08065074117819727	7.409902445063158
e_10_20	3346593	0.08308898034508529	14.668611268138898
f_20_40	10094357	0.0884476346536981	29.841066748087623
g_40_60	14102001	0.0959885054610335	50.068323273583545
h_60_80	13530096	0.1104998811538366	71.13301302036129
i_80_100	9689710	0.1265618888490987	87.1472601307007
```

格式化视图（四舍五入 + 占比派生列，仅供扫读，**不作证据**）：

| bucket                 | samples              | actual_cvr | avg_cp |
| ---------------------- | -------------------- | ---------- | ------ |
| a_zero                 | 36,412,115（40.02%） | 0.1481     | 0.0    |
| b_00_01                | 93,936（0.10%）      | 0.0581     | 0.740  |
| c_01_05                | 1,430,827（1.57%）   | 0.0744     | 3.323  |
| d_05_10                | 2,289,328（2.52%）   | 0.0807     | 7.410  |
| e_10_20                | 3,346,593（3.68%）   | 0.0831     | 14.669 |
| f_20_40                | 10,094,357（11.09%） | 0.0884     | 29.841 |
| g_40_60                | 14,102,001（15.50%） | 0.0960     | 50.068 |
| h_60_80                | 13,530,096（14.87%） | 0.1105     | 71.133 |
| i_80_100               | 9,689,710（10.65%）  | 0.1266     | 87.147 |
| j_100_1000 / k_gt_1000 | 0（未出现在返回中）  | —          | —      |

### 2.3 判决【事实读数→判决】

- 计数闭合 90,988,963 逐位一致；**j+k = 0（\<1%）→ H_scale 百分制确认**（值域 0~100，avg_cp 与切点自洽），H_score 排除。
- **非零段 b→i actual_cvr 严格单调**（0.0581→0.1266，8/8 步升）→ 命中预注册"单调 → P1-6 重启"分支；零桶反转（0.1481 全表最高）须独立处理。
- 校准差（高分段 /100 高估 ~7×）→ **只作序信号不作概率**。
- 判决：**P1-6r 重启**——分桶 raw_feature，boundaries 1e-08/1/5/10/20/40/60/80/100，emb=8，10 buckets，入 all 组。config `home_flow_2608_v19_multiscene_v6f_p02a_p16cpbucket.config` 生成+冒烟 PASS。详录 [PLAN §9.11–9.12](PLAN_CTR_NEXT_20261107.md)。
- 注：判读图盲区（"0 是真实打分且零点反转"）解释性裁决已透明化，判据零变动（PLAN §9.12）。

______________________________________________________________________

## 3. SQL-14：零点反转构成分解（20261111 23:45，编码表 dt='20261030'）

### 3.1 SQL 原文

```sql
SELECT bucket, item_type,
  COUNT(1) AS samples,
  AVG(is_conversion) AS actual_cvr
FROM (
  SELECT
    CASE WHEN convert_probability <= 0 THEN 'a_zero' ELSE 'b_pos' END AS bucket,
    item_type,
    is_conversion
  FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
  WHERE dt = '20261030'
) t
GROUP BY bucket, item_type
ORDER BY bucket, item_type;
```

### 3.2 原始结果【原始证据】

查询返回逐字原样（TSV，不作任何改写）：

```text
bucket	item_type	samples	actual_cvr
a_zero	[0]	28438639	0.13151431051253895
a_zero	[1]	7702787	0.20858060855116467
a_zero	[7]	106906	0.00001870802387143846
a_zero	[9]	163783	0.27560247400523863
b_pos	[0]	54576848	0.10155419748681713
```

格式化视图（四舍五入 + 占比/注释派生，仅供扫读，**不作证据**）：

| bucket | item_type     | samples                   | actual_cvr           |
| ------ | ------------- | ------------------------- | -------------------- |
| a_zero | [0] 单品      | 28,438,639（零桶 78.1%）  | 0.1315               |
| a_zero | [1] 促销活动  | 7,702,787（21.2%）        | 0.2086               |
| a_zero | [7] 文章/公告 | 106,906（0.29%）          | 0.0000187（≈2 转化） |
| a_zero | [9] 优惠福利  | 163,783（0.45%）          | 0.2756               |
| b_pos  | [0] 单品      | 54,576,848（= 全部 cp>0） | 0.1016               |

（item_type 映射：0=单品，1=促销活动，7=文章/公告，8=多品，9=优惠福利；[8] 本窗 0 行。）

### 3.3 判决【事实读数→判决】

- 闭合三口径与 SQL-13 逐位一致；**cp>0 的样本 100% 是单品**（b_pos 仅 1 行）。
- **构成效应证实**：非单品（21.9% 零桶）结构性 N/A 恒 0；促销 cvr 0.209 / 福利 0.275 结构性拉高零桶——全口径 2.55× 断崖解释到单品内 1.30×。
- 残余反转仍在：单品 cp=0 cvr 0.1315 > cp>0 0.1016 且 > 最高分桶 0.1266 → SQL-15 冷启动假说。
- 判决：P1-6r 结构不变（0 独立成桶 + item_type 在 all 组交叉消歧）。详录 [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)。

______________________________________________________________________

## 4. SQL-15：单品冷启动假说（20261111 23:57，源头口径下亦用编码表 item 历史深度代理）

### 4.1 SQL 原文

```sql
SELECT
  CASE WHEN convert_probability <= 0 THEN 'a_zero' ELSE 'b_pos' END AS bucket,
  COUNT(1) AS samples,
  AVG(item__cnt_click_rt24h) AS avg_item_click_24h,
  SUM(CASE WHEN item__cnt_click_rt24h <= 0 THEN 1 ELSE 0 END) / COUNT(1) AS no_hist_rate,
  AVG(is_conversion) AS actual_cvr
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261030' AND item_type[0] = 0
GROUP BY bucket
ORDER BY bucket;
```

### 4.2 原始结果【原始证据】

查询返回逐字原样（TSV，不作任何改写）：

```text
bucket	samples	avg_item_click_24h	no_hist_rate	actual_cvr
a_zero	28438639	136.6631539927069	0.02897290548960518	0.13151431051253895
b_pos	54576848	301.1379597627184	0.002484002007591204	0.10155419748681713
```

格式化视图（四舍五入、no_hist_rate 转百分比仅供扫读，**不作证据**）：

| bucket | samples    | avg_item_click_24h | no_hist_rate | actual_cvr |
| ------ | ---------- | ------------------ | ------------ | ---------- |
| a_zero | 28,438,639 | 136.66             | 2.90%        | 0.1315     |
| b_pos  | 54,576,848 | 301.14             | 0.25%        | 0.1016     |

### 4.3 判决【事实读数→判决】

- 闭合 83,015,487 与 SQL-14 单品两侧逐位一致。
- **浅历史倾斜证实**：零分段深度 136.7 = 有分段 45%；无历史率 2.90% vs 0.25%（11.7×）。
- **窄义冷启动算术排除**：零分段 97.1% 有历史；无历史子集 cvr=100% 时均值上限 0.1276 < 实测 0.1315——残余反转必须在**有历史人群内部**。
- 判决：P1-6r 不动；FG 反馈稿定稿（浅历史欠分方向）。详录 [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)。

______________________________________________________________________

## 5. SQL-16R：源头零值语义定标（20261112 11:12，源头表 dt='20261030'）

> 触发：用户质询"为何不在 feature_mall\_...\_training_set 源头表探索"→ 查明 fg_v5.json 中 convert_probability `default_value="0"`（1186 特征 998 个 default=0）→ 编码表 0 = 真实 0 ∪ 缺省填充不可分辨，须回源头定标。

### 5.1 SQL 原文

```sql
SELECT
  COUNT(1) AS samples,
  SUM(CASE WHEN convert_probability IS NULL THEN 1 ELSE 0 END) AS null_cnt,
  SUM(CASE WHEN convert_probability = 0 THEN 1 ELSE 0 END) AS zero_cnt,
  SUM(CASE WHEN convert_probability > 0 AND convert_probability <= 100 THEN 1 ELSE 0 END) AS pos_0_100,
  SUM(CASE WHEN convert_probability > 100 THEN 1 ELSE 0 END) AS gt_100,
  MIN(convert_probability) AS min_cp,
  MAX(convert_probability) AS max_cp
FROM feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set
WHERE dt = '20261030';
```

### 5.2 原始结果【原始证据】

查询返回逐字原样（TSV，不作任何改写）：

```text
samples	null_cnt	zero_cnt	pos_0_100	gt_100	min_cp	max_cp
2691204	1180823	0	1510381	0	1.1	99.59
```

格式化视图（千分位 + 占比派生列，仅供扫读，**不作证据**）：

| samples   | null_cnt            | zero_cnt | pos_0_100 | gt_100 | min_cp | max_cp |
| --------- | ------------------- | -------- | --------- | ------ | ------ | ------ |
| 2,691,204 | 1,180,823（43.88%） | 0        | 1,510,381 | 0      | 1.1    | 99.59  |

### 5.3 判决【事实读数→判决】

- 闭合 1,180,823+0+1,510,381+0 = 2,691,204 ✓。
- **命中"缺省填充实锤"分支且更强**：源头**真实 0 分 = 0 行**，有分值域 [1.1, 99.59]——**源头打分器从不输出 0**；编码表 0 桶 100% = NULL → FG default_value=0 填充。"单品 0 = 真实 0 分"语义**撤销**。
- 零点反转终局改判：**缺分人群高转化**（非打分器 0 点低估）；打分器有分段序有效（SQL-13）。
- 判决：P1-6r 结构/判据不动，0 桶注释改定"0 = 缺分填充"；FG −1 哨兵建议→**必须**。详录 [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)。

______________________________________________________________________

## 6. SQL-17：NULL 语义判别（20261112 11:36，源头表 dt='20261030'，item_type=0）

### 6.1 SQL 原文（判读图先于结果预注册）

```sql
SELECT
  CASE
    WHEN convert_probability IS NULL THEN 'a_null'
    WHEN convert_probability <= 5 THEN 'b_low_0_5'
    WHEN convert_probability <= 20 THEN 'c_mid_5_20'
    ELSE 'd_high_20_100'
  END AS cp_band,
  COUNT(1) AS samples,
  AVG(item__cnt_click_rt24h) AS avg_item_click_24h,
  SUM(CASE WHEN item__cnt_click_rt24h <= 0 THEN 1 ELSE 0 END) / COUNT(1) AS no_hist_rate,
  AVG(is_conversion) AS actual_cvr
FROM feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set
WHERE dt = '20261030' AND item_type = 0
GROUP BY cp_band
ORDER BY cp_band;
```

**预注册判读图**：NULL 桶历史画像显著浅于低分桶 → (a) 未打分/覆盖不足坐实；两桶同形 → (b) 打分为 0→NULL 坐实（底端反转，bug 级）。

### 6.2 原始结果【原始证据】

查询返回逐字原样（TSV，不作任何改写）：

```text
cp_band	samples	avg_item_click_24h	no_hist_rate	actual_cvr
a_null	980174	158.37751460454982	0.026906447222635983	0.14501098784501526
b_low_0_5	69382	402.94906459888733	0.004352713960393185	0.06807241071171197
c_mid_5_20	310434	433.8619577752437	0.0025995863855118964	0.08190146697848819
d_high_20_100	1130565	376.47665017048996	0.0016584628039962319	0.10167747984414872
```

格式化视图（四舍五入、no_hist_rate 转百分比仅供扫读，**不作证据**）：

| cp_band       | samples   | avg_item_click_24h | no_hist_rate | actual_cvr |
| ------------- | --------- | ------------------ | ------------ | ---------- |
| a_null        | 980,174   | 158.38             | 2.69%        | 0.1450     |
| b_low_0_5     | 69,382    | 402.95             | 0.44%        | 0.0681     |
| c_mid_5_20    | 310,434   | 433.86             | 0.26%        | 0.0819     |
| d_high_20_100 | 1,130,565 | 376.48             | 0.17%        | 0.1017     |

### 6.3 判决【事实读数→判决】

- **互证闭合**：非单品 = 2,691,204 − 2,490,555 = 200,649 = 1,180,823 − 980,174（非单品 NULL 数）——全部非单品都是 NULL，与 SQL-14"cp>0 100% 单品"逐位互证。
- **命中 (a) 分支**：NULL vs 低分桶(0,5\] 画像显著不同形——深度 158.4 vs 402.9（39%）、无历史率 2.69% vs 0.44%（6.2×）、cvr 0.1450 vs 0.0681（2.13×）。
- **(b) 强烈拒绝**：若 NULL=打分为 0→NULL 应近似最低真分桶，实际差 2.5×/2.13×/6.2×——打分器底端反转 bug 假说**排除**。
- 有分段自检：b→c→d cvr 0.0681→0.0819→0.1017 严格单调，历史深度大致平——打分器覆盖人群内序有效。
- **判决：NULL = (a) 未打分/覆盖不足；FG 反馈走覆盖路线**；convert_probability 勘验链**全部收档**（SQL-12→17 不再追加）。详录 [PLAN §9.12](PLAN_CTR_NEXT_20261107.md)。

______________________________________________________________________

*创建：2026-11-12。本文件为取证链底稿（append-only），判决更新写 PLAN §9.10–9.12，结论同步 MASTER.md。*
