# FG v5 未使用特征清单与优化建议（20261105）

**对象**：`sql/2609/home_flow_2608_ctrcvr_sorter_config_fg_v5.json`（FG 特征全集，2026-10-15 版）
**对照**：`home_flow_2608_v19_multiscene_v6f_kv_fusion.config`（v6f 基线，全场最优）
**口径**：FG 声明但 v6f config 的 input_config（`feature_name`）与 feature_groups/sequence_encoders（`feature_names`/`input`）**全部未引用**的特征 = 未使用。
**证据标注纪律**：【事实读数】= 对账/既有读数直接得出；【推断】= 机制/先验判断。全部单 seed 语境。

______________________________________________________________________

## 〇、对账口径与总量【事实读数】

| 项                              | 数量                  | 说明                                                                                                                                            |
| ------------------------------- | --------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| FG features 条目                | 1,186                 | 含 8 个序列定义块（无 feature_name）                                                                                                            |
| FG 命名特征                     | 1,178                 | raw 219 / id 93 / lookup(kv) 731 / combo 66 / overlap 20 / seq_id 48 / expr 1                                                                   |
| FG 序列定义块                   | 8                     | click_10 / click_50 / chajia_click_100 / search_click_100 / **like_100** / favorite_10 / conversion_20 / **search_conversion_20**，各 20 子字段 |
| v6f 定义（input_config）        | 1,098                 |                                                                                                                                                 |
| v6f 引用（组内/序列）           | 1,214                 | 其中 118 个序列子字段是训练表 raw 列直连（不经 FG 命名特征）                                                                                    |
| **FG 有、v6f 未用（命名特征）** | **81**                | 本清单 §2                                                                                                                                       |
| **FG 有、v6f 未用（序列级）**   | **2 整条 + 2 子字段** | §1（like_100_seq / search_conversion_20_seq / 2×ts）                                                                                            |
| kv(lookup) 731                  | **全部已用**          | 覆盖矩阵见 §3                                                                                                                                   |

**序列命名对账已清**【事实读数】：FG `sequence_id_feature` 的 48 个（offline_chajia_click_100 / offline_like_100 / offline_order_100 / offline_search_click_100 × 12 子字段）与 config 逐位匹配、全部在用；config 另 118 个 `*_seq__*` 是训练表 raw 列（`;` 分隔）直连，不属 FG 命名特征差集。`f_req_domain`、顶层 `ts` 两个 FG 特征 config 定义了但组内未引用（L2）。

______________________________________________________________________

## 一、L0 序列级未使用（最高优先级）【事实读数】

### 1.1 两条整序列：FG 现成、config 零接入

| 序列                         | 长度 | pk                            | 子字段                                                                | 状态       | 判断【推断】                                                                                 |
| ---------------------------- | ---- | ----------------------------- | --------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------------------------- |
| **like_100_seq**             | 100  | user:like_100_seq             | 20 个（同 click_50 集：item_id/cate/brand/core_entity/site/spu/ts/…） | **全未用** | 点赞=强正向意图，序列匹配信号（浓度 2.35×）的增量来源；offline_like_100 已在用，在线版更实时 |
| **search_conversion_20_seq** | 20   | user:search_conversion_20_seq | 20 个（同上）                                                         | **全未用** | 搜索场景转化=最强意图；conversion_20 在用，此为场景细分（对齐 kv 的 \*\_search 细分逻辑）    |

### 1.2 两个 ts 子字段：**修正此前"FG 缺 ts"的说法**

| 子字段                     | 状态                             | 修正说明                                                                                |
| -------------------------- | -------------------------------- | --------------------------------------------------------------------------------------- |
| chajia_click_100_seq\_\_ts | FG 块内**已定义**，config 未引用 | 此前 PLAN_CTR_NEXT P1b 写"需 FG 补 2 列 ts"——**收回**：FG v5 已有，纯 config 侧接入即可 |
| search_click_100_seq\_\_ts | 同上                             | 同上                                                                                    |

⚠️ 前提【事实读数→待核】：训练样本表需有对应列（`chajia_click_100_seq__ts`/`search_click_100_seq__ts`/`like_100_seq__*`/`search_conversion_20_seq__*`）。click_50_seq\_\_ts 已证实存在（SQL-1 勘察），其余待 SQL-7（`DESC` 训练表）确认——若训练表未落列，转为 FG+样本管道需求单。

