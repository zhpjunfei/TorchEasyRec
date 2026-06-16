# sample_v3 特征工程逻辑

## 目录结构 & 数据流

```
┌══════════════════════════ 离线批处理 (ODPS MaxCompute, 每日一次) ══════════════════════════┐
│                                                                                           │
 │ [ODPS源表]                                                                                │
│     │ mmb_dwh.dwd_log_zhekou_rec_user_bhv_info                                             │
│     ▼                                                                                     │
│ ⓪ preprocess_v1.sql ──────→ preprocess_v1 (10列, 当天行为日志, 含request_id/page)         │
│     │                                                                                     │
│     ├──→ ① item_basic_info_preprocess_v3.sql ─────→ item_basic_info_preprocess_v3         │
│     │       (商品画像宽表, 30+列, 含title_vector)                                          │
│     │                                                                                     │
│     ├──→ pre_t_agg_v1.sql ←── 行为预聚合                                                  │
│     │       │ 15天, [mmb_id,item_id,event]去重, 截Top-50/20/10                            │
│     │       │ 输出: pre_t_agg_v1 (5列, 不含商品属性!)                                    │
│     │       │                                                                             │
│     │       ├──→ pre_t_seq 分支 (历史行为，T-1)                                           │
│     │       │       │  LEFT JOIN item_basic_info 补齐商品属性                              │
│     │       │       ├── behavior_wide_for_pre_t_seq_v3 (宽表,行为+商品画像)               │
│     │       │       │   └── WM_CONCAT_BY_SORT 按 mmb_id 聚合，产出 6 种序列               │
│     │       │       └── mmb_id_pre_t_seq_v3 (6×21=126列 序列特征)                         │
│     │       │                                                                             │
│     │       └──→ pre_t_agg_v1_agg.sql ←── FS 同步中间表                                   │
│     │            └── 180天行为, 再次去重截断, 输出5列                                       │
│     │                用作 Python sync 的 datasource                                        │
│     │                                                                                     │
│     └──→ t_seq 分支 (当天行为，T)                                                          │
│             │                                                                             │
│             ├── behavior_wide_for_t_seq_v3 (行为+商品画像 JOIN)                           │
│             │   └── RT_SEQ_FEATURE 窗口函数，产出 3 种序列                                │
│             └── mmb_id_t_seq_v3 (3×21=63列 序列特征)                                      │
│                                                                                           │
│ ② mmb_id_all_seq_feat_v3.sql                                                              │
│     ├── sq0 = t_seq (实时长序列: click_50, conversion_20, favorite_10)                     │
│     ├── sq1 = pre_t_seq (离线短序列: click_10, conversion_5, favorite_5)                   │
│     └── SINGLE_SEQ_REPLENISH 补齐 → 产出 6 种完整序列 (120列)                              │
│                                                                                           │
│ ③ fix_sample_v3.sql ──────→ training_set (含 ~600 列非序列特征)                           │
│                                                                                           │
│ [下游 pipeline 将 training_set + all_seq_feat JOIN]                                       │
│     │                                                                                     │
│     ▼                                                                                     │
│ ④ pyfg101 编码 (ctrcvr_sorter_config_fg_v3.json)                                         │
│     │                                                                                     │
│     ▼                                                                                     │
│ ⑤ TFRecord → EasyRec 训练                                                                 │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘

┌══════════════════════════ 实时流处理 (Flink SQL) ════════════════════════════════════════┐
│                                                                                           │
│ SLS (LogService: mmb-zhekou-log/user-bhv-log)                                             │
│     │                                                                                     │
│     ├──→ ⑥ mmb_id_all_seq_feat_v1_flink.sql                                               │
│     │   └── 原始事件 (event_time, event, item_id, mmb_id) → FeatureStore (v1)             │
│     │       用于在线推理时实时拼接序列 (不自己做序列化, 由FS框架处理)                       │
│     │                                                                                     │
│     └──→ ⑦ statistic_real_time_feature_to_fs_v1.sql                                       │
│         └── SLS → JOIN item_info → MessageDelay → SWCountCatesKVS                         │
│              ├──→ item_id_rt_statistic_feat (item行为计数: 1h/3h/12h/24h)                 │
│              └──→ mmb_id_rt_statistic_feat (user行为KV特征: 20属性×3行为×4窗口)           │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘

┌══════════════════════════ 离线→在线同步 (Python) ════════════════════════════════════════┐
│                                                                                           │
│ ⑧ create_sync_onlinestore.py                                                              │
│     └── FeatureStoreClient → create_sequence_feature_view                                 │
│         ├── datasource = pre_t_agg_v1_agg (MaxCompute)                                    │
│         ├── event_time='event_unix_time' (源表event_time列) ✓                              │
│         ├── 120个 SequenceFeatureConfig (offline列→online序列名)                           │
│         ├── SequenceTableConfig(event_time='request_id') ← ⚠️ 配置错误                     │
│         └── publish_table(direct_sync=True) → FeatureStore 在线表                         │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘

┌══════════════════════════ 在线推理 (FeatureStore + FG + EasyRec) ════════════════════════┐
│                                                                                           │
│ 推理请求 (mmb_id, item_id, context)                                                        │
│     │                                                                                     │
│     ├──→ FeatureStore: 拉取用户行为序列 (v3同步历史 + v1 Flink实时)                       │
│     ├──→ FeatureStore: 拉取item/user统计特征 (statistic_rt + batch)                       │
│     ├──→ pyfg101: FG编码 → TFRecord                                                        │
│     └──→ EasyRec: 模型 scoring                                                             │
│                                                                                           │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

______________________________________________________________________

## 各文件详细逻辑

### 1. `item_basic_info_preprocess_v3.sql` — 商品画像

**输入**: `mmb_dwh.ads_log_zhekou_rec_item_basic_info` + `feature_mall_feed_rec_flow_item_title_embedding_v5_offline`

**输出**: `home_flow_2604_ads_log_zhekou_rec_item_basic_info_preprocess_v3`

**核心操作**:

| 操作         | 细节                                                                                                                                 |
| ------------ | ------------------------------------------------------------------------------------------------------------------------------------ |
| 特殊字符清洗 | 所有字符串字段将 `:`, `,`, `;` 替换为 `_`，避免与序列分隔符冲突                                                                      |
| 多值分隔符   | `keyword`/`tags`/`discount_type`/`modifiers` 将内部 `#` 替换为 `\x1d` (CHR(29))                                                      |
| title_vector | `ARRAY<DOUBLE>` → `STRING`：`CONCAT_WS(',', TRANSFORM(b.title_vector, x -> CAST(ROUND(x, 7) AS STRING)))`，每位保留7位小数，逗号分隔 |
| 去重         | 每个 `item_id` 取最新一条 `title_vector` embedding                                                                                   |

**关键细节**:

- `title_vector` 来源：`feature_mall_feed_rec_flow_item_title_embedding_v5_offline`，按 `fs_write_time DESC` 取最新
- 范围：dt >= '20260604' 至 T-1
- `CONCAT_WS(',', TRANSFORM(...))` 将 128 维浮点数组转为逗号分隔字符串，如 `"0.0275008,-0.1693267,...,0.0171398"`

______________________________________________________________________

### 1a. `dwd_log_zhekou_rec_user_bhv_info_preprocess_v1.sql` — 行为日志清洗

**文件**: `home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1.sql` (34 行)

**角色**: 整条 v3 管线最上游的行为数据入口。从 ODPS 源表读取当天行为日志，进行最小清洗。

**数据流**:

```
mmb_dwh.dwd_log_zhekou_rec_user_bhv_info (原始ODPS行为日志, dt=bizdate)
  │
  │ event_time, event, event_value, item_id, scene, mmb_id, request_id, page
  ▼
清洗操作:
  ① scene → REPLACE(':', '_')     ← 防序列分隔符冲突
  ② page  → REPLACE(':', '_')     ← 同上
  ③ event_time → event_unix_time  ← 别名
  ④ DATEPART → day_h             ← 当天第几小时 (0-23)
  ⑤ WEEKDAY  → week_day          ← 星期几 (0-6)
  ▼
home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_preprocess_v1 (10列)
```

**输出表 schema** (10 列):

| 列名              | 类型   | 说明                          |
| ----------------- | ------ | ----------------------------- |
| `event_unix_time` | BIGINT | Unix 时间戳                   |
| `event`           | STRING | click / conversion / favorite |
| `event_value`     | DOUBLE | 行为数值（如成交金额）        |
| `item_id`         | STRING | 商品 ID                       |
| `scene`           | STRING | 场景（已清洗 `:`）            |
| `mmb_id`          | STRING | 用户 ID                       |
| `request_id`      | STRING | 请求 ID                       |
| `page`            | STRING | 页面（已清洗 `:`）            |
| `day_h`           | BIGINT | 行为当天的小时                |
| `week_day`        | BIGINT | 行为当天的星期                |

**关键属性**: 仅含行为日志字段，**不含任何商品属性**（cate_id_path, brand 等）。商品属性在后续 SQL 中通过 LEFT JOIN `item_basic_info_preprocess_v3` 引入。

**下游引用**:

- `mmb_id_t_seq_v3.sql` (t_seq 分支): 直接引用, LEFT JOIN item_basic_info 得宽表
- `mmb_id_pre_t_agg_v1.sql` (pre_t 聚合): 从此表读取 15 天数据做聚合

