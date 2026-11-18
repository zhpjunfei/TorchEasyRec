# PLAN_CTR_NEXT_20261107 —— v6f_kv_fusion 基线 · 接下来的优化方案（执行版）

> ⭐ **最新最全结论与进展见 [`MASTER.md`](MASTER.md)（唯一活文档）**；本文件为方案证据底稿，判决更新以 MASTER.md 为准。

> **基线**：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`（下称 v6f），eval ctr **0.723206** / cvr **0.744960**（20261030 样本集，All-ranks 1,638,400，同 eval 指纹 17 位逐位一致）。
> **本文档定位**：`PLAN_CTR_NEXT_20261105.md`（路线图）+ `UNUSED_FEATURES_FG_V5_20261105.md` §六（DDL 双表定谳）合并后的**执行版**。1105 的证据盘点与不做清单继续有效；**执行顺序与臂规格以本方案为准**。
> **口径纪律**：只解读 Δ（绝对 AUC 含 train==eval 乐观偏置，T 债未清）；单 seed σ_Δ≈0.25pp；任何 ≥0.2pp 的宣称走 3-seed 符号闸。方案即预注册：判据先于实验写死。
> 创建：2026-11-07。

______________________________________________________________________

## 〇、一句话现状【事实读数】

12 跑全景（`SUMMARY_20261030_ALL_RUNS.md`）+ SQL-1~7 取证链（`SQL_EVIDENCE_CHAIN_20261103.md`）+ 判决实验（`READOUT_20261105_JUDGE_SYNTH.md`）+ DDL 双表核查（`UNUSED_FEATURES_FG_V5_20261105.md` §六）之后的格局：

| 已证值钱（在基线内/保留）                          | 已证不值钱（不再投）                          | 数据面定谳（20261107 DDL）                                 |
| -------------------------------------------------- | --------------------------------------------- | ---------------------------------------------------------- |
| exposure 族 kv 89 条 **+0.52pp**（全场最大单杠杆） | 序列骨架替换（self-attn/transformer/pos）全负 | P0-1~4 前提**全成立**，纯 config 可跑                      |
| DCNv2 cross_num=4 **+0.42~0.48pp**（通用放大器）   | ID 级 target-keyed kv 203 条 ≈0.03pp          | **P0c/P0d（cart/stay/share/负反馈/场景曝光）数据面不存在** |
| DIN 4 路打分读出（q,s,q−s,q⊙s，基线已是该形态）    | target-aware 点积读出（T0−F1b≈0，骨架性质）   | 人群比率族 219 条样本有、编码丢弃（试点级）                |
| 近因/位置信息（SQL-3/4 带内 −20pp 梯度）           | time_gate 单序列（T3 −0.062pp）               | 编码表最终可接口径 = **未用 143 列**                       |

**当前最短路径**【推断】：DDL 核查解锁的 **6 个纯 config 臂**（零 FG 依赖、零上游排期）先行；FG 侧扩 kv（P0a/P0b）转需求单**并行**推进（长周期）。

______________________________________________________________________

## 一、SQL-8（第一梯队立项前唯一前置，按纪律先给这一条）

DDL 只证明"列在"，不证明"有货"。P0-1 两序列的预期上限由**填充率**决定，跑前先看一眼：

```sql
-- SQL-8: L0 双序列 + 双 ts 的填充率/长度分布（P0-1/P0-2 数据面核）
-- 表 = 60d 训练集（fg 后编码表，模型实际输入；schema 前缀按执行库调整）
SELECT
  COUNT(1) AS samples,
  -- like_100_seq（P0-1a）
  AVG(IF(SIZE(like_100_seq__item_id) > 0, 1, 0))                          AS like100_fill_rate,
  AVG(SIZE(like_100_seq__item_id))                                        AS like100_avg_len,
  AVG(IF(SIZE(like_100_seq__item_id) >= 5, 1, 0))                         AS like100_fill_ge5,
  -- search_conversion_20_seq（P0-1b）
  AVG(IF(SIZE(search_conversion_20_seq__item_id) > 0, 1, 0))              AS sconv20_fill_rate,
  AVG(SIZE(search_conversion_20_seq__item_id))                            AS sconv20_avg_len,
  AVG(IF(SIZE(search_conversion_20_seq__item_id) >= 5, 1, 0))             AS sconv20_fill_ge5,
  -- chajia/search_click 的 ts（P0-2a 前提的数据面核，DDL 已证列在）
  AVG(IF(SIZE(chajia_click_100_seq__ts) > 0, 1, 0))                       AS chajia_ts_fill,
  AVG(IF(SIZE(search_click_100_seq__ts) > 0, 1, 0))                       AS search_ts_fill
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5;
```

**判读标准（预注册）**【推断】：

- fill_rate ≥ 20% 且 avg_len ≥ 5 → P0-1 该臂按 +0.1~0.3pp 预期跑；
- fill_rate 5%~~20% → 预期下调至 +0.05~~0.15pp，仍跑（成本已 sunk 在列上）；
- fill_rate < 5% → 该臂降级到第二梯队末位或弃；
- 两序列填充率差异决定 P0-1a/P0-1b **跑序**（高的先跑）。
- chajia_ts_fill / search_ts_fill 只需非零（列是借位现成的，P0-2a 成本极低）。

全扫太重时可加 `TABLESAMPLE`；拿到结果贴回来，按纪律再给下一条（如有必要）。

______________________________________________________________________

## 二、第一梯队：6 个纯 config 臂（新增 config，不动既有文件）

**共同规格**【预注册】：

- 每臂 = 新文件 `home_flow_2608_v19_multiscene_v6f_pXX_*.config`，由 v6f_kv_fusion **单变量**派生；生成走字节级 diff 校验（只含预期改动）+ EasyRecConfig proto 解析冒烟（绕 fbgemm 注册法，与判决实验 config 同规程）。
- 训练口径：20261030 样本集、同 eval 指纹、T_max 纪律沿用（记录实际步数核对调度）。
  |     |     |     |
  | --- | --- | --- |
- 判读：Δctr ≥ **+0.10pp** 且 cvr 方向不背离 → 续投/过符号闸；|Δ| ≤ 0.05pp → 弃；−0.05~−0.2pp → 记负入不做清单。
- 随臂搭车：P2a grad clipping（`grad_clipping {clipping_type:"norm", max_gradient:5.0, enable_global_grad_clip:true}`，保险项 ≈0 收益，选一臂带上即可，不单独占 run）。

| 序  | 臂                                      | 新 config 文件                   | 改动量                                    | 预期【推断】                   |
| --- | --------------------------------------- | -------------------------------- | ----------------------------------------- | ------------------------------ |
| 1   | **P0-1a** like_100_seq 接入             | `..._v6f_p01a_like100seq.config` | 1 序列块 20 子字段 + 1 组 + 1 din_encoder | **+0.1~0.3pp**（最大杠杆）     |
| 2   | **P0-1b** search_conversion_20_seq 接入 | `..._v6f_p01b_sconv20seq.config` | 同上                                      | **+0.1~0.3pp**                 |
| 3   | **P0-4** exposure rt 标量 5 条          | `..._v6f_p04_exposurert5.config` | 5 个标量定义 + 入 all 组                  | +0.05~0.15pp（最稳）           |
| 4   | **P0-2a** chajia/search ts 补全         | `..._v6f_p02a_seqts.config`      | 2 个 raw_feature + 2 组引用               | +0.05~0.15pp                   |
| 5   | **P0-3** overlap 补齐 10 条             | `..._v6f_p03_overlap10.config`   | 10 个 bucketizer 定义 + 入组              | +0.03~0.1pp                    |
| 6   | **P0-2b** time_gate 四序列齐开          | `..._v6f_p02b_timegate4.config`  | 4 个 din_encoder 加 `time_gate_dim: 8`    | −0.05~+0.1pp（试探，区间含负） |

### 变更单（生成时逐字执行；模板行号以 v6f_kv_fusion 为准）

**P0-1a / P0-1b（同构，仅名不同）**

1. `feature_configs` 区新增 `sequence_feature` 块：`sequence_name: "like_100_seq"`（P0-1b：`search_conversion_20_seq`）、`sequence_length: 100`（P0-1b：20）、`sequence_delim: ";"`；20 个子字段**逐位照抄 click_50_seq 块**（L10083–10268）：同 `embedding_dim`/`hash_bucket_size`/`embedding_name`（item_id 用 `shared_item_id`，v4 P1-3 全局共享约定不破），仅把 `feature_name` 前缀换成新序列名。子字段集与 DDL 逐位一致（item_id/cate_id_path/related_goods_ids/brand/core_entity/first_cate_id/second_cate_id/third_cate_id/price_tag/promotion_channel/publish_user/site/spu_id/discount_intensity/dianpupingfen/pinpaidengji/dianpufensi/item_type/username/ts，已对账 20/20）。
1. `ts` 子字段照 click_50 形态 `raw_feature { feature_name: "ts", embedding_dim: 8, boundaries: 19 档借位 click_50（647~694233 秒）}`——边界按"同族模板借位"惯例，正式版再按训练数据分位数重算。
1. `feature_groups` 新增组 `like_100_seq`（P0-1b：`search_conversion_20_seq`），20 个 `feature_names: "<seq>__<field>"`。
1. 模型序列编码区（L18649–18699 现有 6 个 din_encoder 旁）新增 1 个 `din_encoder { attn_mlp { hidden_units: 128 hidden_units: 64 activation: "Dice" } }`，绑定新组——与现有 6 个逐字节同构。
1. **维度账**【事实读数】：子字段 emb 合 = 224（19 id 项 216 + ts 8，与 click_50 同构），din 输出 224，下游 concat 自动 +224；生成后冒烟核对前向维度链（防 BUG_FIX_MLP_DIMENSION 复发）。

**P0-4（5 条标量）**

- 新增定义照 `user__cnt_exposure_15d` 模板（L11997）：`user__cnt_exposure_rt1h` / `rt3h` / `rt12h` / `rt24h` + `user__num_exposure_avg_current_price_15d`（照同族 num 模板），入 all 组。

**P0-2a（ts 补全）**

- 在 `chajia_click_100_seq`（L10632）/ `search_click_100_seq`（L10792）块内各加 `ts` raw_feature（同 P0-1a 第 2 条形态）；对应组各加 `chajia_click_100_seq__ts` / `search_click_100_seq__ts` 引用（ts 只挂全名、不成对）。维度账：两序列 din 输出各 216→224。
- ts boundaries **不借位**，用 §9.8 分位数定标终版（per-seq 19 cuts）；行号级变更单见 §9.8。

**P0-3（overlap 10 条）**

- 照 `offline_chajia_*_common_ratio` 模板（L12095–12224）新增 `offline_like_{brand,first_cate_id,second_cate_id,third_cate_id,site}_common_ratio` + `offline_order_*` 同 5 实体，共 10 条（编码表 FLOAT 列已核实在），边界借位同族，入 all 组。

**P0-2b（time_gate 四序列）**

- 给 **click_10 / click_50 / conversion_20 / favorite_10** 四个 din_encoder 加 `time_gate_dim: 8`（T3 形态推广）。⚠️ 双因子警示（T3 归档已记）：time_gate 开启后 ts 8 维退出 DIN 输出（224→216），维度链整体平移，生成时按各 encoder 实际输出核对。
- 不含 chajia/search（基线无 ts）；若 P0-2a 先落地并过闸，"6 序列 time_gate"另立一臂，不混入本臂。

______________________________________________________________________

## 三、第二梯队：纯 config 边际补强（视一梯队读数挑跑，≤4 run）

| 臂                                | 内容                                                                             | 备注                                                                 |
| --------------------------------- | -------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| P1-1 item 先验组                  | srh_hot + price_drop_freq + comment_tag + his_high_level + coupon_titles（5 条） | 一次一族打包单臂                                                     |
| P1-2 价格偏好补齐                 | user\_\_num\_{chajia,search}*click_avg_current_price*{15d,360d} 4 条             | 与 P0-4 同属"价格带"，可在 P0-4 过闸后合并归因                       |
| P1-3 实时场景计数                 | user\_\_cnt\_{chajia,search}\_click_rt{1h,3h,12h,24h} 8 条                       | 与 P0-4 同构"rt 标量"                                                |
| P1-4 订阅画像 5 条                | is_atpush / is_not_disturb / is_subscribe\_{clockin,discount,savemoney}          | 便宜小臂                                                             |
| P1-5 粗交叉试点                   | gender_x_third_cate_id_fg 1 条先行                                               | 过闸再议扩 9 条粗交叉                                                |
| P1-6 convert_probability **单臂** | item 转化先验                                                                    | **先过泄漏核查**（生成时点 vs label 窗）——核查不过则弃，不过闸不并组 |

______________________________________________________________________

## 四、第三梯队：FG/上游需求单（长周期，并行推进，不占 run）

| 需求单 | 内容                                                      | 对应                                                                                                       |
| ------ | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| R1     | cfr/ctr/cvr 比率族实体扩展 12→19 + 补 15d/rt 窗（~35 列） | 1105 P0a（数据侧最高优先）                                                                                 |
| R2     | exposure 补 60d/360d 窗 + 近/远衰减比值特征（~45 列）     | 1105 P0b                                                                                                   |
| R3     | 新行为族 cart / stay / share / 负反馈 kv                  | 1105 P0c（**DDL 判死数据面**，需 FG+样本管道从零建）                                                       |
| R4     | 场景细分 exposure（search/chajia_exposure）               | 1105 P0d（同上）                                                                                           |
| R5     | 人群比率族 `__kv_ratio_*` 219 条启用                      | 需改 pyfg 编码配置；先试点 1~2 条（age_group\_\_kv_ratio_third_cate_id_click_exposure_15d 之类），不进主线 |

R1/R2 需求单定稿后走上游 FG 排期；落地后按同一判据各出 1 个新 config 臂。

______________________________________________________________________

## 五、微旋钮/保险（搭车，不单独占 run）

- **P2a grad clipping**：随第一梯队任一臂带上（现读数 grad_norm 0.1–0.3 无爆炸，纯保险）。
- **P2b T2 温度/clip**：din 读出 `softmax(score/T)` T∈{0.5,2} + score clip ±10，低预期（±0.03pp），顺手再跑。
- **P2c exposure 接入位置**：exposure kv 移 all 组 → domain 门控组（调制而非交叉），1 run。
- **P2d cvr 头独立读出**：cvr 头序列读出独立配置（更近因加权），cvr 侧 +0.05~0.15pp 试探。

______________________________________________________________________

## 六、判据与纪律（预注册，先于实验）

|     |     |     |     |     |
| --- | --- | --- | --- | --- |

1. **过闸**：Δctr ≥ +0.10pp 且 cvr 不背离 → 续投；|Δ| ≤ 0.05pp → 弃；过闸臂补 2 seed 配对，**3/3 同号 + |mean| ≥ 0.15pp** 才宣称；宣称前必须清 **train==eval 债**（rm -rf/train==eval 修复待批）。
1. **单变量**：一臂一族、唯一变量；新 config 不动既有文件；字节级 diff + proto 冒烟 4/4、8/8 式校验。
1. **口径**：全部 20261030 样本集、同 eval 指纹；只解读 Δ；跨行诊断、组内配对判决。
1. **SQL 纪律**：一条一条给，基于上一条结果给下一条（当前在 SQL-8）。
1. **判决实验收尾（非阻塞）**：B = C1 补 2 seed（4 run）/ C = C1K1 组合臂（2 run）可在 FG 排期期间穿插，不影响本方案执行。

______________________________________________________________________

## 七、执行顺序与预算

```
D0        SQL-8（fill rate，0.5 天）→ 定 P0-1a/1b 跑序与预期档位
D0–D1     生成第一梯队 6 个 config（diff 校验 + 冒烟；新文件不动既有）
第 1 周   P0-1a →（按 SQL-8 定序）P0-1b → P0-4 → P0-2a，逐臂读数过判据
第 2 周   P0-3 → P0-2b；第二梯队挑 1–2 臂；R1/R2 需求单并行给上游
决策点    任一臂过 +0.10pp → 3-seed 符号闸 → 清 T 债 → 出 READOUT 归档
预算      模型侧 ≤10 run（第一梯队 6 + 第二梯队 ≤2 + 符号闸补 seed 视需要）；
          FG 侧集中在 R1/R2（~80 新列）