### 1.3 两个零散定义

- `f_req_domain`（请求域名）：定义后未引用【事实读数】；域名与 site 高共线，价值低【推断】，暂缓。
- 顶层 `ts`（user:ts 通用时间戳）：未引用；序列 ts 已覆盖近因语义，冗余【推断】。

______________________________________________________________________

## 二、81 个命名特征未使用清单（逐条 + 建议动作）【事实读数】

动作图例：**采纳**=建议接入试点；**试点**=低置信挑臂验证；**暂缓**=先验弱/成本高；**弃**=不建议。

### A. user 实时窗计数（12 个）——曝光/场景活跃的标量实时版

| #   | 特征                           | 表达式 | 动作     | 判断【推断】                                                          |
| --- | ------------------------------ | ------ | -------- | --------------------------------------------------------------------- |
| 1   | user\_\_cnt_exposure_rt1h      | user:… | **采纳** | 曝光族 kv +0.52pp 同方向；实时窗是 kv rt 窗的标量版，会话强度直接信号 |
| 2   | user\_\_cnt_exposure_rt3h      | 同     | **采纳** | 同上                                                                  |
| 3   | user\_\_cnt_exposure_rt12h     | 同     | **采纳** | 同上                                                                  |
| 4   | user\_\_cnt_exposure_rt24h     | 同     | **采纳** | 同上                                                                  |
| 5   | user\_\_cnt_chajia_click_rt1h  | 同     | **试点** | 比价场景实时意图；chajia 序列已在用，补标量实时窗                     |
| 6   | user\_\_cnt_chajia_click_rt3h  | 同     | **试点** | 同上                                                                  |
| 7   | user\_\_cnt_chajia_click_rt12h | 同     | **试点** | 同上                                                                  |
| 8   | user\_\_cnt_chajia_click_rt24h | 同     | **试点** | 同上                                                                  |
| 9   | user\_\_cnt_search_click_rt1h  | 同     | **试点** | 搜索场景实时意图，同构                                                |
| 10  | user\_\_cnt_search_click_rt3h  | 同     | **试点** | 同上                                                                  |
| 11  | user\_\_cnt_search_click_rt12h | 同     | **试点** | 同上                                                                  |
| 12  | user\_\_cnt_search_click_rt24h | 同     | **试点** | 同上                                                                  |

注：同族 15d/60d/360d 窗的 cnt 特征 v6f **已用**（click/conversion/favorite/exposure_15d/search/chajia），此 12 个是纯 rt 窗缺口。

### B. overlap 重叠度（10 个）——同构特征已在用

| #     | 特征                                                                                 | 动作     | 判断【推断】                                                                                |
| ----- | ------------------------------------------------------------------------------------ | -------- | ------------------------------------------------------------------------------------------- |
| 13-17 | offline_like\_{brand,first_cate_id,second_cate_id,third_cate_id,site}\_common_ratio  | **采纳** | offline_chajia / offline_search_click 的同构 10 个**已用**——like 版是同管道现成产物，纯加法 |
| 18-22 | offline_order\_{brand,first_cate_id,second_cate_id,third_cate_id,site}\_common_ratio | **采纳** | order=成交意图重叠度，同构，纯加法                                                          |

这 10 个与已用的 chajia/search_click common_ratio 构成完整组，接入边际成本最低（无新 FG/样本需求）。

### C. user 价格偏好补齐（5 个）——已用同族的场景/曝光缺口

| #   | 特征                                            | 动作     | 判断【推断】                                                             |
| --- | ----------------------------------------------- | -------- | ------------------------------------------------------------------------ |
| 23  | user\_\_num_exposure_avg_current_price_15d      | **采纳** | 曝光均价=用户价格带暴露面，与曝光族 +0.52pp 同方向                       |
| 24  | user\_\_num_chajia_click_avg_current_price_15d  | **试点** | 已用同族：click/conversion/favorite × 15d/60d/360d 共 9 个；场景细分补齐 |
| 25  | user\_\_num_chajia_click_avg_current_price_360d | **试点** | 同上                                                                     |
| 26  | user\_\_num_search_click_avg_current_price_15d  | **试点** | 同上                                                                     |
| 27  | user\_\_num_search_click_avg_current_price_360d | **试点** | 同上                                                                     |

### D. item 侧先验（14 个）——注意 convert_probability 泄漏核查