______________________________________________________________________

### 1b. `dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1.sql` — 行为预聚合

**文件**: `home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1.sql` (36 行)

**角色**: 从 `preprocess_v1` 表聚合历史行为，去重 + 截断，作为 `pre_t_seq` 分支的输入。

**数据流**:

```
preprocess_v1 (10列, 15天分区: bizdate-14 ~ bizdate)
  │
  │ 过滤: event IN ('click','conversion','favorite')
  │
  ▼ 两层 Row_Number 去重截断:

  内层 rk: PARTITION BY mmb_id, item_id, event
           ORDER BY event_unix_time DESC
           → 保留 rk=1 (同一用户对同一商品同种行为只留最新)

  外层 rnk: PARTITION BY mmb_id, event
            ORDER BY event_unix_time DESC
            → 保留 rnk ≤ N: click=50, conversion=20, favorite=10
  ▼
pre_t_agg_v1 (5列, 每人每种行为最多N条)
```

**输出表 schema** (5 列):

| 列名              | 类型   | 说明                          |
| ----------------- | ------ | ----------------------------- |
| `event_unix_time` | BIGINT | Unix 时间戳                   |
| `event`           | STRING | click / conversion / favorite |
| `item_id`         | STRING | 商品 ID                       |
| `scene`           | STRING | 场景                          |
| `mmb_id`          | STRING | 用户 ID                       |

**关键属性**: 仅 5 列，**不含商品属性、不含 request_id、不含 event_value**。这是一个纯聚合索引表，记录"谁在什么时候对什么商品做了什么行为"。

**与 `preprocess_v1` 的对比**:

| 维度     | preprocess_v1                                | pre_t_agg_v1                   |
| -------- | -------------------------------------------- | ------------------------------ |
| 数据范围 | 当天 (dt=bizdate)                            | 近 15 天                       |
| 行数     | 当天全部行为                                 | 去重后每人每种最多 50/20/10 条 |
| 列数     | 10 列 (含 request_id, page, day_h, week_day) | 5 列 (仅核心标识)              |
| 用途     | t_seq 分支的宽表源                           | pre_t_seq 分支的聚合源         |

**两层去重的意义**:

```
原始日志: 用户A 在1分钟内点击了商品X 3次
  ↓ 内层 rk: 3 条 → 保留 1 条 (最新那次)
  ↓ 外层 rnk: 该用户当日可能有200次click → 保留最近的50条
```

**下游引用**:

- `mmb_id_pre_t_seq_v3.sql`: 引用 `pre_t_agg_v1`，LEFT JOIN `item_basic_info_preprocess_v3` 补齐商品属性后做 WM_CONCAT_BY_SORT
- `mmb_id_pre_t_agg_v1_agg.sql`: 引用 `pre_t_agg_v1` 的 180 天分区做第二层聚合 (FS 同步数据源)

______________________________________________________________________

### 2. `mmb_id_pre_t_seq_v3.sql` — 离线预训练序列特征

**输入**: `pre_t_agg_v1` (历史行为聚合, 5列) + `item_basic_info_preprocess_v3` (商品画像, 30+列)

**关键**: `pre_t_agg_v1` 只含行为标识（谁、什么时间、对什么商品、做了什么），不含商品属性。商品属性在此步骤通过 LEFT JOIN `item_basic_info_preprocess_v3` 引入，形成宽表后再做 WM_CONCAT_BY_SORT 序列化。

**输出**: `home_flow_2604_mmb_id_pre_t_seq_v3`

**数据流**:

```
behavior_wide_for_pre_t_seq_v3 ── 行为日志 LEFT JOIN 商品画像
    │
    └── GROUP BY mmb_id ── WM_CONCAT_BY_SORT 聚合 ──→ pre_t_seq (126列)
```

**WM_CONCAT_BY_SORT 函数** 为每种序列 × 每个子特征各自独立调用一次（重复 126 次）。

**6 种序列**:

| 序列名              | 行为过滤     | 最大长度 | 用途                        |
| ------------------- | ------------ | -------- | --------------------------- |
| `click_10_seq`      | `click`      | 10       | 近10次点击，用于 DIN 注意力 |
| `click_50_seq`      | `click`      | 50       | 近50次点击，长序列捕捉      |
| `conversion_5_seq`  | `conversion` | 5        | 近5次转化                   |
| `conversion_20_seq` | `conversion` | 20       | 近20次转化                  |
| `favorite_5_seq`    | `favorite`   | 5        | 近5次收藏                   |
| `favorite_10_seq`   | `favorite`   | 10       | 近10次收藏                  |

**每个序列包含 21 个子特征**:

```
item_id, cate_id_path, related_goods_ids, brand, core_entity,
first_cate_id, second_cate_id, third_cate_id, price_tag,
promotion_channel, publish_user, site, spu_id,
discount_intensity, dianpupingfen, pinpaidengji, dianpufensi,
item_type, username, title_vector, ts
```

**每列的格式**:

```
click_10_seq__item_id:       "12345;67890;111213;..."
click_10_seq__ts:            "1623456789;1623456790;..."
click_10_seq__title_vector:  "0.0275,-0.1693,...;0.0970,-0.1213,..."
```

**填鸭逻辑**: 通过 `IF(LENGTH(col)>0, col, '')` 确保空行为空字符串而非 NULL。

______________________________________________________________________

### 3. `mmb_id_t_seq_v3.sql` — 在线推断序列特征

**输入**: `dwd_log_zhekou_rec_user_bhv_info_preprocess_v1` (实时行为) + `item_basic_info_preprocess_v3`

**输出**: `home_flow_2604_mmb_id_t_seq_v3`

**与 pre_t_seq 的核心区别**:

| 维度       | pre_t_seq (离线)                        | t_seq (在线)                                |
| ---------- | --------------------------------------- | ------------------------------------------- |
| 数据来源   | T-1 预聚合历史行为                      | 当天实时行为日志                            |
| 聚合方式   | `GROUP BY mmb_id` + `WM_CONCAT_BY_SORT` | `RT_SEQ_FEATURE` 窗口函数                   |
| 序列数量   | 6 种                                    | 3 种 (click_50, conversion_20, favorite_10) |
| 子特征数量 | 21                                      | 21                                          |
| 定位       | 完整序列离线训练                        | 短序列在线拼接，训练时回填                  |

**RT_SEQ_FEATURE 签名**:

```sql
RT_SEQ_FEATURE(
    partition_key,        -- mmb_id
    order_col,            -- event_unix_time
    feature_array,        -- ARRAY(20个子特征的当前行值)
    feature_names,        -- ARRAY('item_id', ..., 'title_vector')
    event_col,            -- event 字段
    event_filter,         -- ARRAY('click','conversion','favorite')
    max_lengths,          -- ARRAY(50,20,10)
    reverse,              -- 1 (时间倒序)
    seq_combine,          -- 'split'
    seq_len,              -- 3 (3种行为)
    delimiter,            -- ';'
    request_id
) → MAP<string, string>
```

______________________________________________________________________

### 4. `mmb_id_all_seq_feat_v3.sql` — 序列特征全量汇总

**输入**: `t_seq` (sq0) + `pre_t_seq` (sq1)

**输出**: `home_flow_2604_mmb_id_all_seq_feat_v3`

**核心**: `t_seq` 有长序列 (50/20/10)，`pre_t_seq` 有短序列 (10/5/5)。通过 `SINGLE_SEQ_REPLENISH` 合并补齐：

```
click_10_seq        ← click_50_seq 截取前10 + pre_t_seq.click_10_seq
click_50_seq        ← t_seq.click_50_seq + pre_t_seq.click_50_seq
conversion_5_seq    ← conversion_20_seq 截取前5 + pre_t_seq.conversion_5_seq
conversion_20_seq   ← t_seq.conversion_20_seq + pre_t_seq.conversion_20_seq
favorite_5_seq      ← favorite_10_seq 截取前5 + pre_t_seq.favorite_5_seq
favorite_10_seq     ← t_seq.favorite_10_seq + pre_t_seq.favorite_10_seq
```

**SINGLE_SEQ_REPLENISH 签名**:

```sql
SINGLE_SEQ_REPLENISH(
    长序列列, 短序列列,
    参考序列(长), 参考序列(短),
    默认值, 分隔符, 目标长度, 对齐模式
)
```

______________________________________________________________________

### 5. `fix_sample_v3.sql` — 训练集定义

**输出**: `feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set`

**特征分类**:

| 类别         | 数量    | 示例                                                                                |
| ------------ | ------- | ----------------------------------------------------------------------------------- |
| 曝光样本主键 | 5 列    | `__item_id__`, `request_id`, `is_click`, `is_conversion`                            |
| 用户画像     | ~20 列  | `gender`, `province`, `dev_brand`, `install_apps`                                   |
| 商品画像     | ~35 列  | `item_id`, `cate_id_path`, `current_price`, `title_vector ARRAY<DOUBLE>`            |
| 交叉统计     | ~400 列 | `{group}__ratio_{b1}_{b2}_{window}d` / `{group}__kv_ratio_{feat}_{behav}_{window}d` |
| 用户行为统计 | ~60 列  | `user__cnt_click_15d`, `user__kv_brand_click_15d`                                   |
| 商品行为统计 | ~27 列  | `item__cnt_click_15d`                                                               |
| 实时行为 KV  | ~180 列 | `user__kv_item_id_click_rt1h`                                                       |

