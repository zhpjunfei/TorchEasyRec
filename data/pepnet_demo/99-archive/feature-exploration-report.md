______________________________________________________________________

## date: 2026-05-30 tags: [archive, feature, exploration] status: archived related: ["[[../30-data/sample-v3-pipeline]]"]

# 推荐系统特征勘探报告

## 📊 表结构概览

**表名**: `feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set`

**分区字段**: `dt STRING`

**存储格式**: ORC

**生命周期**: 90天

______________________________________________________________________

## 🗂️ 特征分类体系

### 1. 基础信息特征 (Basic Info)

| 特征名            | 类型   | 说明       |
| ----------------- | ------ | ---------- |
| `event_unix_time` | BIGINT | 曝光时间戳 |
| `item_id`         | STRING | 商品ID     |
| `mmb_id`          | STRING | 用户ID     |
| `request_id`      | STRING | 请求ID     |
| `scene`           | STRING | 场景       |
| `page`            | STRING | 页面       |
| `is_click`        | BIGINT | 是否点击   |
| `is_conversion`   | BIGINT | 是否转化   |

### 2. 用户画像特征 (User Profile)

- **人口属性**: `gender`, `age_group`, `reg_type`, `mmb_level`
- **行为属性**: `user_status`, `mmb_status`, `intergral`, `gold_coin`
- **订阅偏好**: `is_subscribe_discount`, `is_subscribe_savemoney`, `is_subscribe_clockin`
- **推送设置**: `receive_push`, `is_not_disturb`, `is_atpush`
- **地理信息**: `province`, `city`, `area_code`, `login_province`, `login_city`
- **设备信息**: `sdk_version`, `app_version`, `os_type`, `os_version`, `dev_brand`, `dev_model`

### 3. 商品属性特征 (Item Attributes)

- **基础信息**: `item_type`, `cate`, `cate_id_path`, `brand`, `spu_id`, `core_entity`
- **价格信息**: `current_price`, `price_tag`, `discount_intensity`, `discount_type`
- **内容信息**: `title`, `sub_title`, `keyword`, `tags`, `related_goods_ids`
- **店铺信息**: `dianpufensi`, `dianpupingfen`, `shop_id`, `publish_user`, `username`
- **分类层级**: `first_cate_id`, `second_cate_id`, `third_cate_id`

### 4. 时间特征 (Temporal Features)

| 特征名      | 类型   | 计算逻辑                              |
| ----------- | ------ | ------------------------------------- |
| `day_h`     | BIGINT | 曝光时刻的小时                        |
| `week_day`  | BIGINT | 曝光时刻的星期                        |
| `pub_hours` | DOUBLE | `(event_unix_time - pub_time) / 3600` |
| `reg_days`  | DOUBLE | 用户注册天数                          |

### 5. 统计特征 (Statistical Features)

#### 5.1 用户维度统计 (User Stats)

- **15天统计**: `user__cnt_favorite_15d`, `user__cnt_conversion_15d`, `user__cnt_click_15d`
- **KV特征**: `user__kv_*_click_15d`, `user__kv_*_conversion_15d`, `user__kv_*_favorite_15d` (多个维度)

#### 5.2 物品维度统计 (Item Stats)

- **多时间窗口**: 15d/3d/1d/rt1h/rt3h/rt12h/rt24h
- **统计指标**: cnt (计数), ratio (比率)

#### 5.3 交叉维度统计 (Cross Stats)

- **性别维度**: `gender__ratio_*_15d`, `gender__kv_ratio_*_15d`
- **年龄维度**: `age_group__ratio_*_15d`, `age_group__kv_ratio_*_15d`
- **城市维度**: `login_city__ratio_*_15d`, `login_city__kv_ratio_*_15d`
- **设备品牌**: `dev_brand__ratio_*_15d`, `dev_brand__kv_ratio_*_15d`
- **类目维度**: `first_cate_id`, `second_cate_id`, `cate_id_path`, `brand`, `site`, `core_entity`, `price_tag`, `promotion_channel`, `discount_intensity`, `dianpupingfen`, `pinpaidengji`, `spu_id`, `publish_user`, `username`