| #   | 特征                    | 类型           | 动作               | 判断【推断】                                                                                                                             |
| --- | ----------------------- | -------------- | ------------------ | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 28  | **convert_probability** | raw float      | **试点（先核查）** | item 转化概率先验，信号强；⚠️ **必须确认生成时点**（模型分不得用当前样本窗之后的数据训练，否则目标泄漏+与 label 捷径相关），核查不过则弃 |
| 29  | srh_hot                 | id string      | **采纳**           | 搜索热度=item 运营信号，与 srh 系列序列/意图正交                                                                                         |
| 30  | price_drop_freq         | id string      | **采纳**           | 降价频率=价格敏感用户钩子，与 discount_intensity/pinpaidengji 互补                                                                       |
| 31  | comment_tag             | id string      | **试点**           | 评论标签=口碑信号                                                                                                                        |
| 32  | his_high_level          | id string      | **试点**           | 历史层级=品质信号                                                                                                                        |
| 33  | coupon_titles           | id string      | **试点**           | 优惠券标题=促销信号，与 promotion_channel 互补                                                                                           |
| 34  | create_time             | raw float      | **试点**           | 与已用 pub_hours_fg（发布小时，expr）部分冗余；可只补一个                                                                                |
| 35  | pub_time                | raw float      | **暂缓**           | pub_hours_fg 已派生在用，原始时间戳冗余                                                                                                  |
| 36  | copyright_end           | raw float      | **弃**             | 版权到期与 CTR 无机制关联                                                                                                                |
| 37  | modifiers               | id string      | **弃**             | 语义不明，先验缺失                                                                                                                       |
| 38  | sqk_id                  | id string      | **弃**             | 站内 id，语义不明                                                                                                                        |
| 39  | cate                    | id string      | **暂缓**           | 与 first/second/third_cate_id、cate_id_path 四层类目高度共线                                                                             |
| 40  | title_vector (128 维)   | raw float[128] | **暂缓**           | 文本向量有信息但接入改造大（独立 emb/MLP 通路）；属 P2 级独立立项                                                                        |

### E. 用户侧画像/资产/归因（16 个）

| #     | 特征                                                                                                                | 动作     | 判断【推断】                                                                                           |
| ----- | ------------------------------------------------------------------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------ |
| 41    | intergral（积分）                                                                                                   | **试点** | 购买力/忠诚度资产信号                                                                                  |
| 42    | gold_coin（金币）                                                                                                   | **试点** | 同上                                                                                                   |
| 43    | login_time                                                                                                          | **试点** | 活跃节奏                                                                                               |
| 44    | crowd_prefer                                                                                                        | **试点** | 人群包偏好，冷启动有益；注意分布偏斜                                                                   |
| 45-49 | first_ad_name / first_campaign_name / first_site_name / first_utm_campaign / first_utm_source（获客归因 5 件套）    | **暂缓** | 获客渠道→留存偏好有先验，但高基数+分布偏斜+合规敏感；多场景（home/bijia/haojia/trend）人群差异大时再上 |
| 50-54 | is_atpush / is_not_disturb / is_subscribe_clockin / is_subscribe_discount / is_subscribe_savemoney（推送订阅 5 件） | **试点** | 订阅偏好≈价格敏感/互动意愿画像，弱先验、维度小、便宜                                                   |
| 55    | dev_model                                                                                                           | **弃**   | 与 dev_brand 高共线（dev_brand 的 combo 也未用）                                                       |
| 56    | sdk_version                                                                                                         | **弃**   | 工程属性，无机制                                                                                       |
| 57    | jpush / receive_push                                                                                                | **弃**   | 推送通道属性                                                                                           |
| 58    | type（user:type）                                                                                                   | **弃**   | 语义不明                                                                                               |

### F. combo 交叉（22 个）——大部分弃、少数粗交叉试点