**字段命名规范**:

```
{维度}__{统计量}_{行为类型}_{时间窗口}
gender    ratio_click   click       15d
user      cnt_conversion conversion 3d
item      kv_ratio_brand favorite   1d
                                  rt1h (realtime 1 hour)
```

______________________________________________________________________

### 6. FG JSON — 特征工程配置

**文件**: `home_flow_2604_ctrcvr_sorter_config_fg_v3.json`

**特征类型**:

| FG 类型          | 数量 | 说明                                |
| ---------------- | ---- | ----------------------------------- |
| `id_feature`     | ~50  | 离散特征，Embedding 映射            |
| `raw_feature`    | ~100 | 连续特征，Bucketize 分桶            |
| `lookup_feature` | ~60  | KV 查询特征                         |
| `combo_feature`  | ~30  | 交叉组合                            |
| `sequence_*`     | 6    | click/conversion/favorite 各2种长度 |

**序列特征结构** (示例 click_10_seq):

```json
{
    "sequence_name": "click_10_seq",
    "sequence_length": 10,
    "sequence_delim": ";",
    "features": [
        {"feature_type": "id_feature", "feature_name": "item_id", ...},
        ...
        {"feature_type": "raw_feature", "feature_name": "title_vector",
         "value_dim": 128, "value_type": "float"},
        {"feature_type": "raw_feature", "feature_name": "ts", ...}
    ]
}
```

**pyfg101 序列处理**: 读 `{seq}__{feat}` 列 → 按 `;` 拆分为 N 个元素 → 每个元素按 feature_type 编码 → 输出固定长度序列。

______________________________________________________________________

## title_vector 完整流水线

```
item_embedding_v5_offline (ARRAY<DOUBLE>)
    │
    ▼ CONCAT_WS(',', TRANSFORM(ROUND(x,7)))
    ▼
item_basic_info_preprocess_v3.title_vector (STRING)
    │
    ├──→ behavior_wide_for_pre_t_seq_v3
    │       └── WM_CONCAT_BY_SORT → click_10_seq__title_vector (STRING)
    │
    └──→ behavior_wide_for_t_seq_v3
            └── RT_SEQ_FEATURE → click_50_seq__title_vector (STRING)

    ┌── all_seq_feat: 6 种 {seq}__title_vector (STRING)
    ├── training_set: title_vector (ARRAY<DOUBLE>)  ← 非序列版本

    [JOIN] → pyfg101
     ├── raw_feature title_vector {value_dim:128}    → 非序列
     └── sequence raw_feature title_vector {value_dim:128} → 序列

    → EasyRec: "all" group + click_10_seq group 中引用
```

**关键格式约束**:

- 外分隔符 `;` (FG `sequence_delim`)
- 内分隔符 `,` (128维浮点)
- 空元素用空串：`val1;;val3` → 第2位 pad
- 商品画像清洗时将 `,`/`;`/`:` 替换为 `_`，防冲突

______________________________________________________________________

## 7. `click_10_seq__ts` 完整机制（时间戳序列特征）

`ts` 在每个序列组中仅存在于 **sequence 侧**（无 target 侧配对），是整个 DIN 注意力中唯一的时间维度信号。

### 7a. 数据来源

```
behavior log: event_unix_time (BIGINT, Unix 时间戳, 如 1746028800)

pre_t_seq:  WM_CONCAT_BY_SORT(IF(LENGTH(event_unix_time)>0,event_unix_time,''),
                                event_unix_time, event, ARRAY('click'), ';', 10)
            → click_10_seq__ts: "1746028800;1746032400;1746036000;..."

t_seq:      RT_SEQ_FEATURE(..., event_unix_time, ARRAY(...feature列不含ts...), ...)
            → event_unix_time 作为排序键，自动输出 click_50_seq__ts
            → all_seq_feat 中 click_10_seq__ts 由 click_50_seq 截取补齐

fix_sample_v3: click_10_seq__ts STRING ← JOIN all_seq_feat
```

### 7b. 时间差计算（在 FG 层自动完成）

从 C++ `pyfg.FgArrowHandler` 内部处理 `expression: "user:ts"` 时，对序列元素的**原始 Unix 绝对时间戳**自动做：

```
delta_seconds = current_timestamp - event_unix_time
                ↑ FG 系统时间         ↑ 从序列拆出的元素值
```

**FG 输出的 TFRecord 中已存为时间差**（秒数），而非绝对时间戳。

证明：模型 config 的 boundaries 范围仅 46~610396（约 1 分钟~7 天），如果是绝对时间戳（~1.78e9），所有值会落入同一个末桶，特征失效。因此 TFRecord 中存的必是秒级时间差。

### 7c. FG 编码（raw_feature + expression）

FG JSON（每个序列组内的 ts 定义一致）：

```json
{
    "feature_type": "raw_feature",
    "feature_name": "ts",
    "default_value": "0",
    "expression": "user:ts",
    "value_type": "float"
}
```

**序列处理流程**：

```
click_10_seq__ts (STRING)
  → 按 ';' 拆 → ["1746028800", "1746032400", ...]
  → 对每个元素: expression "user:ts" → FG 自动计算 now - value (秒)
  → 输出 float 数组 [delta_0, delta_1, ..., delta_9]  →  [batch, 10] float32
```

### 7d. Model Config 定义

```protobuf
features {
  raw_feature {
    feature_name: "ts"
    expression: "user:ts"
    embedding_dim: 8                                           ← 每个 bucket 映射 8 维
    boundaries: 46.0     # < 1 分钟
    boundaries: 125.0    # ~2 分钟
    boundaries: 282.0    # ~5 分钟
    boundaries: 688.0    # ~11 分钟
    boundaries: 2513.0   # ~42 分钟
    boundaries: 7472.0   # ~2 小时
    boundaries: 14930.0  # ~4 小时
    boundaries: 25031.0  # ~7 小时
    boundaries: 36817.0  # ~10 小时
    boundaries: 49553.0  # ~14 小时
    boundaries: 64052.0  # ~18 小时
    boundaries: 79269.0  # ~22 小时
    boundaries: 89994.0  # ~25 小时
    boundaries: 115554.0 # ~1.3 天
    boundaries: 154402.0 # ~1.8 天
    boundaries: 190410.0 # ~2.2 天
    boundaries: 261456.0 # ~3 天
    boundaries: 379553.0 # ~4.4 天
    boundaries: 610396.0 # ~7 天
  }
}
```

**bucket 分配算法**：`bucket_id = count(boundary < raw_value)`（strict greater）。

对 delta=600 秒（10分钟前）：

```
600 > 46 ✓, 600 > 125 ✓, 600 > 282 ✓, 600 > 688 ✗ → bucket = 3
```

20 个 buckets（19 boundaries + 最高桶），每个 mapped to 8 维 embedding：

```
[delta_0] → bucket 3 → EmbeddingLookup(20×8) → [8]
[delta_1] → bucket 7 → EmbeddingLookup(20×8) → [8]
...
→ click_10_seq__ts_emb: [batch, 10, 8]   ← 仅 sequence 侧
```

### 7e. 在 DIN Attention 中的角色

| 特征         | target_emb                                     | seq_emb_i                                   | 差异点                                   |
| ------------ | ---------------------------------------------- | ------------------------------------------- | ---------------------------------------- |
| item_id      | ✅ **32-dim** from Embedding (top-level 3M×32) | ✅ **24-dim** from Embedding (seq 1.96M×24) | 两侧维度不同，seq 端由 DIN 自动 pad 对齐 |
| title_vector | ✅ 128-dim 直接值                              | ✅ 128-dim 直接值                           | 预训练冻结，无参数                       |
| cate_id_path | ✅ 12-dim                                      | ✅ 12-dim                                   | 两侧共有                                 |
| **ts**       | **❌ 无 target 侧**                            | **✅ 8-dim from bucket Embedding**          | **序列独有**                             |

在 attention score 计算中（对位置 i）：

```
input_i = concat(target_emb,      ← 不含 ts
                 seq_emb_i,       ← 含 ts_emb[8]
                 target_emb − seq_emb_i,
                 target_emb ⊙ seq_emb_i)

score_i = attn_MLP(input_i)
```

`ts_emb` 提供了 **"这个行为多久前发生的"时间维度信号**：近期行为（bucket 0~2）倾向高权重，久远行为（bucket 18~19）倾向低权重。

### 7f. 训练 vs 推理

| 阶段         | 训练                                        | 推理                          |
| ------------ | ------------------------------------------- | ----------------------------- |
| 原始值来源   | event_unix_time (绝对时间戳, BIGINT)        | 同                            |
| 时间差计算   | FG `user:ts` 表达式自动 `now - event_time`  | 同                            |
| Bucket 范围  | 46s~7天，20 buckets                         | 同                            |
| Embedding 表 | 20×8 = 160 参数，训练时更新                 | 冻结                          |
| pad 位置     | delta=0 → bucket 0（< 46s，可视为"刚发生"） | 空位 → default "0" → bucket 0 |
| 无历史行为   | 序列全 pad，ts 全 0 → bucket 0 → 无区分     | 同                            |

### 7g. 替代方案：乘法时间门控（B2）| 已实现

当前方案将 ts concat 进 seq_emb，与物品特征（item_id/cate_id/title_vector 等）混在一起。但 **ts 是行为交互属性（"多久前"），不是物品属性**——与 GAT 中边特征不应编码进节点表示同理。