```

**预期账**【推断】：P0-1a/b 合计 +0.1~~0.3pp（上限看 SQL-8 填充率）；P0-4/P0-2a/P0-3 合计 +0.1~~0.3pp；组合中枢 **ctr 0.7232 → 0.725+**（+0.2pp 量级）。要上 +0.5pp 需 R3/R4 出现"第二个 exposure 级"行为族。

______________________________________________________________________

## 八、明确不做清单（继承 1105，防回头路）

1. 序列骨架替换（self-attn / transformer 点积 / pos encoding）——12 跑全负；
1. 加层/加宽/容量类——v14 证否；
1. target-ID 级 kv 增补（click/conversion/favorite 复述）——K1≈0.03pp；
1. 多任务动态平衡（GradNorm/Uncertainty）——方向不利 CTR；
1. Focal loss / 难负样本——case-control 过采样集上动校准、不可比，暂缓；
1. 特征重要性加权梯度——破坏对照纪律；
1. 训练侧 tricks 直接平移（零实验数据，tzrec 已覆盖大半）；
1. ID 级 combo / item×item combo / copyright_end / modifiers / sqk_id / dev_model / sdk_version / jpush / receive_push / type / pub_time / cate（四层类目共线）。

## 九、更新记录①（20261107 · SQL-8 读数 → P0-1 降级、跑序重排）

### 9.1 SQL-8 原始结果【原始证据】（60d 编码表，99,528,307 行）

| 指标                   | like100   | sconv20    | chajia_ts | search_ts |
| ---------------------- | --------- | ---------- | --------- | --------- |
| fill_rate              | 1.0       | 1.0        | 1.0       | 1.0       |
| avg_len                | **1.123** | **2.119**  | —         | —         |
| fill_ge5（len≥5 占比） | **0.33%** | **10.56%** | —         | —         |

### 9.2 读数【事实读数】

1. **fill_rate=1.0 与 avg_len≈1 并存**是异常形态：要么空序列被占位符填充（`[""]`/`["0"]` 之类，SIZE=1 即算"fill"），要么序列真退化到人均 ~~1 条。两种假设都与聚合数自洽（占位符假设下 like 真实行 ≈3%、真实行均长 ≈5；真实假设下 like 长度分布为 1~~4 条）——**SQL-9 判别**。
1. **判据对照**：过闸条件"fill≥20% **且** avg_len≥5"未全过（两臂 avg_len 双双 \<5，密度代理失效）→ 不得套用 +0.1~0.3pp 档。判据三分支未覆盖"fill=1.0 且 avg_len\<5"，按**保守方向补全**（不挪门槛）：密度代理失效即降档，SQL-9 判别图预注册于 §9.4。
1. **血统修正（收回上一版表述）**【事实读数】：`offline_like_100`（12 子字段）**已在 v6f 内**（FG 对账：48 个序列命名特征全在用）→ P0-1a 是"在线实时补量"而非新工作面；`search_conversion_20_seq` = 已在用的 `conversion_20_seq` 的**场景切片** → P0-1b 是"场景细分"而非新匹配源。**§二 表中 P0-1a/b "+0.1~0.3pp（最大杠杆）"的表述收回**，下调为 P0-1a +0~~0.05pp、P0-1b +0.03~~0.1pp。
1. P0-2a 前提复核通过（chajia/search ts fill=1.0）【事实读数】。

### 9.3 跑序重排（20261107 版，已被 §9.6 终版取代）

```
第一梯队（改）: P0-4 → P0-2a → P0-3 → P0-2b          （原 P0-1a/1b 让位）
第二梯队（改）: P1-1…P1-6 不变 + P0-1b 降至本梯队末位（+0.03~0.1pp 试探档）
暂停           : P0-1a（待 SQL-9 判占位符后定弃/留；两种假设下默认弃）
```

**P0-3 地位上升**【推断】：offline_like/order common_ratio 是 like/order 行为的**密度无关**标量形态——序列稀疏的情形下，overlap 标量是吃这批行为的稳健通道（且与 P0-4 的曝光族方向互补）。

### 9.4 SQL-9（下一条，判别占位符假设；判读图先于结果预注册）

```sql
-- SQL-9: 占位符核查（SQL-8 异常：fill=1.0 但 avg_len≈1）+ click_50 同口径参照
-- 注：若 len1_placeholder/len1_real 均为 0 而 len1_rate 非 0 → [0] 取空（ODPS 下标 1 基），改 [1] 重跑本条
SELECT
  COUNT(1) AS samples,
  -- ① 参照锚：click_50（已证有货，校准同口径）
  AVG(SIZE(click_50_seq__item_id))                 AS click50_avg_len,
  AVG(IF(SIZE(click_50_seq__item_id) >= 5, 1, 0))  AS click50_fill_ge5,
  -- ② like_100：len=1 占比、首元素占位符形态、首元素基数
  AVG(IF(SIZE(like_100_seq__item_id) = 1, 1, 0))   AS like100_len1_rate,
  AVG(IF(SIZE(like_100_seq__item_id) = 1
         AND like_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS like100_len1_placeholder,
  AVG(IF(SIZE(like_100_seq__item_id) = 1
         AND like_100_seq__item_id[0] NOT IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS like100_len1_real,
  COUNT(DISTINCT IF(SIZE(like_100_seq__item_id) = 1, like_100_seq__item_id[0], NULL)) AS like100_len1_distinct_first,
  -- ③ sconv20 同构
  AVG(IF(SIZE(search_conversion_20_seq__item_id) = 1, 1, 0))   AS sconv20_len1_rate,
  AVG(IF(SIZE(search_conversion_20_seq__item_id) = 1
         AND search_conversion_20_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS sconv20_len1_placeholder,
  AVG(IF(SIZE(search_conversion_20_seq__item_id) = 1
         AND search_conversion_20_seq__item_id[0] NOT IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS sconv20_len1_real,
  COUNT(DISTINCT IF(SIZE(search_conversion_20_seq__item_id) = 1, search_conversion_20_seq__item_id[0], NULL)) AS sconv20_len1_distinct_first
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5;
```

**判读图（预注册）**：

- `click50_avg_len ≥ 8` → 口径校准通过，like/sconv 是真稀疏；若 click50 也 ≈1 → 口径坏了（SQL-3/4 已证 click 有货，预期不会）。
- `len1_placeholder ≈ len1_rate` 且 `len1_distinct_first ≤ 10` → **占位符假设成立**：真实填充 = 1 − len1_rate（like 预计 ~3%）→ P0-1a **弃**（\<5% 判据）；sconv 真实填充看 len≥2 行占比再定档。
- `len1_real ≈ len1_rate` 且 `len1_distinct_first` 大 → **真退化**：P0-1a 弃（人均 1.12 条无匹配面），P0-1b 维持 +0.03~0.1pp 试探档（1 run 值得，放第二梯队末位）。
- 任一情形下 P0-4/P0-2a/P0-3/P0-2b 的跑序与预期**不受影响**（本判别只裁 P0-1a/1b）。

### 9.5 SQL-9 结果与判决（20261109，`WHERE dt='20261106'`，99,528,307 行）

> ⚠️ **分区口径修正（20261109 二次修正）**：应为 `WHERE dt='20261030'`（12 跑同窗）。本节数字为 dt='20261106' 窗，**判决已由 §9.7 的 20261030 重跑数字复核取代**（两窗结论逐项一致，无漂移翻转；本节保留作稳定性旁证）。

**分区口径修正**【用户反馈】：训练集表按 dt 分区，SQL 必须带 `WHERE dt='...'`（本表现用 `dt='20261106'`）。SQL-9 与 SQL-8 计数逐位相同（99,528,307）→ 两次读数同分区、可比。

**SQL-9 原始结果**【原始证据】：

| 指标              | 数值       | 指标                        | 数值       |
| ----------------- | ---------- | --------------------------- | ---------- |
| click50_avg_len   | **40.276** | click50_fill_ge5            | **92.90%** |
| like100_len1_rate | 98.66%     | like100_len1_placeholder    | **93.91%** |
| like100_len1_real | 4.75%      | like100_len1_distinct_first | 18,574     |
| sconv20_len1_rate | 67.86%     | sconv20_len1_placeholder    | **49.25%** |
| sconv20_len1_real | 18.61%     | sconv20_len1_distinct_first | 94,695     |

**判决（对照 §9.4 预注册图）**：

1. **口径校准通过**【事实读数】：click_50 均长 40.28（cap=50）、ge5 92.9%——同口径下 like/sconv 的稀疏是**真实的**，不是度量假象。
1. **占位符假设以"主导污染"形式成立**【事实读数】：like 的 len-1 行中 95.2%（=93.91/98.66）首元素是占位符（''/'0'/'-1' 等）；sconv 的 len-1 行中 72.6% 是占位符。distinct 大（18,574/94,695）源于真实单条行里的真 item id，**不推翻**占位符结论（预注册图的 distinct≤10 条件按字面未过，按"主导污染"精神裁决——与两分支的 P0-1a 结论一致，无挪门槛）。
1. **真实填充率（SIZE>0 口径修正后）**【事实读数】：like_100 = 1 − 0.939 ≈ **6.1%**（4.75% 真单条 + 1.34% len≥2，len≥2 行均长 ≈10.2）；sconv20 ≈ **50.7%**（18.6% 真单条 + 32.1% len≥2，len≥2 行均长 ≈4.5、全真实行均长 ≈3.2）。
1. **定谳**：
   - **P0-1a 弃（终审）**：真实填充 6.1% 贴着 5% 弃档线、真实均长 ~3、且在线增量仅为 offline_like_100（已在用）的实时补量——两分支预注册均为弃，终审不变。
   - **P0-1b 维持二梯队末位试探档（+0.03~0.1pp）**：真实填充 50.7% 过 20% 线，但真实均长 3.2 未过 5 密度门槛 → 保守不升档。
1. **§9.4 末条预判修正**【诚实记录】：曾判"P0-2a 不受影响"——**收回**。ts fill=1.0 同样是 SIZE>0 口径，占位符污染机制相同；chajia/search 序列密度未测 → **P0-2a 定档前置 SQL-10**。

### 9.6 跑序终版（20261109，取代 §9.3）+ SQL-10

```
第一梯队: P0-4 曝光 rt 标量 → P0-2a（SQL-10 已过，见 §9.7；边界待 SQL-11 定标）→ P0-3 overlap 10 条 → P0-2b time_gate
第二梯队: P1-1…P1-6 不变 + P0-1b 末位（试探档 1 run）
弃（终审）: P0-1a like_100_seq 接入
```

**SQL-10（下一条；判读图先于结果预注册）**：

```sql
-- SQL-10: chajia/search_click 序列真实密度 + ts 数值形态（P0-2a 定档前置）
-- 分区口径修正（20261109）：必须带 dt 分区过滤
SELECT
  COUNT(1) AS samples,
  -- ① chajia_click_100_seq 真实密度（占位符感知，集合与 SQL-9 一致）
  AVG(IF(SIZE(chajia_click_100_seq__item_id) = 1
         AND chajia_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS chajia_ph_rate,
  AVG(IF(NOT (SIZE(chajia_click_100_seq__item_id) = 1
         AND chajia_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan')), 1, 0)) AS chajia_real_fill,
  AVG(SIZE(chajia_click_100_seq__item_id)) AS chajia_avg_len_raw,
  -- ② search_click_100_seq 同构
  AVG(IF(SIZE(search_click_100_seq__item_id) = 1
         AND search_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), 1, 0)) AS search_ph_rate,
  AVG(IF(NOT (SIZE(search_click_100_seq__item_id) = 1
         AND search_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan')), 1, 0)) AS search_real_fill,
  AVG(SIZE(search_click_100_seq__item_id)) AS search_avg_len_raw,
  -- ③ ts 数值形态（尺度锚 = click_50；语义应为近因秒数差 ~1e2~1e6）
  AVG(IF(NOT (SIZE(click_50_seq__item_id) = 1
         AND click_50_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan')), click_50_seq__ts[0], NULL)) AS click50_ts0_real_mean,
  AVG(IF(NOT (SIZE(chajia_click_100_seq__item_id) = 1
         AND chajia_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan')), chajia_click_100_seq__ts[0], NULL)) AS chajia_ts0_real_mean,
  AVG(IF(SIZE(chajia_click_100_seq__item_id) = 1
         AND chajia_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'), chajia_click_100_seq__ts[0], NULL)) AS chajia_ts0_ph_mean,
  AVG(IF(NOT (SIZE(search_click_100_seq__item_id) = 1
         AND search_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan')), search_click_100_seq__ts[0], NULL)) AS search_ts0_real_mean
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261106';
```

**判读图（预注册）**：

- chajia_real_fill **与** search_real_fill 均 ≥ 20% 且 ts_real_mean 与 click50_ts0_real_mean 同尺度（O(1e2~1e6) 秒）→ **P0-2a 回第一梯队**（P0-4 之后）；
- 任一真实填充 5~20% → P0-2a 降二梯队；或 ts 尺度不一致（~1e9 = 裸 unix 时间戳）→ ts 语义需 FG 先转换，P0-2a 转 FG 需求单；
- 任一真实填充 < 5% → **P0-2a 弃**；
- `*_ts0_ph_mean ≈ 0` → 占位形态确认，仅记录不改判。

### 9.7 SQL-8/9/10 重跑（dt='20261030'，12 跑同窗）→ P0-2a 回第一梯队 + 边界定标修订（20261109）

**分区终版**【用户修正】：`WHERE dt='20261030'`（90,988,963 行）——与 12 跑训练/评估同窗，判决以此为准。dt='20261106' 窗（99,528,307 行）数字仅作旁证：两窗结论逐项一致（like 占位 94.1% vs 93.9%、sconv 占位 50.6% vs 49.3%、click50 均长 40.22 vs 40.28）→ **占位符问题是 FG 结构性的，不随日期漂移**【事实读数】。

**重跑关键数字**【原始证据】：

| 项                              | dt='20261030'                             | 判决影响                   |
| ------------------------------- | ----------------------------------------- | -------------------------- |
| like100 真实填充（1 − len1_ph） | **5.86%**（ph 94.14%，真单条 4.58%）      | P0-1a 弃（终审）不变       |
| sconv20 真实填充                | **49.4%**（ph 50.56%，真单条 18.66%）     | P0-1b 二梯队末位不变       |
| **chajia_real_fill**            | **44.90%**（ph 55.10%，avg_len_raw 3.37） | ≥20% ✓                     |
| **search_real_fill**            | **76.68%**（ph 23.32%，avg_len_raw 7.61） | ≥20% ✓                     |
| click50_ts0_real_mean           | **55,059 s ≈ 15h**（尺度锚）              | —                          |
| chajia_ts0_real_mean            | **625,223 s ≈ 7.2d**                      | O(1e5~1e6) 秒 ✓ 非裸 unix  |
| search_ts0_real_mean            | **547,910 s ≈ 6.3d**                      | 同上 ✓                     |
| chajia_ts0_ph_mean              | **0.0**                                   | 占位形态确认，仅记录不改判 |

**SQL-10 判决（对照 §9.6 预注册图）**【事实读数→判决】：双真实填充均 ≥20% 且 ts 尺度与 click50 同为秒级（~1e5，非 ~1e9 裸 unix）→ **P0-2a 回第一梯队**（P0-4 之后）。ts 语义 = 近因秒数差确认，无需 FG 转换。

**新发现：ts 近因分布偏老 ~10× → 借位边界压缩风险**【事实读数】：chajia/search 的真实 ts 均值（6.25e5/5.48e5 秒）比 click_50（5.5e4）老一个数量级；click_50 供借位的 19 边界（647~694,233 秒）是按 click_50 自身分布定标的，chajia/search 的质量将压进顶部 2~3 桶。**先例**【事实读数】：click_10 与 click_50 的 ts 边界本就各自定标（282~610,396 vs 647~694,233）——"同族借位"不是惯例，per-seq 分位数定标才是。

- **后果**【推断】：借位直接跑存在 P0-2a **假阴性**风险（分辨率压扁 → 过不了 +0.10pp 闸 → 误弃好臂）。
- **变更单修订**：P0-2a 的 ts 边界由"借位 click_50"改为 **按各自序列 ts 分位数定标**（19 cuts / 20 buckets / emb=8 形态不变），定标数据 = SQL-11。
- **两个选项**：**A（推荐）** SQL-11 先定标再生成 P0-2a config（+1 SQL，防假阴性；P0-4/P0-3/P0-2b 不受影响可先行）；**B** 借位直接跑（快，但过不了闸也**不得直接弃**，需定标重跑后复判）。

**SQL-11（下一条；用途 = P0-2a 边界定标）**：

```sql
-- SQL-11: chajia/search_click ts 全元素分位数（P0-2a 边界定标，19 cuts/20 buckets）
-- 口径：真实行（剔占位符行，集合与 SQL-9 一致）、数组全元素（边界作用于每个元素）；分区 dt='20261030'
SELECT
  seq,
  COUNT(1) AS ts_elems,
  PERCENTILE_APPROX(ts_val, ARRAY(0.05,0.10,0.15,0.20,0.25,0.30,0.35,0.40,0.45,0.50,
                                 0.55,0.60,0.65,0.70,0.75,0.80,0.85,0.90,0.95)) AS pcts
FROM (
  SELECT 'chajia' AS seq, ts_val
  FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
  LATERAL VIEW EXPLODE(chajia_click_100_seq__ts) t AS ts_val
  WHERE dt = '20261030'
    AND NOT (SIZE(chajia_click_100_seq__item_id) = 1
             AND chajia_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'))
  UNION ALL
  SELECT 'search' AS seq, ts_val
  FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
  LATERAL VIEW EXPLODE(search_click_100_seq__ts) t AS ts_val
  WHERE dt = '20261030'
    AND NOT (SIZE(search_click_100_seq__item_id) = 1
             AND search_click_100_seq__item_id[0] IN ('', '0', '-1', 'null', 'NULL', 'None', 'nan'))
) x
GROUP BY seq;
```

注：① 若 ODPS 不支持 `PERCENTILE_APPROX` 的 array 形式，拆成 19 个单值调用或先跑 5 点版（0.1/0.25/0.5/0.75/0.9）重跑本条；② 全量太重可加 `AND rand() < 0.1` 抽样，分位数不受影响；③ 拿到 19 个分位点后直接落成 P0-2a 的两组 boundaries（小数取整），无需再跑 SQL。

**跑序（§9.6 括号项已解）**：P0-4 → P0-2a（SQL-11 定标后）→ P0-3 → P0-2b；P0-4/P0-3/P0-2b 的 config 生成不依赖 SQL-11，可先行。

### 9.8 SQL-11 结果与 P0-2a 边界定标终版（20261109，`WHERE dt='20261030'`）

**SQL-11 原始结果**【原始证据】：

| seq    | ts_elems    | pcts（p05→p95，19 点，秒）                                                                                                                                                                                   |
| ------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| search | 671,422,069 | 54,590 / 125,557 / 208,428 / 301,394 / 402,057 / 507,893 / 610,319 / 730,190 / 859,232 / 991,662 / 1,130,367 / 1,285,071 / 1,439,533 / 1,599,994 / 1,765,047 / 1,933,046 / 2,106,226 / 2,281,807 / 2,456,786 |
| chajia | 256,268,229 | 48,968 / 120,576 / 204,235 / 298,299 / 399,966 / 505,534 / 606,514 / 719,191 / 846,796 / 971,512 / 1,116,071 / 1,254,909 / 1,403,060 / 1,562,632 / 1,729,027 / 1,899,153 / 2,075,925 / 2,258,037 / 2,442,498 |

（表内已取整；原始浮点见用户回贴，取整规则 = round-half-up 到整数秒，对齐 config `boundaries: <float>.0` 形态。）

**读数**【事实读数】：

1. ODPS `PERCENTILE_APPROX` 的 array 形式直接可用——§9.7 注①的拆跑回退未触发。
1. **元素数交叉验证逐位自洽**：search 671M ≈ 91M×(7.612−0.233)≈672M、chajia 256M ≈ 91M×(3.367−0.551)≈257M——与 SQL-10 的 avg_len_raw/占位率同口径闭合，EXPLODE 无漏无重。
1. **分布形态**：两序列几乎重合（同分位点差 ≤15%，chajia 略老）；p5≈0.57~0.63d、p50≈11.2~11.5d、p95≈28.3d——60d 窗内长尾。5% 步进 19 cuts → 20 桶各含 ~5% 元素，**分辨率充足**，§9.7 的"借位压扁假阴性"风险正式解除。
1. 尺度 O(1e4~1e6) 秒复确认，非裸 unix。
1. 副发现【推断】：ts[0] 均值（6.25e5/5.48e5）低于全元素中位数（~9.7e5/9.9e5）→ 序列按近因**倒序**排（首位偏新）。不影响边界（边界作用于全元素），仅记录。

**边界定标终版（P0-2a 直接可用，19 cuts/20 buckets/emb=8）**【事实读数→产出】：

```
chajia_click_100_seq__ts:
  boundaries: 48968.0 / 120576.0 / 204235.0 / 298299.0 / 399966.0 / 505534.0 / 606514.0 / 719191.0 / 846796.0 / 971512.0 / 1116071.0 / 1254909.0 / 1403060.0 / 1562632.0 / 1729027.0 / 1899153.0 / 2075925.0 / 2258037.0 / 2442498.0
search_click_100_seq__ts:
  boundaries: 54590.0 / 125557.0 / 208428.0 / 301394.0 / 402057.0 / 507893.0 / 610319.0 / 730190.0 / 859232.0 / 991662.0 / 1130367.0 / 1285071.0 / 1439533.0 / 1599994.0 / 1765047.0 / 1933046.0 / 2106226.0 / 2281807.0 / 2456786.0
```

**P0-2a 变更单终版（行号级，kv_fusion.config 基线行号）**：

1. **块内插入**（形态照 click_50 ts 子块 L10240–10263：`features { raw_feature { feature_name: "ts" / expression: "user:ts" / embedding_dim: 8 / boundaries: … } }`）：
   - `chajia_click_100_seq` 块（L10632 起）：插在 L10787（username 子块收尾 `    }`）与 L10788（`  }` 收 sequence_feature）之间，boundaries 用 chajia 组 19 值；
   - `search_click_100_seq` 块（L10792 起）：插在 L10947 与 L10948 之间，boundaries 用 search 组 19 值。
1. **组引用**（形态照 click_50 组 L18486：**ts 只挂全名、不成对**——与 id 子特征"短名+全名"成对写法不同，勿照抄成对）：
   - chajia 组（L18567 起）：L18605 之后插 `feature_names: "chajia_click_100_seq__ts"`（1 行）；
   - search 组（L18608 起）：L18646 之后插 `feature_names: "search_click_100_seq__ts"`（1 行）。
1. 维度账不变：两序列 din 输出各 216→224（ts emb=8 追加）。
1. 数据面：编码表 `chajia_click_100_seq__ts ARRAY<FLOAT>` / `search_click_100_seq__ts ARRAY<FLOAT>`（DDL 已核实在，SQL-10/11 实测有货）。

|                                                                                                                                                                                                                                                                                                                                            |     |     |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --- | --- |
| **命名勘误（收回本次一处误读）**【勘误】：会话中途据 `grep -c "offline_chajia\|offline_search"` 得"编码表 0 个 offline\_ 列"——**假读数**（macOS BSD grep 的 `\|` 不当交替用）。重查：编码表实有 **68 个 offline\_ 列**（offline_chajia 17，含 `offline_chajia_brand_common_ratio FLOAT` 等）。真实结构 = 双家族并存，**不改 P0-2a 目标**： |     |     |

- `chajia_click_100_seq` / `search_click_100_seq`（sequence_feature，L10632/L10792）= DIN 对齐序列族，消费编码表裸名 ARRAY 列 → **P0-2a 目标**；
- `offline_chajia_click_100_seq__*` / `offline_search_click_100_seq__*`（扁平 id_feature，`separator: ";"` + `pooling: "mean"`，L11413 起）= 池化辅助族，不在 P0-2a 范围；
  | | |
  | \--- | --- |
- 后续 DDL 核查纪律追加：`grep -a` 强制文本模式 + 单模式匹配（不用 `\|` 交替，不用 rg 查中文 md）。

**SQL 链收档**：SQL-8~11 完成 P0 全部数据面前置（P0-4/P0-3 列已核实在、P0-2b 纯 config）→ **无 SQL-12**（纪律：有必要才给）。第一梯队 4 个 config（P0-4 → P0-2a → P0-3 → P0-2b）全部解锁，等用户"确认生成"。

### 9.9 第一梯队生成记录（20261109，用户"确认生成"）

4 个 config 已生成并全量验证（明细见 `GEN_P0_FIRST_BATCH_20261109.md`，脚本 `gen_p0_first_batch_20261109.py`）：
`..._v6f_p04_exposurert5` / `..._v6f_p02a_seqts` / `..._v6f_p03_overlap10` / `..._v6f_p02b_timegate4`。
验证：diff 纯新增 4/4、EasyRecConfig 冒烟 5/5、P0-2a 边界逐值 = §9.8 2/2、time_gate_dim==ts emb 4/4。

**变更单修正 2 处**【事实读数→修正】：① favorite_10 的 ts emb=**4**（非 8）→ 其 `time_gate_dim=4`（8/8/8/4），否则门控误卷 username 尾 4 维（bug 级）；② T3 "224→216"账只对 ts=8 序列成立，favorite_10 实为 **220→212**（下游动态适配不受影响）。另 2 处决策已记录：P0-4 num 边界借位 click_15d 价格 cuts；grad_clipping 搭车选 P0-2b。

**状态**：4 config 已训练完毕（20261109 样本集同窗配对，单 seed）——读数与判决见 `READOUT_20261111_P0_FIRST_BATCH.md`：**P0-2a +0.240pp 续投（进 3-seed 符号闸）**、P0-4 +0.081pp 判据灰区、P0-3 弃、P0-2b 弃（time_gate 族两窗收档）。

### 9.10 SQL-12 结果与 P1-6 判决（20261111，`WHERE dt='20261030'`，90,988,963 行）

**SQL-12 原始结果**【原始证据】（convert_probability × is_conversion 分桶校准表）：

| bucket      | samples              | actual_cvr | actual_ctr | avg_cp      |
| ----------- | -------------------- | ---------- | ---------- | ----------- |
| a_cp_zero   | 36,412,115（40.02%） | 0.1481     | 0.3804     | 0.0         |
| b_cp_00_10  | 1,084（0.00%）       | 0.0175     | 0.4225     | 0.0663      |
| c_cp_10_30  | 4,907（0.01%）       | 0.0695     | 0.3962     | 0.1945      |
| d_cp_30_50  | 11,296（0.01%）      | 0.0524     | 0.3668     | 0.4196      |
| e_cp_50_70  | 13,312（0.01%）      | 0.0614     | 0.3518     | 0.5880      |
| f_cp_70_90  | 37,712（0.04%）      | 0.0521     | 0.3411     | 0.8231      |
| g_cp_90_100 | 54,508,537（59.91%） | 0.1016     | 0.3568     | **52.9273** |

**读数**【事实读数】：

1. 计数闭合：90,988,963 与 SQL-8/9 同窗逐位一致；加权 actual_cvr = 0.1202 ≈ eval mean_target 0.1204。
1. **avg_cp = 52.9 @ g 桶 → 该字段不是 0~1 概率**（值域无上界，命名与语义不符）；分布三峰：40.02% 零（default）、0.075% 落 (0,0.9\]、59.91% 落 (0.9,∞)。
1. **校准极差且粗粒度反相关**：cp=0 桶 cvr 0.1481 > 总体 0.1202 > cp>0.9 桶 0.1016；中段桶（样本极少）actual_cvr 0.02~0.07 无单调。

**对照预注册判读图**：泄漏分支（近完美校准）**未命中**——无任何桶接近"预测≈实际"，标签泄漏嫌疑排除【事实读数】；"正常先验形态"分支**未命中**（无单调斜率，零桶反而最高）；"平坦无信息"分支**部分命中**。判读图三分支都没覆盖"值域无界"情形——按保守方向裁决：

**P1-6 判决：as-is 暂停，不进 config**【事实读数→判决】。风险性质从"泄漏"改判为"**语义不明**"（好消息是没有泄漏，坏消息是字段不能当概率用）。两个待分辨假说：

- **H_scale（百分制）**【推断】：若真实值域 0~100，则 g 桶 (0.9,∞) 实际是 [1,100+] 的大杂烩，均值 52.9 与"1~100 近均匀"吻合——概率单位是百分数；
- **H_score（无界打分/计数）**【推断】：上游模型 raw score 或转化计数，语义需 FG 问询。

### 9.11 SQL-13（下一条，定标判别；判读图先于结果预注册）

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

**判读图（预注册）**：

- 质量集中在 b~i（0~100）且 j+k 合计 < 1% → **H_scale 百分制确认**：再看重分桶后 actual_cvr 是否随 avg_cp 单调——单调（哪怕校准差）→ P1-6 重启（分桶 raw_feature，boundaries 1/5/10/20/40/60/80/100，只作序信号不作概率）；仍无序 → **P1-6 终弃**；
- j+k 合计 ≥ 5% → **H_score 确认**：无界打分/计数 → 转 FG 口径问询（生成公式/单位/时间窗），P1-6 as-is **终弃**；
- 任一情形：泄漏已被 SQL-12 排除，本条只判"可用性"不重开泄漏审。

### 9.12 SQL-13 结果与 P1-6r 判决（20261111 晚，`WHERE dt='20261030'`，90,988,963 行逐位闭合）

**SQL-13 原始结果**【原始证据】（重分桶定标表，j/k 桶 0 行未出现在结果中）：

| bucket                 | samples              | actual_cvr | avg_cp |
| ---------------------- | -------------------- | ---------- | ------ |
| a_zero                 | 36,412,115（40.02%） | **0.1481** | 0.0    |
| b_00_01                | 93,936（0.10%）      | 0.0581     | 0.740  |
| c_01_05                | 1,430,827（1.57%）   | 0.0744     | 3.323  |
| d_05_10                | 2,289,328（2.52%）   | 0.0807     | 7.410  |
| e_10_20                | 3,346,593（3.68%）   | 0.0831     | 14.669 |
| f_20_40                | 10,094,357（11.09%） | 0.0884     | 29.841 |
| g_40_60                | 14,102,001（15.50%） | 0.0960     | 50.068 |
| h_60_80                | 13,530,096（14.87%） | 0.1105     | 71.133 |
| i_80_100               | 9,689,710（10.65%）  | 0.1266     | 87.147 |
| j_100_1000 / k_gt_1000 | **0（未出现）**      | —          | —      |

**读数**【事实读数】：

1. **计数闭合**：9 桶合计 90,988,963 = SQL-12 同窗逐位一致；加权 actual_cvr = 0.1202 ≈ eval mean_target 0.1204。
1. **j+k = 0 行（0% < 1%）→ 命中 H_scale 分支**：值域 0~100 收敛（i 桶 avg_cp 87.1 落在 80~100 内，全桶 avg_cp 与切点自洽）→ **H_scale 百分制确认**，H_score（无界打分）排除。
1. **重分桶后非零段严格单调**：b→i actual_cvr 0.0581 → 0.0744 → 0.0807 → 0.0831 → 0.0884 → 0.0960 → 0.1105 → 0.1266（8/8 步升）→ 命中预注册"单调（哪怕校准差）→ P1-6 重启"分支。
1. **零桶反转（须独立处理）**：a_zero（cp=0，40.02% 质量）actual_cvr 0.1481 为全表最高——cp=0 是 default/missing 语义（SQL-12 已证 40% 默认填充），非"最低转化"打分；含零桶整体不单调。
1. **校准差确认"只作序信号"**：按百分制 /100 当概率读，高分段高估 ~7x（i 桶 0.87 vs 0.13）——预注册"只作序信号不作概率"口径成立，不得当校准概率用。

**对照预注册判读图（PLAN §9.11）**：

- "质量集中在 b~i 且 j+k < 1%" → **命中**（H_scale 百分制确认）；
- "actual_cvr 随 avg_cp 单调" → **非零段命中**（b→i 8/8 步升）。单调性检验的对象是打分序（有分人群），零桶是无分 default，不参与序检验，以 1e-08 首切独立成桶处置（与预注册 boundaries 1/5/10/20/40/60/80/100 + 房规零桶切分一致）；
- 泄漏审不重开（SQL-12 已排除）。

**P1-6r 判决：重启，只作序信号**【事实读数→判决】。形式按预注册：分桶 raw_feature，boundaries **1e-08/1/5/10/20/40/60/80/100**（8 预注册切点 + 1e-08 零桶切，同 current_price 房规），emb=8，10 buckets，入 all 组，单臂单变量。FG 口径问询降级为 P2 备注（语义已定标，不阻塞）。

**P1-6r 变更单（已执行）**：新文件 `home_flow_2608_v19_multiscene_v6f_p02a_p16cpbucket.config` = `v6f_p02a_seqts.config`（P0-2a 过闸新基线）+ 1 条：

1. feature_configs（L307-322，current_price 块后）：`raw_feature{feature_name: "convert_probability" / expression: "item:convert_probability" / embedding_dim: 8 / boundaries 9 切}`；
1. all 组 feature_names（L17418）：`convert_probability`（current_price 后）。

**生成验证**（2026-11-11）：diff 纯新增 25+/0−；proto 冒烟 PASS（EasyRecConfig 解析；boundaries 9 切/10 桶逐位核对；feature_configs 1103→1104 仅 +convert_probability；all 组 +1 其余组零变化；除上述外 proto 级逐位一致，含 6 条 din_encoder 与 time_gate_dim=0）。判据照共同规格：Δctr ≥ +0.10pp 续投 / |Δ| ≤ 0.05pp 弃。

**语义更正（20261111 23:15，用户域知识输入，优先于推断）**：convert_probability = **真实"预估出单概率"百分制打分（0 = 预估出单概率为 0，上限 100）**，不是缺省填充值——本文上文"default/missing 语义"的措辞**撤销**（此前把 40% 精确 0 推断为默认填充，是推断不是证据；SQL-12/13 只证了 40.02% 精确 0 与值域 0~100）。更正后的重新论证：

1. **0 独立成桶依然成立**（结构不变）：0 桶 actual_cvr 0.1481 vs (0,1\] 桶 0.0581 断崖 2.55×；若按序值口径把 0 并入最低桶（boundaries 从 1 起），混合桶 cvr 0.1478 被 0 桶 99.74% 质量淹没，(0,1\] 段分辨率全毁。分桶 embedding 每桶独立学习、不带序假设，"0 分段反而高转化"的反转是**可学的**；反之连续序值编码（raw/log1p）会被 0 点反转的错误梯度挤压。1e-08 首切保证 0 精确落桶 0、(0,1\] 落桶 1。
1. **零点反转改判为上游打分质量问题（待勘验）**：真实 0 分人群实际 cvr 全表最高（0.148）——两个假说：① 上游打分零点系统性低估/打分口径（出单定义或时间窗）与 is_conversion label 窗不一致；② 0 分段是特殊流量（冷启动新品/运营强曝类目，如活动贴），高转化由流量性质驱动。这决定 P1-6r 学到的是稳健序信号还是"0 桶=高转化"人群规则（对分布漂移敏感）；判据不动，读数见真章。可选 SQL-14 勘验 0 桶人群构成。
1. **缺省填充规则（FG 需求单备注，P3）**：0 已被赋予真实语义——若线上/FG 对**缺字段**默认填 0，会与真实 0 分混淆，不合理；建议缺省用越界哨兵（如 −1）。样本侧无此问题（SQL-13 的 k_gt_1000 ELSE 桶 = 0 行 → 无 NULL 落入，全部行有真实值）。
1. **预注册纪律备注（判读图盲区，透明化）**：判读图"单调→重启/仍无序→终弃"未预见"0 是真实打分且零点反转"情形。严格字面读法（0 计入序检验）全尺度非单调→走终弃分支；本裁决走"打分段 (0,100\] 8/8 步升 + 0 桶分桶可学"的解释路径，保留 P1-6r（臂的生死由预注册读数判据决定，不由此解释决定）。此为盲区解释性裁决，判据与门槛零变动。

**SQL-14 勘验（20261111 23:45，零点反转构成分解；dt='20261030'）**：

| bucket | item_type     | samples                   | actual_cvr           |
| ------ | ------------- | ------------------------- | -------------------- |
| a_zero | [0] 单品      | 28,438,639（零桶 78.1%）  | 0.1315               |
| a_zero | [1] 促销活动  | 7,702,787（21.2%）        | 0.2086               |
| a_zero | [7] 文章/公告 | 106,906（0.29%）          | 0.0000187（≈2 转化） |
| a_zero | [9] 优惠福利  | 163,783（0.45%）          | 0.2756               |
| b_pos  | [0] 单品      | 54,576,848（= 全部 cp>0） | 0.1016               |

**闭合**【原始证据】：a_zero 36,412,115 / b_pos 54,576,848 / 总 90,988,963，三口径与 SQL-13 逐位一致；b_pos 仅 1 行 → **cp>0 的样本 100% 是单品**。item_type [8] 多品本窗 0 行。

**读数**【事实读数】：

1. **构成效应证实（假说②）**：非单品（促销/文章/福利 7.97M，零桶 21.9%）**结构性恒 0**——上游只对单品打"出单概率"，非单品的 0 是 **N/A 不打分**，不是"预估 0 分"；促销 cvr 0.209 / 福利 0.275 结构性拉高零桶（文章 cvr≈0，label 语义自洽）。语义三拆定谳：**单品 0 = 真实 0 分；非单品 0 = 结构性 N/A**。
1. **残余反转仍在（假说①仍活）**：单品内部 cp=0 cvr 0.1315 > cp>0 cvr 0.1016（1.30×），且 0.1315 > i_80_100 最高分桶 0.1266——构成效应把全口径 2.55× 断崖解释到 1.30×，**不是全部**；单品零分段系统性高转化（冷启动/打分口径窗不一致待上游排查，或 SQL-15 用 item 历史深度检验冷启动假说）。

**判决**：

- **P1-6r 结构不变**：0 独立成桶 + item_type 已在 all 组（DCNv2 交叉可消歧"单品真实 0 分 vs 非单品 N/A"）；(0,1\] 最低 cvr 0.058 与 0 桶断崖被两个独立桶分开——连续编码会毁掉这个区域，分桶是对的。判据不动，读数见真章。
- **FG 需求单备注升级（P3）**：非单品结构性 N/A 填 0 实锤——建议上游对非单品输出缺省哨兵（−1）与单品真实 0 分分离；单品零分段高转化问题一并反馈（附 SQL-13/14 读数）。
- 可选 SQL-15（单品冷启动假说，一条，item 历史深度代理）：

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

（若 `item_type` 是字符串列用 `item_type = '[0]'`；`item__cnt_click_rt24h` 若列名不符贴 DDL 我改写。零分段 no_hist_rate/历史深度显著更浅 → 冷启动解释残余反转。）

**SQL-15 勘验（20261111 23:57，单品冷启动假说；dt='20261030'，item_type[0]=0）**：

| bucket | samples    | avg_item_click_24h | no_hist_rate | actual_cvr |
| ------ | ---------- | ------------------ | ------------ | ---------- |
| a_zero | 28,438,639 | 136.66             | 2.90%        | 0.1315     |
| b_pos  | 54,576,848 | 301.14             | 0.25%        | 0.1016     |

**闭合**【原始证据】：28,438,639 + 54,576,848 = 83,015,487，与 SQL-14 单品两侧逐位一致。

**读数**【事实读数】：

1. **广义冷启动/浅历史倾斜方向成立**：零分段 avg_item_click_24h 136.7 = 有分段的 45%；no_hist_rate 2.90% vs 0.25%（11.7×）——零分段商品显著更浅历史。
1. **窄义冷启动（无历史新品）被算术排除为完整解释**：零分段 97.1% 有历史；即使无历史子集 cvr=100%、其余 97.1% 取 pos 桶 0.1016，零分段均值上限 0.1276 < 实测 0.1315——反转必然存在于**有历史人群内部**。合理情形下无历史子集占比更低（cvr=0.3 时仅解释 gap 的 ~19%）。
1. **剩余解释空间二选一（或并存）**：① 历史深度梯度——浅历史单品转化更高、上游打分随历史深度上升（校准随热度反向）；② 真零点反转——同深度层内 cp=0 仍更高（打分口径/label 窗不一致）。判别 = SQL-16 按历史深度分层看 cp 零点差（见下）。

**判决**：

- P1-6r 结构与判据**不动**（分桶 embedding 可学任意构成模式）；零点反转对 P1-6r 的影响限于收益形态解读（"0 桶=高转化"规则部分是构成性的，对漂移敏感）。
- **FG 反馈稿定稿（P3）**：① 非单品 N/A 建议 −1 哨兵（SQL-14）；② 单品打分对浅历史人群欠分——零分段历史深度仅为有分段 45%、无历史率 11.7×，但其实际转化反而高 30%（SQL-15），建议上游核查打分是否随历史热度过拟合、出单口径/窗与 label 窗是否一致。
- 债务更新：零点反转 = 非单品 N/A 构成（已解释 2.55×→1.30×）+ 浅历史倾斜（方向证实、份额待定）+ 残余（窄义冷启动排除，SQL-16 分层判别）。
- 可选 SQL-16（深度分层判别 ① vs ②，一条）：

```sql
SELECT
  CASE WHEN convert_probability <= 0 THEN 'a_zero' ELSE 'b_pos' END AS bucket,
  CASE
    WHEN item__cnt_click_rt24h <= 0 THEN 'h0_none'
    WHEN item__cnt_click_rt24h < 50 THEN 'h1_lt50'
    WHEN item__cnt_click_rt24h < 200 THEN 'h2_50_200'
    WHEN item__cnt_click_rt24h < 1000 THEN 'h3_200_1000'
    ELSE 'h4_ge1000'
  END AS hist_band,
  COUNT(1) AS samples,
  AVG(is_conversion) AS actual_cvr
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5
WHERE dt = '20261030' AND item_type[0] = 0
GROUP BY bucket, hist_band
ORDER BY bucket, hist_band;
```

（同深度层内 a_zero vs b_pos 差距消失 → ①构成解释收口；仍在 → ②真零点反转坐实，FG 反馈升级为"打分口径 bug 级"。）

**源头口径补勘（20261112 11:03，用户质询触发）**：勘验口径分工与一个新实锤——

- 转化链路：`feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set`（源头）→ pyfg101 + `home_flow_2608_ctrcvr_sorter_config_fg_v5.json`（1186 特征）→ 编码表 → 打散 60d 窗（`..._pyfg_encoded_v5.py`，17 行驱动）。
- **fg_v5.json 实锤**：`convert_probability` 的 `default_value = "0"`（1186 特征中 998 个 default=0，204 个 lookup 序列特征 default 全 0）→ **编码表的 0 = 真实 0 分 ∪ 缺省填充，编码表上不可分辨**；SQL-13"无 NULL"只证编码后无 NULL，证不了源头无缺失。
- 口径纪律固化：**"模型所见"类（占位符污染/边界定标/同窗 Δ 配对）锁编码表；"源头语义/质量"类（convert_probability 0 三拆之缺省填充项）必须回源头表**。SQL-12~15 的 0 语义链缺源头半边，自此补勘。
- **SQL-16R（源头零值语义，一条，判读图预注册）**：

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

判读图：null≈0 且 zero 率≈40% → 真实 0 语义源头坐实（SQL-13~15 解读维持，FG 备注降级）；null 显著 → 缺省填充实锤（单品零桶重拆真实 0/缺失填充，SQL-15 归因重算，FG −1 哨兵从建议变必须）；源头 vs 编码 zero 率差 = 填充量直接估计。（分区/列名不符贴 DDL 改写；比率不比绝对量。）原 SQL-16（hist_band 分层）顺延为 SQL-17，且若零桶混填充须在"真实 0"子集上重跑。

**SQL-16R 结果与判决（20261112 11:12，源头表 `feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set`，dt='20261030' 单日 2,691,204 行）**：

| samples   | null_cnt                | zero_cnt | pos_0_100 | gt_100 | min_cp  | max_cp |
| --------- | ----------------------- | -------- | --------- | ------ | ------- | ------ |
| 2,691,204 | **1,180,823（43.88%）** | **0**    | 1,510,381 | 0      | **1.1** | 99.59  |

**闭合**【原始证据】：1,180,823+0+1,510,381+0 = 2,691,204 ✓。

**读数**【事实读数】：

1. **命中预注册"缺省填充实锤"分支，且比预期更强**：null 率 43.88%（阈值 1~2%）；**真实 0 分 = 0 行**，有分值域 [1.1, 99.59]——**源头根本不存在 0 分**，编码表 0 桶 100% = NULL→FG default_value=0 填充。此前"单品 0 = 真实 0 分"的语义三拆**撤销**，0 桶实为"单品缺分 + 非单品 N/A"二拆。
1. **率级对账**：源头 NULL 43.88%（单日）≈ 编码零桶 40.02%（60d 窗）——窗口差异可解释，填充路径坐实。
1. **"零点反转"终局改判**：0 桶高 cvr（单品 0.1315 > 有分 0.1016）不是打分器 0 点低估，是**缺分人群高转化**（浅历史 45%、无历史率 11.7×，SQL-15）——打分器在**有分段**序信息有效（SQL-13 b→i 严格单调 0.058→0.127），质量问题定位从"打分器"移至"覆盖/缺分"。
1. **NULL 语义二分（源头不可分辨，FG 问询项）**：(a) 未打分/覆盖不足（旁证：浅历史画像 + 低分真值通路存在——(0,1\] 桶 avg 0.74，若打 ~0 分应输出小正值而非 NULL）；(b) 打分为 0→上游输出 NULL（则"0 分人群 cvr 13%"是打分器底端反转，质量问题升级）。【推断】(a) 概率大，待上游确认。
1. **小尾巴**：编码窗 (0,1\] 桶 93,936 行（avg 0.74）证明其他日子存在 \<1 真实分值 → 本日 min=1.1 不外推全窗；若他日存在真实 0 分，将与填充值碰撞（现无法分辨）→ −1 哨兵仍必要。

**判决**：

- **P1-6r 结构/判据不动**，0 桶语义注释改定为"**0 = 源头 NULL 填充（缺分/未打分）**"——对分桶 embedding 反而是可学信号（缺分=高转化人群规则，注意漂移敏感）；boundaries 1e-08 首切对 −1 哨兵前向兼容（−1 同落桶 0）。
- **FG 需求单（P3）措辞定稿**：① 非单品 N/A 与缺分共用填充值 0 → **−1 越界哨兵从建议升级为必须**（判读图分支命中）；② 上游问询 NULL 语义（未打分 vs 打分为 0，附 min_cp=1.1/zero_cnt=0 证据）；③ 缺分人群（43.9%）高转化反馈（附 SQL-14/15/16R 读数）。
- **SQL-17 修订（判别 NULL 语义 (a) vs (b)，一条）**：比较 NULL 桶与低分桶（0\<cp≤5）的历史深度画像——

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

判读图：NULL 桶历史画像**显著浅于**低分桶 → (a) 未打分/覆盖不足坐实（FG 反馈走覆盖路线）；两桶画像**同形** → (b) 打分为 0 坐实（打分器底端反转，质量问题升级为 bug 级）。（列名/类型不符贴 DDL 改写；item_type 类型待确认，若是字符串用 `item_type = '[0]'`。）

**SQL-17 结果与判决（20261112 11:36，源头表 dt='20261030'，item_type=0，NULL 语义判别）**：

| cp_band       | samples   | avg_item_click_24h | no_hist_rate | actual_cvr |
| ------------- | --------- | ------------------ | ------------ | ---------- |
| a_null        | 980,174   | **158.38**         | **2.69%**    | **0.1450** |
| b_low_0_5     | 69,382    | 402.95             | 0.44%        | 0.0681     |
| c_mid_5_20    | 310,434   | 433.86             | 0.26%        | 0.0819     |
| d_high_20_100 | 1,130,565 | 376.48             | 0.17%        | 0.1017     |

**闭合与互证**【原始证据】：单品 4 桶合计 2,490,555；非单品 = 2,691,204 − 2,490,555 = 200,649 = 1,180,823 − 980,174（非单品 NULL 数）——**全部非单品都是 NULL**，与 SQL-14"cp>0 100% 单品"逐位互证，链路闭合。

**读数**【事实读数】：

1. **命中预注册"(a) 未打分/覆盖不足"分支**：NULL 桶 vs 低分桶(0,5\] 历史画像显著不同形——avg_item_click_24h 158.4 vs 402.9（仅 39%）、no_hist_rate 2.69% vs 0.44%（6.2×）、cvr 0.1450 vs 0.0681（2.13×）。
1. **假说 (b) 强烈拒绝**：若 NULL=打分为 0→NULL，NULL 桶应近似最低真分桶 b_low（0\<cp≤5）；实际深度差 2.5×、cvr 差 2.13×、无历史率差 6.2×——不是同一人群，打分器底端反转 bug 假说**排除**。
1. **有分段自检通过**：b→c→d actual_cvr 0.0681 → 0.0819 → 0.1017 严格单调（与 SQL-13 b→i 单调一致），历史深度大致平（403/434/376）——打分器在覆盖人群内序信息有效、无深度倾斜。
1. **归因链终局**：零点反转 = **缺分/未打分人群高转化**（单品 NULL 桶 cvr 0.1450 > 最高真分桶 0.1017，历史深度仅其 42%）——覆盖缺口人群特征（更浅历史、更高转化、更低无历史率基数），SQL-15 的浅历史倾斜与窄义冷启动排除与此完全自洽。

**判决（convert_probability 勘验链收档）**：

- NULL 语义定谳 = **(a) 未打分/覆盖不足**【事实读数】；FG 反馈走**覆盖路线**（非 bug 级）：① 非单品 N/A + 单品缺分共用填充值 0 → −1 越界哨兵**必须**（SQL-16R 分支命中）；② 上游问询已答：NULL=未打分（附 SQL-17 画像证据），建议扩大打分覆盖（尤其浅历史商品——该人群转化反而高 30%）；③ 缺分人群高转化反馈（SQL-14/15/16R/17 读数齐）。
- **P1-6r 结构/判据不动**，0 桶语义注释终稿："0 = 源头 NULL 填充（未打分/覆盖不足），缺分=高转化人群规则，注意漂移敏感"。boundaries 1e-08 首切对 −1 哨兵前向兼容。
- 勘验链 SQL-12→13→14→15→16R→17 **全部收档**：泄漏排除 → H_scale 定标 → 构成分解 → 冷启动排除 → 填充实锤 → NULL=未打分。不再追加 SQL。

**训练排期（20261111 23:51 更新）**：P0-4 哨兵已跑（p04@43 vs base@43 复用配对，Δctr = **+0.0655pp**，2/2 同号均灰区，mean +0.073pp）→ 命中预注册"正→并组合臂"分支（READOUT_20261111_P0_FIRST_BATCH.md §九）：P0-4 降级为组合臂因子，不收全闸、不宣称。run 预算 **10/10 用满**（首梯 5 + 符号闸 4 + 哨兵 1）；P1-6r 与组合臂（p02a+p04 vs p02a）各需 1 run（配对 p02a@42/43/44 已在账）→ **扩预算或排序让位等拍板**。

______________________________________________________________________

*创建：2026-11-07。证据锚：`SUMMARY_20261030_ALL_RUNS.md`（12 跑）、`SQL_EVIDENCE_CHAIN_20261103.md`（SQL-1~7）、`READOUT_20261105_JUDGE_SYNTH.md`（判决）、`UNUSED_FEATURES_FG_V5_20261105.md` §六（DDL 定谳）、`PLAN_CTR_NEXT_20261105.md`（路线图）。SQL-8~11 读数与判决见 §9.1–9.8；生成记录见 §9.9 与 `GEN_P0_FIRST_BATCH_20261109.md`。*