### 6. 序列特征 (Sequence Features)

| 特征前缀            | 序列长度 | 包含字段                                       |
| ------------------- | -------- | ---------------------------------------------- |
| `click_10_seq`      | 10       | item_id, cate_id_path, brand, price_tag, ts 等 |
| `click_50_seq`      | 50       | item_id, cate_id_path, brand, price_tag, ts 等 |
| `conversion_5_seq`  | 5        | item_id, cate_id_path, brand, price_tag, ts 等 |
| `conversion_20_seq` | 20       | item_id, cate_id_path, brand, price_tag, ts 等 |
| `favorite_5_seq`    | 5        | item_id, cate_id_path, brand, price_tag, ts 等 |
| `favorite_10_seq`   | 10       | item_id, cate_id_path, brand, price_tag, ts 等 |

### 7. Embedding特征

- `title_vector` (ARRAY<DOUBLE>)
- `sub_title_vector` (ARRAY<DOUBLE>)

### 8. 交叉特征 (Cross Features)

- `brand_x_price_tag`
- `brand_x_cate_id_path`
- `brand_x_gender`
- `brand_x_age_group`
- `cate_id_path_x_gender`
- `cate_id_path_x_age_group`

### 9. 标签与偏好特征 (Tag & Preference)

- **用户标签**: `bhv_gender`, `cate_prefer`, `crowd_prefer`, `bhv_time`, `consume_power`, `price_prefer`, `city_level`, `city_region`, `site_prefer`, `active_days`, `active_bhv`
- **商品标签**: `shop_type`, `shop_subtype`, `comment_tag`, `sales_month_tag`, `top_tag`, `item_class_prefer`, `item_audience_prefer`, `item_gender_prefer`, `potential_score`, `srh_hot`, `price_drop_freq`, `item_comment_tag`, `shop_life_time`, `his_high_level`

### 10. 请求解析特征

- `f_req_page`: 从 scene 字段解析的请求页面
- `f_req_domain`: 从 scene 字段解析的请求域

______________________________________________________________________

## 📈 pub_hours 特征深度分析

### 分布统计结果

| 指标               | 值          |
| ------------------ | ----------- |
| **P50**            | 8.57 小时   |
| **P75**            | 21.59 小时  |
| **P90**            | 33.52 小时  |
| **P95**            | 41.00 小时  |
| **P99**            | 48.29 小时  |
| **Mean**           | 13.69 小时  |
| **Stddev**         | 26.71 小时  |
| **Total Elements** | 158,408,486 |

### 分布特征解读

1. **右偏长尾分布**: Mean (13.69) > Median (8.57)，说明存在少量"老品"拉高了均值
1. **新品主导**: 50% 的商品在曝光前 8.5 小时内发布
1. **时效性窗口**: 90% 的商品在 33.5 小时内发布
1. **长尾截断**: P99 为 48.29 小时，建议对 >48h 的样本做特殊处理

### 分桶分布分析

```sql
CASE
    WHEN pub_hours <= 1 THEN '0-1h_新品爆发期'
    WHEN pub_hours <= 6 THEN '1-6h_热品爬坡期'
    WHEN pub_hours <= 24 THEN '6-24h_稳定曝光期'
    WHEN pub_hours <= 72 THEN '24-72h_长尾衰减期'
    ELSE '72h+_陈旧品'
END AS pub_hour_bucket
```

### 与 Label 的关联分析

| pub_hours_bin | PV        | CTR       | CVR        | CTR_Delta         |
| ------------- | --------- | --------- | ---------- | ----------------- |
| 0h 桶         | 4,515,624 | 3.47%     | 34.65%     | +0.15%            |
| 2h 桶         | 2,288,124 | **3.79%** | 34.91%     | **+0.32%** (峰值) |
| 4h 桶         | 1,672,973 | 3.66%     | 33.92%     | -0.13%            |
| 48h 桶        | 52,774    | **2.31%** | **38.95%** | **-0.59%**        |

**关键发现**:

- **CTR 峰值**: 在 2 小时桶达到峰值 3.79%（新品红利效应）
- **CVR 峰值滞后**: CVR 峰值在 16-20 小时（用户决策需要时间）
- **长尾衰减**: >24h 后 CTR 持续下降
- **48h 桶样本量骤降**: 统计显著性不足

### 反查样本处理方案对比

|                       | LEAST（钳位到 0） | ABS（取绝对值）  |
| :-------------------- | :---------------: | :--------------: |
| 离线 `pub_hours`      |         0         |    2（虚构）     |
| 线上 `pub_hours`      |         0         |    1（错位）     |
| 新品桶(0h)污染        |     略微稀释      |      不污染      |
| Training-Serving Skew |        无         | **有**（值偏移） |

**结论**：`pub_hours < 0` 的真实原因是维表 `pub_time` 被运营编辑操作更新而导致的 anti-time-travel 问题。应该在 SQL 层通过 `dt <= bizdate-1` + `ORDER BY fs_write_time DESC` 防护。当前兜底方案采用 **LEAST** 而非 ABS，避免虚构值时带来的 TS-Skew。

**`is_reedited_after_exposure` 角色**：梯度调节器而非预测特征。离线标记不可信样本，线上永远为 0 不生效。不影响推理。

______________________________________________________________________

## 🔍 特征勘验 SQL 模板

### 基础分布统计

```sql
-- 特征覆盖率
SELECT
    COUNT(1) AS total_samples,
    COUNT(pub_hours) AS has_feature_samples,
    ROUND(COUNT(pub_hours) * 100.0 / COUNT(1), 2) AS coverage_rate
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}';

-- 分位数统计
SELECT
    PERCENTILE_APPROX(pub_hours, 0.5) AS p50,
    PERCENTILE_APPROX(pub_hours, 0.75) AS p75,
    PERCENTILE_APPROX(pub_hours, 0.9) AS p90,
    PERCENTILE_APPROX(pub_hours, 0.95) AS p95,
    PERCENTILE_APPROX(pub_hours, 0.99) AS p99,
    AVG(pub_hours) AS mean,
    STDDEV(pub_hours) AS stddev
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}'
  AND pub_hours IS NOT NULL;
```

### 业务分桶分析

```sql
SELECT
    CASE
        WHEN pub_hours <= 1 THEN '0-1h_新品爆发期'
        WHEN pub_hours <= 6 THEN '1-6h_热品爬坡期'
        WHEN pub_hours <= 24 THEN '6-24h_稳定曝光期'
        WHEN pub_hours <= 72 THEN '24-72h_长尾衰减期'
        ELSE '72h+_陈旧品'
    END AS pub_hour_bucket,
    COUNT(1) AS pv,
    COUNT(DISTINCT mmb_id) AS uv,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS pv_pct,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 4) AS ctr,
    ROUND(SUM(is_conversion) * 100.0 / NULLIF(SUM(is_click), 0), 4) AS cvr
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}'
GROUP BY
    CASE
        WHEN pub_hours <= 1 THEN '0-1h_新品爆发期'
        WHEN pub_hours <= 6 THEN '1-6h_热品爬坡期'
        WHEN pub_hours <= 24 THEN '6-24h_稳定曝光期'
        WHEN pub_hours <= 72 THEN '24-72h_长尾衰减期'
        ELSE '72h+_陈旧品'
    END
ORDER BY pub_hour_bucket;
```

### 连续分布与 Label 关联

```sql
SELECT
    FLOOR(pub_hours / 2) * 2 AS pub_hours_bin,
    COUNT(1) AS pv,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 4) AS ctr,
    ROUND(SUM(is_conversion) * 100.0 / NULLIF(SUM(is_click), 0), 4) AS cvr,
    ROUND(SUM(is_click) * 100.0 / COUNT(1) -
          LAG(SUM(is_click) * 100.0 / COUNT(1)) OVER (ORDER BY FLOOR(pub_hours / 2) * 2), 4) AS ctr_delta
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}'
  AND pub_hours IS NOT NULL
  AND pub_hours <= 72
GROUP BY FLOOR(pub_hours / 2) * 2
HAVING COUNT(1) >= 10000
ORDER BY pub_hours_bin
LIMIT 36;
```