#### B2 方案

```
seq_emb 中 ts 被门控分支接管（不移除 feature_names，仅从 attention content 中剥离）：
  T_seq = 224 → content=216, ts=8    ← 零 F.pad
  T_query = 216                        ← 不变

ts 单独走乘法门控分支：
  gate_i = Sigmoid(Linear(ts_emb))     ← [B, 10, 1]，∈ (0, 1)
  score_i = content_score_i × gate_i   ← 逐位置衰减
  weights = softmax(scores)
  user_interest = Σ(weights_i × seq_emb_i)
```

**物理含义**：时间对 attention score 做折扣缩放——越久远，score 打折越多。

#### 三种 ts 建模方式对比

| 维度              | 当前（concat 进 seq_emb）                | 加性偏置（A）                   | 乘法门控（B2）                                       |
| ----------------- | ---------------------------------------- | ------------------------------- | ---------------------------------------------------- |
| T_seq             | 224                                      | **216**                         | **216**                                              |
| T_query           | 216                                      | 216                             | 216                                                  |
| F.pad             | **8 维**                                 | **0 维**                        | **0 维**                                             |
| DIN MLP 输入      | 896                                      | 864                             | 864                                                  |
| ts 分支参数       | 20×8=160（bucket embed）                 | 8×1+1=9（Linear）               | 8×1+1=9（Linear+Sigmoid）                            |
| 时间对 score 影响 | 通过 seq_emb 间接影响                    | score + bias（加法、无约束）    | score × gate（乘法、门控 ∈ (0,1)）                   |
| 语义              | ❌ 时间混入物品特征，减法/乘法分支无意义 | ✅ 时间单独建模，不污染 content | ✅ 时间单独建模，门控直观                            |
| 衰减保证          | ❌ 无，MLP 自己学                        | ❌ 不保证单调                   | ⚠️ Sigmoid 不强制单调，但 g(0)>g(∞) 可由数据隐式学到 |

#### 实现细节

**Proto 改动** (`tzrec/protos/seq_encoder.proto`)：

```diff
 message DINEncoder {
     optional string name = 1;
     required string input = 2;
     required MLP attn_mlp = 3;
     optional int32 max_seq_length = 6 [default = 0];
+    optional int32 time_gate_dim = 7 [default = 0];  // 新增
 }
```

**模型代码改动** (`tzrec/modules/sequence.py` 的 `DINEncoder`)：

```diff
 class DINEncoder(SequenceEncoder):
-    def __init__(self, sequence_dim, query_dim, input, attn_mlp, max_seq_length=0, **kwargs):
+    def __init__(self, sequence_dim, query_dim, input, attn_mlp, max_seq_length=0, time_gate_dim=0, **kwargs):
         ...
-        self.mlp = MLP(in_features=sequence_dim * 4, dim=3, **attn_mlp)
+        self._time_gate_dim = time_gate_dim
+        self._content_seq_dim = sequence_dim - time_gate_dim
+        self.mlp = MLP(in_features=self._content_seq_dim * 4, dim=3, **attn_mlp)
+        if time_gate_dim > 0:
+            self.time_gate_linear = nn.Linear(time_gate_dim, 1)

-    def output_dim(self): return self._sequence_dim
+    def output_dim(self): return self._content_seq_dim

     def forward(self, sequence_embedded):
         sequence = sequence_embedded[self._sequence_name]
+        if self._time_gate_dim > 0:
+            ts_emb = sequence[:, :, -self._time_gate_dim:]      # [B, T, 8]
+            content_seq = sequence[:, :, :-self._time_gate_dim] # [B, T, 216]
+            gate = torch.sigmoid(self.time_gate_linear(ts_emb)) # [B, T, 1]
+        else:
+            content_seq = sequence
+            gate = None
         ...
-        scores = F.softmax(scores, dim=-1)
-        return torch.matmul(scores, sequence).squeeze(1)
+        if gate is not None:
+            scores = scores * gate.transpose(1, 2)   # 乘法门控
+        scores = F.softmax(scores, dim=-1)
+        return torch.matmul(scores, content_seq).squeeze(1)
```

**Config 改动**（基于 `seq_align`，结果见 `home_flow_2604_v10_seq_align_b2.config`；完全体 `seq_align_all_b2` 基于 `seq_align_all` 加 `time_gate_dim:8`，位于 `home_flow_2604_v10_seq_align_all_b2.config`）：

```diff
   sequence_encoders {
     din_encoder {
       input: "click_10_seq"
+      time_gate_dim: 8       // 新增：last 8 dims of seq_emb = ts
       attn_mlp { ... }
     }
   }  // 所有 6 个 DINEncoder 均添加
```

**关键设计**：

- ts 仍保留在 `sequence_groups.feature_names` 中（`SequenceEmbeddingGroup` 正常产出 224-dim seq_emb）
- DINEncoder 内部从 seq_emb 末尾 split 出 8-dim ts_emb，剩余 216-dim content
- `time_gate_dim=0`（默认值）保持原行为——完全向后兼容
- 不修改 proto `SeqEncoderConfig.oneof`，只在 `DINEncoder` 消息内增加一个 optional 字段

#### 各方案 DIN 输入变化

```
当前（baseline concat）：     [188] + [216/212] +  F.pad(0→24~28)  → MLP(896)
seq_align：                  [188] + [224/220] +  F.pad(0→32~36)  → MLP(896)
seq_align_b2（ts 门控）：     [188] + [216]     +  F.pad(0→28)     → MLP(864)
seq_align_cate（cate align）：[216] + [216/212] +  F.pad(0)/proj(4) → MLP(896)
seq_align_all：               [216] + [224/220] +  F.pad(4~8)      → MLP(896)
seq_align_all_b2：            [216] + [216]     +  零 F.pad        → MLP(864)  ← 最优
```

______________________________________________________________________

## 8. FG + Model Config 类型系统

**核心原则**: FG JSON 和 EasyRec `feature_configs` 通过 `feature_name` 做声明式类型匹配。两者必须同步。

```
FG JSON                            model config
─────────────────                  ────────────────────────
{                                   feature_configs {
  "feature_type": "id_feature",       id_feature {
  "feature_name": "item_id",            feature_name: "item_id"
  ...                                   embedding_dim: 32
}                                     }
                                    }

{                                   feature_configs {
  "feature_type": "raw_feature",      raw_feature {
  "feature_name": "title_vector",       feature_name: "title_vector"
  "value_dim": 128,                     value_dim: 128
  "value_type": "float"               }
}                                   }
```

**FG 决定如何从 ODPS 表解析原始值** → 输出 TFRecord。
**Model Config 决定如何从 TFRecord 消费** → 喂入网络。

两者通过同一 `feature_name` 字符串绑定。序列组中的配对规则：

```
sequence_groups { group_name: "click_10_seq"
  feature_names: "item_id"               ← 读 TFRecord 的 "item_id" 列
  feature_names: "title_vector"          ← 读 TFRecord 的 "title_vector" 列
  feature_names: "click_10_seq__item_id" ← 读 TFRecord 的 "click_10_seq__item_id" 列
  feature_names: "click_10_seq__title_vector" ← 读 TFRecord 的 "click_10_seq__title_vector" 列
}
```

配对逻辑：EasyRec 将前缀 `click_10_seq_` 剥离后，到 `feature_configs` 查同名定义。非序列的同名特征 (`item_id`, `title_vector`) 自动成为 **target 侧**，`{group}__X` 特征成为 **sequence 侧**。

______________________________________________________________________

## 9. FG 编码细节对比：item_id vs title_vector

| 阶段                       | item_id (离散)                                   | title_vector (连续)                                  |
| -------------------------- | ------------------------------------------------ | ---------------------------------------------------- |
| **FG 输入**                | `"12345"` (string)                               | `[0.0275, -0.1693, ..., 0.0171]` (ARRAY\<DOUBLE>)    |
| **FG 处理**                | `id_feature` → hash → int64 token                | `raw_feature` → 直接读取 128 个 float                |
| **FG 序列处理**            | 按 `;` 拆，每个 hash → `[batch, 10]` int64       | 按 `;` 拆，每个 parse `,` → `[batch, 10, 128]` float |
| **TFRecord 类型**          | `tf.int64`                                       | `tf.float32`                                         |
| **Model Config（target）** | `id_feature { embedding_dim: 32 }` (top-level)   | `raw_feature { value_dim: 128 }`                     |
| **Model Config（seq）**    | `id_feature { embedding_dim: 24 }` (sequence)    | `raw_feature { value_dim: 128 }`                     |
| **网络处理（target）**     | EmbeddingLookup(3M×32) → `[batch, 32]`           | 直接读 128 float → `[batch, 128]`                    |
| **网络处理（seq）**        | EmbeddingLookup(1.96M×24) → `[batch, 10, 24]`    | 直接读 → `[batch, 10, 128]`                          |
| **参数**                   | target: 3,000,000×32=96M / seq: 1,963,029×24=47M | 0 参数，预训练值透传                                 |

**序列版本的 pairing 规则**：