| #     | 特征组                                                                                          | 动作     | 判断【推断】                                                                                   |
| ----- | ----------------------------------------------------------------------------------------------- | -------- | ---------------------------------------------------------------------------------------------- |
| 59-64 | gender/login_city/dev_brand × {item_id, related_goods_ids}（ID 级交叉 12 个中的 6）             | **弃**   | K1 已证 ID 级 target-keyed 统计边际≈0.03pp；DCNv2 cross_num=4 本就合成这类交叉，冗余           |
| 65-70 | gender/login_city/dev_brand × {first_cate_id, second_cate_id, third_cate_id}（粗实体交叉 9 个） | **试点** | 粗实体×人群交叉（gender×品类偏好）DCN 不一定高效合成；挑 gender×third_cate_id 1 个单臂先验验证 |
| 71-73 | dev_brand × {first,second,third}\_cate_id                                                       | **试点** | 设备×品类，弱先验                                                                              |
| 74-77 | brand/cate_id_path/core_entity × f_req_month（4 个）                                            | **弃**   | item 实体×请求月=时间×实体的笛卡尔积，样本稀疏、过拟合风险                                     |
| 78-79 | login_city × f_req_month                                                                        | **弃**   | 同上                                                                                           |
| 80    | brand_x_discount_intensity_fg                                                                   | **弃**   | item×item 交叉，DCN 可合成                                                                     |
| 81    | price_tag_x_discount_intensity_fg / cate_id_path_x_discount_intensity_fg                        | **弃**   | 同上                                                                                           |

______________________________________________________________________

## 三、FG 侧缺口（≠未使用，是"不存在"）【事实读数】

kv 族 731 全部已用，但**覆盖矩阵**显示 FG 侧窗口/行为缺口（对照 PLAN_CTR_NEXT P0a/P0b/P0d）：

| 缺口                                                             | 现状                                    | 对应                             |
| ---------------------------------------------------------------- | --------------------------------------- | -------------------------------- |
| exposure 族缺 60d/360d 窗                                        | 仅 15d + rt1h~rt24h                     | P0b（补窗+近/远衰减比值）        |
| cfr/ctr/cvr 缺 15d 与 rt 窗                                      | 仅 60d/360d                             | P0a（cfr 实体扩展 12→19 + 补窗） |
| 场景细分 exposure 缺失                                           | \*\_chajia/\_search 细分只有 click 行为 | P0d（search/chajia_exposure）    |
| \*\_chajia/\_search 细分实体缺 conversion/favorite/exposure 行为 | 只有 click                              | P0d 延伸                         |

______________________________________________________________________

## 四、优化建议（分级，对齐 PLAN_CTR_NEXT 判据）

判据沿用【预注册】：Δ≥+0.10pp 续投、|Δ|≤0.05pp 弃、过闸后 3-seed 符号闸 + 清 train==eval 债才宣称；配对协议、单变量、一臂一族。

### P0（证据同构 / 纯加法，先跑）

| 序   | 臂                             | 内容                                                                                         | 成本                                                         | 预期【推断】                                                |
| ---- | ------------------------------ | -------------------------------------------------------------------------------------------- | ------------------------------------------------------------ | ----------------------------------------------------------- |
| P0-1 | **L0 序列接入**                | like_100_seq + search_conversion_20_seq 两条整序列（各 20 子字段，含 ts）→ DIN/seqtrans 通路 | config 2 块（前提 SQL-7 确认训练表列在；不在则转 FG 需求单） | +0.1~0.3pp（序列匹配浓度 2.35×、远端检索 1.38× 的新工作面） |
| P0-2 | **ts 补全 + time_gate 全序列** | chajia/search_click 的 ts 接入 + time_gate_dim:8（T3 形态推广）                              | 纯 config（FG 已有 ts）                                      | +0.05~0.15pp                                                |
| P0-3 | **overlap 补齐 10 条**         | offline_like/order common_ratio 全族                                                         | 纯 config                                                    | +0.03~0.1pp                                                 |
| P0-4 | **exposure 实时标量**          | user\_\_cnt_exposure_rt×4 + num_exposure_avg_current_price_15d（5 条）                       | 纯 config                                                    | +0.05~0.15pp（曝光族同方向）                                |

### P1（单臂验证）

| 序   | 臂                | 内容                                                                     | 备注                                                             |
| ---- | ----------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------- |
| P1-1 | item 先验组       | srh_hot + price_drop_freq + comment_tag + his_high_level + coupon_titles | 一次一族或打包单臂；convert_probability **单独臂**且先过泄漏核查 |
| P1-2 | 价格偏好补齐      | user\_\_num\_\*avg_current_price 4 条场景版                              | 与 P0-4 可合并为"价格带"单变量                                   |
| P1-3 | 实时场景计数      | cnt\_{chajia,search}\_click_rt×8                                         | 与 P0-4 合并为"rt 标量"单变量                                    |
| P1-4 | 推送订阅画像 5 条 | is_subscribe\_\* 等                                                      | 便宜小臂                                                         |
| P1-5 | 粗人群交叉试点    | gender_x_third_cate_id_fg（1 条先行）                                    | 验证后决定是否扩 9 条粗交叉                                      |