### 数据质量检查

```sql
-- 异常值检查
SELECT
    COUNT(1) AS abnormal_count,
    ROUND(COUNT(1) * 100.0 / SUM(COUNT(1)) OVER (), 2) AS abnormal_rate
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}'
  AND (
    pub_hours IS NULL
    OR pub_hours < 0
    OR pub_hours > 720
  );

-- 负值样本分析
SELECT
    f_req_page,
    pub_hours < 0 AS is_reedited,
    COUNT(1) AS pv,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 4) AS ctr
FROM feature_mall_home_flow_2604_ctrcvr_sorter_v3_training_set
WHERE dt = '${bdp.system.bizdate}'
  AND pub_hours IS NOT NULL
  AND ABS(pub_hours) <= 24
GROUP BY f_req_page, pub_hours < 0
ORDER BY f_req_page, is_reedited;
```

______________________________________________________________________

## 💡 特征优化建议

### pub_hours 特征处理策略

#### 方案 A: 分段编码 (推荐)

```python
def encode_pub_hours(pub_hours):
    if pub_hours < 0:
        return "data_error"
    elif pub_hours <= 8:
        return "new_item"
    elif pub_hours <= 24:
        return "hot_item"
    elif pub_hours <= 48:
        return "long_tail"
    else:
        return "old_item"
```

#### 方案 B: 连续值变换

```python
pub_hours_transformed = torch.log1p(torch.relu(pub_hours))
```

#### 方案 C: 负值处理

```sql
CASE
    WHEN sq55.pub_time IS NULL OR sq55.pub_time = 0 THEN NULL
    WHEN sq0.event_unix_time < sq55.pub_time THEN 0
    ELSE (sq0.event_unix_time - sq55.pub_time) / 3600.0
END AS pub_hours

-- 辅助特征
IF(sq0.event_unix_time < sq55.pub_time, 1, 0) AS pub_time_after_exposure_flag
```

### 技术方案对比

| 方案         | 粒度 | 参数量 | 表达能力 | 推荐场景           |
| ------------ | :--: | :----: | :------: | ------------------ |
| 原始连续值   | 连续 |   低   | 低(线性) | 不推荐单独使用     |
| 分段编码     | 分段 |   中   |    中    | ✅ 当前业务最佳    |
| Log变换      | 连续 |   低   |  中偏上  | 适合非线性衰减     |
| 指数衰减权重 | 连续 |   低   |    高    | 适合与gate网络配合 |

## 📋 行动清单

### 立即执行

1. ✅ 排查 `pub_hours < 0` 的样本来源（时序错误或特殊业务）
1. ✅ 确认负值样本占比和 CTR 特征
1. ✅ 验证 48h+ 长尾样本的统计显著性

### 短期优化

1. ⏳ 在特征工程中对 `pub_hours` 做分段编码或 log 变换
1. ⏳ 增加 `pub_time_after_exposure_flag` 辅助特征
1. ⏳ 对 >48h 的样本做截断处理 `LEAST(pub_hours, 48)`

### 长期规划

1. 📅 将 `pub_hours` 与实时热度、用户消费力等特征交叉
1. 📅 构建更精细的时效性信号（如新品标识、热品标识）
1. 📅 在 PEPNet 中让 gate 网络动态学习 pub_hours 的权重

______________________________________________________________________

## 🎯 总结

**pub_hours 特征价值**:

- 强时效性特征，p50=8.57h 说明新品主导
- CTR 在 2h 达到峰值 3.79%，验证"新品红利"效应
- CVR 峰值滞后于 CTR（16-20h），符合用户决策规律
- > 24h 后 CTR 持续衰减，需做分段或截断处理

**建模策略**:

- 主特征：负值截断为 0，对齐线上分布
- 辅助特征：标识"曝光后被编辑"的业务信号
- 编码方式：分段编码 (0-8h, 8-24h, 24-48h, 48h+) 或 log 变换
- 交叉增强：与实时热度、用户消费力等特征交叉