```
feature_names: "item_id"
  → 查 feature_configs（top-level）→ id_feature { embedding_dim: 32 }
  → EmbeddingLookup(3M×32) → [batch, 32]              # target 侧

feature_names: "click_10_seq__item_id"
  → 剥前缀 click_10_seq_ → 查序列 internal 定义
  → id_feature { embedding_dim: 24 }                  # ← 与 top-level 不同！
  → 10 个位置分别 EmbeddingLookup(1.96M×24) → [batch, 10, 24]  # sequence 侧

feature_names: "title_vector"
  → 查 feature_configs → raw_feature { value_dim: 128 }
  → 直接读 float → [batch, 128]                       # target 侧

feature_names: "click_10_seq__title_vector"
  → 剥前缀 → 查 "title_vector"
  → raw_feature { value_dim: 128 }
  → 10 个位置分别解析 → [batch, 10, 128]               # sequence 侧
```

______________________________________________________________________

## 10. DIN Attention 精确计算（含 Shape 标注）

以 click_10_seq 为例，batch=4096，seq_len=10。

展示：**baseline** (原 config) 与 **seq_align** (修复版) 的对比。

______________________________________________________________________

### 10a. 特征嵌入（阶段 1）

每个特征独立查表或读值。仅示意部分特征：

```
item_id (target)
  → EmbeddingLookup(3M×32)          : [4096]          → [4096, 32]
item_id (seq, baseline)
  → EmbeddingLookup(1.96M×24)       : [4096, 10]      → [4096, 10, 24]
item_id (seq, seq_align)
  → EmbeddingLookup(3M×32)          : [4096, 10]      → [4096, 10, 32]

title_vector (target)
  → 直接读 128 个 float             : [4096, 128]     → [4096, 128]
title_vector (seq)
  → 直接读 128 个 float             : [4096, 10, 128] → [4096, 10, 128]

ts (seq-only)
  → bucketize(20) → Embedding(20×8) : [4096, 10] raw  → [4096, 10, 8]
```

______________________________________________________________________

### 10b. 特征拼接（阶段 2）

```
query = concat(item_id[32], title_vector[128], cate_id_path[12],
               related_goods_ids[24], brand[16], core_entity[16],
               first_cate_id[8], second_cate_id[8], third_cate_id[12],   ← seq_align 新增
               price_tag[8], promotion_channel[4], publish_user[8],
               site[8], spu_id[24], discount_intensity[8],
               dianpupingfen[4], pinpaidengji[4], dianpufensi[4],
               item_type[4], username[12])
      = [4096, T_query]

sequence = concat(seq__item_id, seq__title_vector[128], seq__cate_id_path[12],
                  seq__related_goods_ids[24], seq__brand[16], seq__core_entity[16],
                  seq__first_cate_id[8], seq__second_cate_id[8], seq__third_cate_id[12],
                  seq__price_tag[8], seq__promotion_channel[4], seq__publish_user[8],
                  seq__site[8], seq__spu_id[24], seq__discount_intensity[8],
                  seq__dianpupingfen[4], seq__pinpaidengji[4], seq__dianpufensi[4],
                  seq__item_type[4], seq__username[12], seq__ts[8])
         = [4096, 10, T_seq]
```

维度对比：

| 版本      | T_query                       | T_seq                         | 差异来源                                 | F.pad 量  |
| --------- | ----------------------------- | ----------------------------- | ---------------------------------------- | --------- |
| baseline  | **188** (19 feat, item_id=32) | **216** (20 feat, item_id=24) | item_id 差8 + first/second/third/ts 差28 | **28 维** |
| seq_align | **216** (22 feat, item_id=32) | **224** (20 feat, item_id=32) | 仅 ts 差8                                | **8 维**  |

______________________________________________________________________

### 10c. 维度对齐（阶段 3）

```
# T_query < T_seq → DINEncoder 自动右补零
query_padded = F.pad(query, (0, T_seq − T_query))
```

| 版本      | query       | query_padded | 补零区域                                                          |
| --------- | ----------- | ------------ | ----------------------------------------------------------------- |
| baseline  | [4096, 188] | [4096, 216]  | 后 28 维（first_cate_id 8 + second_cate_id 8 + third_cate_id 12） |
| seq_align | [4096, 216] | [4096, 224]  | 后 8 维（仅 ts）                                                  |

______________________________________________________________________

### 10d. 逐位置 Attention MLP（阶段 4）

对序列每个位置 i ∈ [0, 9]：

```
q_i = query_padded                     [4096, T_seq]   ← 已补零对齐
s_i = sequence[:, i, :]                [4096, T_seq]   ← seq 第 i 位
```

四路拼接：

```
input_i = concat(q_i, s_i, q_i − s_i, q_i × s_i)

dim:       [T_seq] + [T_seq] + [T_seq] + [T_seq] = [T_seq × 4]
baseline:  [216]  + [216]   + [216]    + [216]    → [864]
seq_align: [224]  + [224]   + [224]    + [224]    → [896]
```

MLP 三层（与 T_seq 无关，结构固定）：

```
input_i           [4096, T_seq × 4]
  ↓ Linear + Dice
h1                [4096, 128]
  ↓ Linear + Dice
h2                [4096, 64]
  ↓ Linear
score_i           [4096, 1]              ← 第 i 位置的注意力分数
```

______________________________________________________________________

### 10e. Softmax + 加权求和（阶段 5）

```
scores = stack([score_0, ..., score_9])  [4096, 10]
weights = softmax(scores)                [4096, 10]    ← 每样本权重和 = 1
```

```
user_interest = Σ_i(weights[:, i] × sequence[:, i, :])
              = [4096, T_seq]            ← 输出给后续网络
```

______________________________________________________________________

### 10f. 全流程 Shape 总览

```
特征嵌入 → 拼接 → 补零 → 逐位置 MLP → Softmax → 加权求和

target 19/22 feat    seq 20 feat
      │                  │
      ▼                  ▼
  [4096, T_query]   [4096, 10, T_seq]
      │                  │
      └── F.pad ──► [4096, T_seq]
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
    q_i [T_seq]     s_i [T_seq]     s_i [10, T_seq]
        │               │               │
        └──── concat(q, s, q−s, q×s) ───┘
                        │
                  [4096, T_seq × 4]
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
         Linear(→128)        Dice
              ▼                   ▼
         Linear(→64)         Dice
              ▼
         Linear(→1)
              ▼
         score_i [4096, 1]     ← 10 次循环
              ▼
         scores [4096, 10] → Softmax → weights [4096, 10]
              ▼
         user_interest = sum(weights × sequence) [4096, T_seq]
              ▼
         送入 PLE / DCN / task_towers
```

______________________________________________________________________

### 10g. item_id vs title_vector 在 DIN 中的角色

|                | item_id (target→seq)                                                                               | title_vector                                       |
| -------------- | -------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| Embedding 方式 | target: EmbeddingLookup(3M×32) / seq: EmbeddingLookup(**1.96M×24** baseline / **3M×32** seq_align) | 无 Embedding，128 维直接输入                       |
| 参数量         | target: 96M / seq: 47M(baseline) or 96M(seq_align)                                                 | 0 参数                                             |
| 参数更新       | ✅ 两侧均通过 BP 训练                                                                              | ❌ 冻结                                            |
| 在 T 中的占比  | target: 32/188(17%) / seq: 24/216(11%) baseline → 32/224(14%) seq_align                            | target: 128/216(59%) / seq: 128/224(57%) seq_align |
| 语义来源       | 纯数据驱动，同现关系学习                                                                           | 预训练 sentence embedding，语义先验                |
| DIN pad 影响   | baseline: target(32) > seq(24)，差 8 维补零; seq_align: 一致                                       | 两侧同为 128 维，无需对齐                          |

______________________________________________________________________

## 11. 训练 vs 推理 — 完整对比

### 11a. 数据路径

```
┌─────────────────────────────────────────────────────────────┐
│ 训练                                                        │
│                                                             │
│ pre_t_seq (T-1 全量历史, WM_CONCAT_BY_SORT)                 │
│   + t_seq (当天, RT_SEQ_FEATURE)                            │
│   → all_seq_feat (SINGLE_SEQ_REPLENISH) → 6 种完整序列      │
│   + fix_sample_v3 → training_set (用户/商品/交叉统计)        │
│   → JOIN → pyfg101 编码 → TFRecord → EasyRec 训练           │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│ 推理                                                        │
│                                                             │
│ t_seq (实时行为, RT_SEQ_FEATURE)                             │
│   → all_seq_feat (仅有 t_seq 序列, pre_t_seq 缺)             │
│   + 实时 item_info + user_info                               │
│   → pyfg101 编码 → TFRecord → EasyRec scoring                │
└─────────────────────────────────────────────────────────────┘
```

### 11b. item_id 对比

| 阶段         | 训练                                                         | 推理                       |
| ------------ | ------------------------------------------------------------ | -------------------------- |
| item_id 来源 | training_set.item_id (STRING)                                | 实时请求 item_id           |
| 序列来源     | pre_t_seq click_10 + t_seq click_50 补齐                     | t_seq click_50 截取 10     |
| FG 编码      | id_feature → hash int64                                      | 完全相同                   |
| Embedding 表 | target: 3M×32=96M + seq: 1.96M×24=47M，共 143M 参数，BP 更新 | 已冻结的 checkpoint        |
| DIN 行为     | target + sequence attention                                  | 完全相同                   |
| 序列长度     | 固定 10 (pad 补齐)                                           | 固定 10 (pad 补齐，数据少) |

### 11c. title_vector 对比