### P2（独立立项 / 慎重）

- title_vector 128 维文本通路（改造大）；
- 获客归因 5 件套（高基数+合规+偏斜，多场景差异大时再议）；
- intergral/gold_coin/login_time/crowd_prefer 资产组。

### 明确弃（防回头路）

ID 级 combo（dev_brand/gender/login_city × item_id/related_goods_ids）、item×item combo、copyright_end/modifiers/sqk_id/dev_model/sdk_version/jpush/receive_push/type/pub_time（与 pub_hours_fg 冗余）/cate（四层类目共线）。

### 排序逻辑（与证据线对账）【推断】

1. **L0 两条序列（P0-1）是清单里唯一的"新工作面"级机会**——其余 81 条都是标量/交叉的边际补强。SQL 链已坐实：匹配浓度 2.35×、部分匹配工作面 72.3%、远端检索 1.38×；like/search_conversion 带来**新的匹配源**，是 T2（4 路读出 +0.074pp）之外唯一可能上 0.1pp 的杠杆。
1. 曝光方向（P0-4）与 +0.52pp 增益同构【事实读数】，是最稳的标量臂。
1. combo/ID 级特征受 K1 结论（ID 级边际≈0.03pp）+ DCN 合成能力双重压制【推断】，弃。
1. convert_probability 单列是因为**泄漏风险**而非价值低——价值反而可能是 item 组最高。

______________________________________________________________________

## 五、下一步（SQL 纪律）

按纪律给下一条 SQL（即 PLAN_CTR_NEXT 已预告的 SQL-7，现在优先级提升为 P0-1 的前置）：

```sql
-- SQL-7: 训练表全字段勘察 —— 确认 L0 接入前提
-- ① like_100_seq__* / search_conversion_20_seq__* 20 字段是否已落列
-- ② chajia_click_100_seq__ts / search_click_100_seq__ts 是否已落列
-- ③ cart/stay/share/负反馈/场景曝光列是否存在（P0c/P0d 前置）
DESC mmb_sage.feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set;
```

拿到 DESC 结果看三点：① 两条新序列的列是否在（在→P0-1 纯 config 可跑；不在→FG/样本管道需求单，P0-2/3/4 先跑）；② 两个 ts 列是否在（在→P0-2 即刻可跑）；③ 顺带核对 cart/stay/share/负反馈列（PLAN 的 P0c）。贴回来后我出 config 变更单或 FG 需求单。

______________________________________________________________________

*创建：2026-11-05。对账源：fg_v5.json（1,186 条目）× v6f_kv_fusion.config（1,098 定义/1,214 引用）。修正项：PLAN_CTR_NEXT P1b "search/chajia 补 ts 需 FG 加列" → FG v5 已有，纯 config 侧（训练表列存在性待 SQL-7）。*

______________________________________________________________________

## 六、DDL 核查定谳（20261107，SQL-7 由 DDL 直接回答）

**数据源**【原始证据】：单日样本表 fg 前 `mmb_sage.feature_mall_home_flow_2608_ctrcvr_sorter_v5_training_set.ddl`（1,502 列）× 60d 训练集 fg 后 `home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5.ddl`（1,358 列）。

### 6.1 SQL-7 三问全部答完【事实读数】

| 核查项                                      | fg 前样本表 | fg 后编码表（模型实际输入）                   | 结论                                                                                         |
| ------------------------------------------- | ----------- | --------------------------------------------- | -------------------------------------------------------------------------------------------- |
| **like_100_seq** 20 列（含 ts）             | ✅ 20       | ✅ 20（id 类 ARRAY<STRING>，ts=ARRAY<FLOAT>） | **P0-1 前提成立，纯 config 可接**                                                            |
| **search_conversion_20_seq** 20 列（含 ts） | ✅ 20       | ✅ 20                                         | **P0-1 前提成立，纯 config 可接**                                                            |
| **chajia_click_100_seq\_\_ts**              | ✅          | ✅ ARRAY<FLOAT>                               | **P0-2 前提成立**；config 定义=False 引用=False，需加定义+入组（照 click_50_seq\_\_ts 形态） |
| **search_click_100_seq\_\_ts**              | ✅          | ✅ ARRAY<FLOAT>                               | 同上                                                                                         |
| cart/加购                                   | ❌ 无       | ❌ 无                                         | **P0c 数据面不存在** → FG+样本管道需求单，非 config 可解                                     |
| stay/停留                                   | ❌ 无       | ❌ 无                                         | 同上                                                                                         |
| share/分享                                  | ❌ 无       | ❌ 无                                         | 同上                                                                                         |
| 负反馈/dislike                              | ❌ 无       | ❌ 无                                         | 同上                                                                                         |
| 场景细分 exposure                           | ❌ 无       | ❌ 无                                         | **P0d 同上**（exposure 族只有总量，无 search/chajia 细分）                                   |