| 阶段              | 训练                                                      | 推理                               |
| ----------------- | --------------------------------------------------------- | ---------------------------------- |
| title_vector 来源 | training_set.title_vector ARRAY\<DOUBLE>                  | 实时 item_basic_info_preprocess_v3 |
| 序列来源          | pre_t_seq WM_CONCAT_BY_SORT + t_seq RT_SEQ_FEATURE → 补齐 | t_seq RT_SEQ_FEATURE 截取          |
| FG 编码           | raw_feature → 128 float                                   | 完全相同                           |
| 参数              | 0 参数，预训练值透传                                      | 0 参数                             |
| DIN 行为          | target 128-dim + sequence 10×128-dim attention            | 完全相同                           |

### 11d. 关键差异汇总

| 差异项        | 说明                                                                                                                                  |
| ------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| 行为数据范围  | 训练有 pre_t_seq (全量) + t_seq (当天)，推理只有 t_seq (当天)                                                                         |
| click_10 来源 | 训练: `click_50 截10 + pre_t 的 click_10` → 历史+当天补齐；推理: 仅 `click_50 截10` → 仅当天                                          |
| 特征值        | item_id 的表一致，title_vector 的表一致；推理时无 pre_t_seq 的"昨日遗忘"问题                                                          |
| FG 编码       | 完全相同（同一份 FG JSON）                                                                                                            |
| 模型参数      | item_id 的 Embedding 表（target 96M + seq 47M，**不同表不同维度**）在训练时更新，推理时冻结；启用 weight sharing 后统一为 1×3M×32=96M |

______________________________________________________________________

## 12. Weight Sharing: bag ↔ seq item_id embedding

### 12a. 为什么需要 weight sharing

- 序列侧 (seq) `item_id` 和目标侧 (bag/target) `item_id` 是同一个商品的 ID，但分属不同的 Embedding 表
- 两个表独立初始化、独立 BP，导致 bag 和 seq 的 `item_id` 落在不同向量空间
- DIN attention 本质是 target embedding 与 seq embedding 做 Dot-Product — 如果两个向量空间不统一，attention 打分失去物理意义

### 12b. 实现方案

**原理**: `EmbeddingGroup.__init__` 在构建完 bag 和 seq 的 `EmbeddingCollection` 后，检测哪些 `embedding_name` 同时出现在两者中。对匹配的 name，将 seq 的 `EmbeddingCollection` 中对应的 `nn.Embedding.weight` 替换为 bag 侧 `EmbeddingBagCollection` 中同一个 `nn.Parameter` 对象。

```python
# tzrec/modules/embedding.py:243-292
# 1) 收集 bag 侧和 seq 侧的 embedding name
bag_names = set(bag_impl.ebc.embedding_bags.keys())
if hasattr(bag_impl, "mc_ebc"):
    bag_names.update(bag_impl.mc_ebc._embedding_module.embedding_bags.keys())
    #               ^^^^^^^^^^^^^^ 注意：MC wrapper 不暴露 embedding_bags，
    #                               需过 _embedding_module 访问内部 EBC

seq_names = set()
for ec in seq_impl.ec_dict.values():
    seq_names.update(ec.embeddings.keys())
for ec in seq_impl.mc_ec_dict.values():
    seq_names.update(ec._embedding_module.embeddings.keys())

# 2) 对同名的 embedding，alias seq 的 weight → bag 的 weight
for name in bag_names & seq_names:
    bag_weight = (
        bag_impl.ebc.embedding_bags[name].weight
        if name in bag_impl.ebc.embedding_bags
        else bag_impl.mc_ebc._embedding_module.embedding_bags[name].weight
    )
    for ec in seq_impl.ec_dict.values():
        if name in ec.embeddings:
            seq_emb = ec.embeddings[name]
            assert seq_emb.weight.shape == bag_weight.shape
            seq_emb.weight = bag_weight  # 同一个 Parameter 对象
    for ec in seq_impl.mc_ec_dict.values():
        if name in ec._embedding_module.embeddings:
            seq_emb = ec._embedding_module.embeddings[name]
            assert seq_emb.weight.shape == bag_weight.shape
            seq_emb.weight = bag_weight
```

这样:

- bag 和 seq 共用同一份 3M×32 的权重矩阵
- BP 时两个路径的梯度都累加到这个共享权重上
- 推理时只有一个权重 (checkpoint 中只存一份)

**前提条件**: 两者的 `hash_bucket_size` 和 `embedding_dim` 必须完全一致 (代码中有 assert 校验)。

**注意**: `ManagedCollisionEmbeddingBagCollection` (MC wrapper for ZCH emb) 不直接暴露 `embedding_bags`/`embeddings` 属性，需通过 `_embedding_module` 访问内部的 `EmbeddingBagCollection`/`EmbeddingCollection`。同理 `ManagedCollisionEmbeddingCollection` (seq 侧的 MC wrapper) 也用 `_embedding_module`。

### 12c. 配置变更

**目标侧 (bag, 原有)** — 无变化:

```protobuf
id_feature {
    feature_name: "item_id"
    expression: "item:item_id"
    embedding_dim: 32
    hash_bucket_size: 3000000
}
```

默认 `embedding_name = "item_id_emb"` (由 `f"{feature_name}_emb"` 推导)。

**序列侧 (seq, 需新增)** — 所有 6 个序列的 `item_id` 统一加一行:

```protobuf
id_feature {
    feature_name: "item_id"
    embedding_name: "item_id_emb"          # ← 新增，覆盖默认 "click_10_seq__item_id_emb"
    expression: "item:item_id"
    embedding_dim: 32
    hash_bucket_size: 3000000
}
```

若不加 `embedding_name`，seq 侧默认名称为 `"click_10_seq__item_id_emb"`，不会被自动检测到。

### 12d. 效果分析

| 指标            | 无 weight sharing                     | 有 weight sharing          |
| --------------- | ------------------------------------- | -------------------------- |
| 参数量          | bag: 3M×32 + seq: 1.96M×24 = **143M** | 1×3M×32 = **96M**          |
| 向量空间        | bag ↔ seq **不同空间**                | bag ↔ seq **同一空间**     |
| DIN Dot-Product | bag v.s. seq 向量无直接可比性         | 语义一致，Attention 更合理 |
| 梯度            | bag 和 seq 独立更新                   | 两个路径的梯度共享累加     |
| 模型大小        | checkpoint 中存两份权重               | checkpoint 中存一份        |

开启 weight sharing 后 CVR 预期回升（缓解 seq 侧 1.96M→3M 的稀疏过拟合）。

### 12e. DMP (Distributed Model Parallel) 兼容性

**问题**: `seq_emb.weight = bag_weight` 使 bag `EmbeddingBagCollection` 和 seq `EmbeddingCollection` 指向同一个 `nn.Parameter` 对象。DMP 的 `sparse_parameters()` (Queue 遍历所有子模块) 会分别采集 bag 和 seq 的 `named_parameters()`，同一 tensor 被收集两次 → `apply_optimizer_in_backward` 重复 stamp → `_optimizer_classes = [Adam, Adam]` → DMP sharder `create_grouped_sharding_infos` 断言 `len(optimizer_classes) == 1` 失败，报 `AssertionError: Only support 1 optimizer`。

**修复** (`tzrec/models/model.py:192-210`): `sparse_parameters()` 返回前按 `id(p)` 去重:

```python
seen_ids = set()
deduped_trainable = []
for p in trainable_parameters_list:
    pid = id(p)
    if pid not in seen_ids:
        seen_ids.add(pid)
        deduped_trainable.append(p)
```

**局限**: DMP 会分别替换 bag EBC → `ShardedEmbeddingBagCollection` 和 seq EC → `ShardedEmbeddingCollection`，各自创建独立的分布式参数。虽然 `_optimizer_classes` 不再重复，但 DMP 无法保持 parameter 别名关系 — bag 和 seq 的权重在分布式训练中独立更新、逐步漂移。

实际影响：

- **初始化一致**：两者从同一份预训练权重开始（约等于 weight sharing 起点）
- **训练中漂移**：梯度独立作用在不同 shard 上，权重缓慢偏离
- **效果**：item_id embedding 维度高（32×3M），漂移速度慢，能保持大部分共享信号。dim alignment + cate alignment 的收益不受影响
- **后续**：true weight sharing (同一个 shard 合并梯度更新) 需要定制 TorchRec planner/sharder，当前版本未实现

______________________________________________________________________

## 13. 实时流处理 (Flink SQL)

### 13a. `mmb_id_all_seq_feat_v1_flink.sql` — 实时行为事件写入

**文件**: `home_flow_2604_mmb_id_all_seq_feat_v1_flink.sql` (70 行)

**角色**: 将 SLS 实时用户行为日志以原始事件格式写入 FeatureStore，用于在线推理时实时序列拼接。

**数据流**:

```
SLS (mmb-zhekou-log/user-bhv-log)
  │ connector = 'sls', query: user_id/doc_id 非空
  ▼
rec_realtime_user_bhv (View)
  │ __tag__['__receive_time__'] → event_time
  │ bhv_type → event
  │ doc_id → item_id
  │ user_id → mmb_id
  ▼
mmb_id_all_seq_feat (FeatureStore Sink)
  │ 只写入: event_time, event, item_id, mmb_id
  │ 过滤: WHERE event IN ('click','conversion','favorite')
  │ 表: home_flow_2604_mmb_id_all_seq_feat_v1
  │ FeatureStore project: feature_mall
```

**与 v3 批处理的差异**:

| 维度       | v3 批处理 (all_seq_feat_v3.sql)        | v1 Flink (\_flink.sql) |
| ---------- | -------------------------------------- | ---------------------- |
| 计算引擎   | ODPS MaxCompute, 每日一次              | Flink, 实时流          |
| 输出       | 120 列 (20属性×6序列) 的序列特征       | 4 列原始事件           |
| 序列化逻辑 | `SINGLE_SEQ_REPLENISH` 合并同天+前一天 | **不做序列化**         |
| 用途       | 离线训练样本                           | 在线推理实时事件源     |

**在线推理时**: FeatureStore 根据 v1 表中原始事件实时拼接用户近期行为序列。Flink 只写 4 列原始事件的原因是——**序列化逻辑由 FeatureStore Go SDK 完成**，而非 SQL。

______________________________________________________________________

### 13b. `statistic_real_time_feature_to_fs_v1.sql` — 实时统计特征

**文件**: `home_flow_2604_statistic_real_time_feature_to_fs_v1.sql` (83 行)

**角色**: 同源 SLS 输入，计算滑动窗口统计特征，输出到两个 FeatureStore 表。

**数据流**:

```
SLS (同源)
  ▼
rec_realtime_user_bhv (event_time, event, item_id, mmb_id, request_id)
  ▼ LEFT JOIN item_basic_info_preprocess_v1 (FeatureStore, FOR SYSTEM_TIME AS OF PROCTIME())
  ▼
rec_realtime_user_bhv_wide_v1 (含20+ item属性: cate_id_path, brand, ...)
  ▼ GROUP BY group_key (HashBucket(mmb_id, 2))
  ▼ MessageDelay(ARRAY[mmb_id,item_id,event,...,username], event_time,
  │             ARRAY[3600,10800,43200,86400], group_key, event_filter)
  ▼
rec_realtime_user_bhv_wide_delay_v1 (延迟信息注入, 含delay_flag)
  │
  ├──→ GROUP BY item_id
  │       └── SWCountCatesKVS → item__cnt_click/conversion/favorite_rt{1h,3h,12h,24h}
  │       └── Sink: home_flow_2604_item_id_rt_statistic_feat (FeatureStore)
  │
  └──→ GROUP BY mmb_id
          └── SWCountCatesKVS → user__kv_{attr}_{behav}_rt{1h} (20属性×3行为)
          └── Sink: home_flow_2604_mmb_id_rt_statistic_feat (FeatureStore)
```

**两个输出表**:

| 输出表                      | 维度              | 窗口                | 特征示例                                                        |
| --------------------------- | ----------------- | ------------------- | --------------------------------------------------------------- |
| `item_id_rt_statistic_feat` | item 行为计数     | 1h, 3h, 12h, 24h    | `item__cnt_click_rt1h`, `item__cnt_conversion_rt24h`            |
| `mmb_id_rt_statistic_feat`  | user 行为 KV 特征 | 1h (含20属性×3行为) | `user__kv_item_id_click_rt1h`, `user__kv_brand_conversion_rt1h` |

**关键实现细节**:

- `MessageDelay` UDF: 解决实时流中事件乱序/延迟到达问题，支持 4 个延迟窗口 (1h/3h/12h/24h) 的事件重新分配
- `SWCountCatesKVS` UDF: 滑动窗口计数，窗口内按类别聚合为 KV 对
- `HashBucket(mmb_id, 2)`: 双 bucket 保证因果一致性，同时提升并行度

**安全问题**: 两份 Flink SQL 均在 SQL 中硬编码了 SLS/FeatureStore 的 `accessId` 和 `accessKey`，应替换为 RAM Role。

______________________________________________________________________

## 14. 离线→在线同步: Python Sync Script

### 14a. `create_sync_onlinestore.py` — 特征视图创建与同步

**文件**: `home_flow_2604_mmb_id_all_seq_feat_v3_create_sync_onlinestore.py` (163 行)

**角色**: 连接 FeatureStore PaaS 服务，创建序列特征视图并将离线 MaxCompute 数据同步到在线存储。

```python
# 核心调用链:
fs = FeatureStoreClient(access_key_id, access_key_secret, endpoint='paifeaturestore-vpc.cn-shenzhen.aliyuncs.com')
project = fs.get_project('feature_mall')

# 创建序列特征视图 (如果不存在)
cur_feature_view = project.create_sequence_feature_view(
    name='home_flow_2604_mmb_id_all_seq_feat_v3',
    datasource=MaxComputeDataSource(
        table='home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1_agg'
    ),
    event_time='event_unix_time',          # ✓ 源表的 event_time 列名
    item_id='item_id',
    event='event',
    deduplication_method=1,                # [mmb_id, item_id, event] 去重
    sequence_feature_config=sequence_feature_config_list,  # 120 个列映射
    sequence_table_config=SequenceTableConfig(             # 在线表配置
        table_name='home_flow_2604_mmb_id_all_seq_feat_v3',
        primary_key='mmb_id',
        event_time='request_id'             # ⚠️ 见 14b 分析
    ),
    entity='user',
    ttl=15552000  # ≈ 180天
)

# 同步数据
task = cur_feature_view.publish_table(partitions={'dt': cur_day}, mode='Overwrite', direct_sync=True)
```

**120 个 SequenceFeatureConfig 的映射逻辑**:

离线 v3 的 20 个属性列（item_id, cate_id_path, brand, ..., title_vector, ts）× 6 个序列长度（click_10, click_50, conversion_5, conversion_20, favorite_5, favorite_10）= 120 个 `offline_seq_name`。每个配置指定：

- `offline_seq_name`: 离线 FS feature view 中该列的名称
- `seq_event`: 行为类型过滤 (click / conversion / favorite)
- `online_seq_name`: 在线序列名称，20 个属性共享同一个名称
- `seq_len`: 序列最大长度

**为什么 20 个属性列映射到同一个 online_seq_name**:

FeatureStore 在线存储不以 120 列平铺方式存储，而是存为**结构化事件列表**:

```
离线 120 列:                                  在线结构化事件:
click_10_seq__item_id:  "A;B;C"               click_10_seq = [
click_10_seq__brand:    "Nike;Adidas;..."       {item_id:"A", brand:"Nike", cate_id_path:"...", ...},
click_10_seq__cate_id_path: "..."               {item_id:"B", brand:"Adidas", ...},
...                                              {item_id:"C", ...}
                                              ]
```

**datasource 为何只需要 5 列**:

datasource `pre_t_agg_v1_agg` 只含 `event_unix_time, event, item_id, scene, mmb_id` 5 列——这是**有意为之**。FS 的 `create_sequence_feature_view` 的工作方式是：

1. 从 datasource 读取原始事件：只需 `event_unix_time`（排序/去重）、`event`（类型过滤）、`item_id`、`mmb_id`（分组键）
1. 按 `mmb_id` 分组、按 `event_unix_time` 排序
1. 在线查询时，FS 通过 `item_id` **自动关联 item feature view**，获取 `cate_id_path`, `brand`, `title_vector` 等商品属性
1. 返回结构化事件列表给模型 FG 层

所以 `SequenceFeatureConfig` 中声明 `cate_id_path`、`brand`、`title_vector` 等列，是在告诉 FS"在线序列中我需要这些字段，请从 item feature view 获取"，而非要求在 datasource 中存在。

这种设计解耦了行为数据（聚合去重的 5 列）和商品属性数据（item feature view），避免了数据的冗余存储。

**TTL**: `15552000` 秒 ≈ 180 天。FS 根据 event_time 字段判断数据年龄并自动淘汰过期数据。

______________________________________________________________________

### 14b. ⚠️ `SequenceTableConfig.event_time='request_id'` 配置错误分析

#### 问题描述

```python
create_sequence_feature_view(
    ...,
    event_time='event_unix_time',    # line 159: ✓ 源表列名
)

seq_table_config = SequenceTableConfig(
    ...,
    event_time='request_id'          # line 156: ⚠️ 在线表列名
)
```

两个 `event_time` 参数角色不同：

| 参数位置                            | 作用                             | 当前值            | 正确性  |
| ----------------------------------- | -------------------------------- | ----------------- | ------- |
| `create_sequence_feature_view(...)` | 指定**源表**中哪列是事件时间戳   | `event_unix_time` | ✅ 正确 |
| `SequenceTableConfig(...)`          | 指定**在线表**中事件时间列的名称 | `request_id`      | ⚠️ 错误 |

#### 影响范围评估

**业务逻辑: 不受影响** ✅

`create_sequence_feature_view` 中的 `event_time='event_unix_time'` 才是决定以下关键行为的配置:

| 行为                    | 配置来源                                                 | 影响                 | 正确性  |
| ----------------------- | -------------------------------------------------------- | -------------------- | ------- |
| 离线 Point-in-Time Join | `create_sequence_feature_view.event_time`                | 训练样本时间穿越防护 | ✅ 正确 |
| 在线序列排序            | `create_sequence_feature_view.event_time`                | DIN 时间顺序         | ✅ 正确 |
| 在线序列去重            | `create_sequence_feature_view.event_time` + dedup_method | 保留最新事件         | ✅ 正确 |