### 6.2 P0-3 修正：common_ratio 20 个全部已在编码表落列【事实读数】

fg 前样本表 0 个 → fg 后编码表 **20 个 FLOAT 列**（pyfg 编码时由 FG overlap_feature 派生计算）：offline\_{chajia,search_click,like,order} × {brand,first_cate_id,second_cate_id,third_cate_id,site}\_common_ratio。其中 chajia/search_click 10 个已用，**like/order 10 个未用、纯 config 可接**（P0-3 前提成立，此前"需 FG 计算"的担心解除；同时修正本清单初次核查 `re.match` 前缀匹配导致的 common_ratio=0 误报）。

### 6.3 新发现：第三类口径——人群比率族 219 个"样本表有、编码表丢弃"【事实读数】

`__kv_ratio_*` 族 219 个（人群前缀 age_group / dev_brand / gender / login_city × 19 实体 × click/conversion/favorite 三行为 × exposure 比率）在 fg 前样本表已落列，但 **pyfg 编码配置未编它们**（fg 后 0 列）——与 FG v5 json 的 731 kv 是不同族（人群级比率 vs 用户级计数）。启用需改 pyfg 编码配置（改动面 > 纯 config，但样本已生产）。价值判断【推断】：人群×实体偏好比率与已用 kv 部分同构、DCN 可合成 gender/login_city×cate 粗交叉，**试点级**（挑 age_group\_\_kv_ratio_third_cate_id_click_exposure_15d 之类 1-2 条验证），不进 P0。

同批消失列还有旧名 combo（brand_x_gender 等 10 个，fg 后以 \*\_fg 新名重新出现 68 个）与 meta 列（scene/page 等，label 侧）。

### 6.4 编码表未用 143 列 = 最终可接口径【事实读数】

模型真正能吃而没吃的：两条序列 40 + 2 个 ts + combo \*_fg 22 + user\_\_cnt_rt 12 + user\_\_num 5 + common_ratio like/order 10 + 推送订阅画像 5（is_atpush/is_not_disturb/is_subscribe_\*3）+ item/user 原始 20+（convert_probability/srh_hot/price_drop_freq/title_vector/获客归因等）+ label/scene 标志 14（is_click 等是 label 不算特征）。

### 6.5 P0 状态更新（前提全成立 → config 变更单可出）

| 臂                                                                 | 前提       | 状态                                                                                   |
| ------------------------------------------------------------------ | ---------- | -------------------------------------------------------------------------------------- |
| P0-1 两条序列接入（like_100 + search_conversion_20，各 20 子字段） | 编码表列在 | ✅ **可跑**（config 加序列编码器块，对齐 click_50 形态：DIN/seqtrans 通路）            |
| P0-2 ts 补全 + time_gate                                           | 编码表列在 | ✅ **可跑**（chajia/search_click 的 ts 加定义+入组 + time_gate_dim:8）                 |
| P0-3 overlap 补齐 10 条                                            | 编码表列在 | ✅ **可跑**（照 offline_chajia\_\*\_common_ratio 的 bucketizer 形态加 10 条定义+入组） |
| P0-4 exposure rt 标量 5 条                                         | 编码表列在 | ✅ **可跑**                                                                            |
| P0c/P0d（cart/stay/share/负反馈/场景曝光）                         | 数据面无   | ❌ 转 FG+样本管道需求单（20261107 判定）                                               |

判据不变：Δ≥+0.10pp 续投、|Δ|≤0.05pp 弃、过闸 3-seed 符号闸；一臂一族、配对协议。**下一步**：待立项确认后出 P0-1~P0-4 的 config 变更单（新增 config，不动既有文件）。