原因是 FS 引擎读取 `pre_t_agg_v1_agg` 源表时，按 `event_time='event_unix_time'` 获取 `event_unix_time` 列的值（epoch 时间戳，如 `1718400000`），然后将该值写入在线表中名为 `request_id` 的列。在线表的**列名错了但值是对的**：

```
源表: event_unix_time=1718400000         ← 正确的值
                           ↓
在线表: request_id=1718400000            ← 列名错了，但值正确
```

因此按时间排序、去重、TTL 计算都基于正确的 epoch 值运行。

**运维层面: 可能受影响** ⚠️

在线存储引擎（Hologres/TableStore）的 TTL 清理依赖物理表结构来判断"哪列是时间"。如果引擎只看列名（`request_id`）而非值：

- 列被推断为 `TEXT` → 无法与当前时间做比较 → **TTL 清理静默失效** → 在线存储数据无限膨胀
- 列被推断为 `BIGINT` → 值本身就是有效时间戳 → TTL 碰巧正常工作

**可维护性: 受影响** ⚠️

在线序列查询结果中 event_time 字段名为 `request_id`:

```json
{
  "click_10_seq": [
    {"item_id": "A", "request_id": 1718400000, ...}
  ]
}
```

排查问题时可能被误认为是真正的请求 ID，造成混淆。

#### 修复建议

```python
seq_table_config = SequenceTableConfig(
    table_name='home_flow_2604_mmb_id_all_seq_feat_v3',
    primary_key='mmb_id',
    event_time='event_unix_time'    # ← 修正
)
```

修改后重新执行 `publish_table(direct_sync=True)` 重建在线表的列名索引。

______________________________________________________________________

## 15. `pre_t_agg_v1_agg.sql` — 行为数据二次聚合（FS 同步专用）

**文件**: `home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1_agg.sql` (56 行)

**角色**: 从 `pre_t_agg_v1`（自身仅 5 列）的 180 天分区中做第二层去重截断，产出 Python sync 脚本的 FeatureStore 数据源。

### 数据源全链

```
         ① preprocess_v1.sql         ② pre_t_agg_v1.sql           ③ pre_t_agg_v1_agg.sql
原始ODPS ───────────→ preprocess_v1 ──────────→ pre_t_agg_v1 ───────────→ pre_t_agg_v1_agg
行为日志  (10列, 当天)         (5列, 15天, 去重)         (5列, 180天, 再次去重)
                                                                           │
                                                                           ↓
                                                               Python sync → FeatureStore
```

### 三级去重对比

| 级别        | SQL                | 数据范围                                       | 去重键                     | 截断规则                  | 输出列  |
| ----------- | ------------------ | ---------------------------------------------- | -------------------------- | ------------------------- | ------- |
| L1 当天     | `preprocess_v1`    | dt = bizdate                                   | 无                         | 无                        | 10列    |
| L2 聚合     | `pre_t_agg_v1`     | bizdate-14 ~ bizdate                           | `[mmb_id, item_id, event]` | click≤50, conv≤20, fav≤10 | **5列** |
| L3 二次聚合 | `pre_t_agg_v1_agg` | bizdate-180 ~ bizdate 内用户最后活跃日往前15天 | `[mmb_id, item_id, event]` | 同上                      | **5列** |

### `_agg` SQL 逻辑

```sql
CREATE TABLE ... LIKE home_flow_2604_dwd_log_zhekou_rec_user_bhv_info_pre_t_agg_v1
-- LIKE 继承 schema: 5 列 (event_unix_time, event, item_id, scene, mmb_id)

INSERT OVERWRITE TABLE ..._agg PARTITION(dt='${bdp.system.bizdate}')
SELECT sq2.event_unix_time, sq2.event, sq2.item_id, sq2.scene, sq2.mmb_id

-- 内层: 180天分区, [mmb_id, item_id, event] 去重
INNER JOIN (SELECT mmb_id, MAX(dt) user_last_dt FROM pre_t_agg_v1 ... GROUP BY mmb_id)
  ON sq0.mmb_id = last_dt.mmb_id
  AND sq0.dt > user_last_dt - 15   -- 只看用户最近活跃日往前15天

-- 外层: [mmb_id, event] 截断 Top N
WHERE rnk <= CASE event WHEN 'click' THEN 50 WHEN 'conversion' THEN 20 WHEN 'favorite' THEN 10 END
```

**schema 设计**: `pre_t_agg_v1` 的 schema 只有 5 列（`event_unix_time, event, item_id, scene, mmb_id`），`_agg` (LIKE) 继承相同 schema。`cate_id_path`, `brand`, `title_vector` 等商品属性不在此表中——它们由 FS 在线查询时通过 `item_id` 自动关联 item feature view 获取（详见 §14a 分析）。

______________________________________________________________________

## 16. 完整离线+在线架构总结

### 16a. 三路数据管线

```
                    ┌──────────────────────────────────────┐
                    │   SLS user-bhv-log (实时行为日志)       │
                    └────────────────┬─────────────────────┘
                                     │ Flink
                   ┌─────────────────┼──────────────────┐
                   ▼                 ▼                   │
        ┌──────────────────┐ ┌──────────────────┐       │
        │ all_seq_feat_v1  │ │ statistic_rt_v1  │       │
        │ (原始事件)       │ │ (滑动窗口统计)    │       │ ODPS
        └────────┬─────────┘ └────────┬─────────┘       │ 每日批次
                 │                    │                  │
                 ▼                    ▼                  ▼
        ┌────────────────────────────────────────────────────┐
        │              FeatureStore 在线特征存储              │
        │  item_info | user_profile | rt_stat | seq_events  │
        └────────────────────────────────────────────────────┘
                          ▲
                          │ create_sync_onlinestore.py
                          │ (pre_t_agg_v1_agg 为数据源)
                          │
        ┌─────────────────┴────────────────────────────────┐
        │             ODPS 离线批处理                       │
        │  ① item_basic_info_preprocess_v3 (商品画像)       │
        │  ② mmb_id_t_seq_v3 (当天行为序列)                 │
        │  ③ mmb_id_pre_t_seq_v3 (前一天行为序列)           │
        │  ④ mmb_id_all_seq_feat_v3 (合并为6种完整序列)     │
        │  ⑤ fix_sample_v3 (组装训练样本)                    │
        │  ⑥ fg_v3.json + pyfg_encoded_v3 (FG编码)        │
        └─────────────────────────────────────────────────┘
```

### 16b. 文件职能总结

| 文件 | 角色 | 输入 | 输出 | 运行方式 |
|\---|---|---|---|---|---|
| `preprocess_v1.sql` | 行为日志清洗 | 原始ODPS行为表 | `preprocess_v1` (10列) | ODPS 一日一次 |
| `pre_t_agg_v1.sql` | 行为预聚合 | `preprocess_v1` 15天 | `pre_t_agg_v1` (5列) | ODPS 一日一次 |
| `pre_t_agg_v1_agg.sql` | 行为二次聚合 | `pre_t_agg_v1` 180天 | `_agg` (5列) | ODPS 一日一次 |
| `item_basic_info_preprocess_v3.sql` | 商品画像 | 原始商品表 + title_vector | `item_preprocess_v3` (30+列) | ODPS 一日一次 |
| `mmb_id_t_seq_v3.sql` | 当天行为序列 | `preprocess_v1` + 商品画像 | `t_seq` (3种×21列) | ODPS 一日一次 |
| `mmb_id_pre_t_seq_v3.sql` | 前一天行为序列 | `pre_t_agg_v1` + 商品画像 | `pre_t_seq` (6种×21列) | ODPS 一日一次 |
| `mmb_id_all_seq_feat_v3.sql` | 序列合并 | `t_seq` + `pre_t_seq` | 完整序列 (120列) | ODPS 一日一次 |
| `fix_sample_v3.sql` | 训练样本 | 曝光日志 + 各种特征 | `training_set` | ODPS 一日一次 |
| `fg_v3.json` | FG 特征配置 | (声明式定义) | FG 编码规则 | pyfg101 引用 |
| `pyfg_encoded_v3` | FG 执行器 | FG JSON | TFRecord | ODPS 一日一次 |
| `_flink.sql` (seq) | 实时行为写 FS | SLS | FeatureStore raw events | Flink 流 |
| `_flink.sql` (stat) | 实时统计特征 | SLS + item_info | FS rt_stat tables | Flink 流 |
| `create_sync_onlinestore.py` | 离线→在线同步 | `_agg` (5列) | FS 在线序列视图 | ODPS Python |

### 16c. 已知问题和注意事项

| #   | 问题                                                                  | 文件                                | 影响                        | 修复优先级 |
| --- | --------------------------------------------------------------------- | ----------------------------------- | --------------------------- | ---------- |
| 1   | `SequenceTableConfig.event_time='request_id'`                         | `create_sync_onlinestore.py:156`    | 在线表列名错误，TTL可能失效 | 高         |
| 2   | Flink SQL 硬编码 accessKey                                            | `_flink.sql:26-27` (两个文件)       | 安全风险                    | 高         |
| 3   | `item_basic_info_preprocess_v3.sql` ALTER TABLE v1 表却写入 v3 schema | `item_basic_info_preprocess_v3.sql` | 建表/插表不匹配             | 中         |
| 4   | 硬编码日期 `dt >= '20260604'`                                         | `item_basic_info_preprocess_v3.sql` | 定时任务过时失效            | 低         |
