# 未使用特征完整清单

**分析日期**: 2026-10-17
**DDL 特征总数**: 211
**Config 已使用**: 196
**未使用特征**: 123
**Phase 1 已添加**: 15
**剩余未使用**: 108

______________________________________________________________________

## 一、Phase 1 已添加特征（15个）

### 比率特征（10个）

```
offline_order_brand_common_ratio
offline_order_first_cate_id_common_ratio
offline_order_second_cate_id_common_ratio
offline_chajia_brand_common_ratio
offline_chajia_first_cate_id_common_ratio
offline_chajia_second_cate_id_common_ratio
offline_search_click_brand_common_ratio
offline_search_click_first_cate_id_common_ratio
offline_search_click_second_cate_id_common_ratio
convert_probability
```

### 用户质量特征（5个）

```
consume_power
his_high_level
gold_coin
potential_score
srh_hot
```

______________________________________________________________________

## 二、未使用特征分类

### 2.1 比率特征（10个剩余）

#### 查价相关（5个）

```
offline_chajia_site_common_ratio
offline_chajia_third_cate_id_common_ratio
```

#### 收藏相关（5个）

```
offline_like_brand_common_ratio
offline_like_first_cate_id_common_ratio
offline_like_second_cate_id_common_ratio
offline_like_site_common_ratio
offline_like_third_cate_id_common_ratio
```

#### 下单相关（2个剩余）

```
offline_order_site_common_ratio
offline_order_third_cate_id_common_ratio
```

#### 搜索点击相关（3个剩余）

```
offline_search_click_site_common_ratio
offline_search_click_third_cate_id_common_ratio
```

**Phase 2 建议**: 添加 chajia/site 和 like 相关特征，验证场景特异性

### 2.2 FG 交叉特征（22个）

#### 品牌交叉（5个）

```
brand_x_discount_intensity_fg
brand_x_f_req_month_fg
dev_brand_x_first_cate_id_fg
dev_brand_x_item_id_fg
dev_brand_x_related_goods_ids_fg
```

#### 类目交叉（8个）

```
cate_id_path_x_discount_intensity_fg
cate_id_path_x_f_req_month_fg
gender_x_first_cate_id_fg
gender_x_item_id_fg
gender_x_related_goods_ids_fg
gender_x_second_cate_id_fg
gender_x_third_cate_id_fg
login_city_x_first_cate_id_fg
```

#### 其他交叉（9个）

```
core_entity_x_f_req_month_fg
dev_brand_x_second_cate_id_fg
dev_brand_x_third_cate_id_fg
login_city_x_f_req_month_fg
login_city_x_item_id_fg
login_city_x_related_goods_ids_fg
login_city_x_second_cate_id_fg
login_city_x_third_cate_id_fg
price_tag_x_discount_intensity_fg
```

**Phase 3 建议**: 根据效果选择性添加高价值交叉特征

### 2.3 用户属性特征（14个）

#### 活跃度（3个）

```
active_bhv
active_days
bhv_gender
bhv_time
```

#### 用户属性（6个）

```
f_req_month
f_req_usertype
mmb_level
mmb_status
reg_time
reg_type
```

#### 其他（5个）

```
jpush
login_time
receive_push
user_status
is_atpush
is_not_disturb
is_subscribe_clockin
is_subscribe_discount
is_subscribe_savemoney
```

**Phase 2 建议**: 添加 active_days, mmb_level 等基础属性

### 2.4 商品属性特征（22个）

#### 商品基础（8个）

```
cate
cate_prefer
comment_tag
copyright_end
create_time
pub_time
shop_id
shop_type
```

#### 商品属性（7个）

```
city_level
city_region
modifiers
price_drop_freq
price_prefer
shop_life_time
shop_subtype
```

#### 商品标签（7个）

```
crowd_prefer
item_audience_prefer
item_class_prefer
item_comment_tag
item_gender_prefer
site_prefer
top_tag
```

**Phase 3 建议**: 添加 cate, comment_tag 等商品信息特征

### 2.5 系统字段（7个，不使用）

```
__item_id__
__mmb_id__
event_unix_time
request_id
page
type
scene
```

### 2.6 样本标记（14个，不使用）

```
is_click
is_conversion
is_favorite
is_like
is_bijia_click
is_bijia_conversion
is_haojia_click
is_haojia_conversion
is_trend_click
is_trend_conversion
is_home_scene
is_bijia_scene
is_haojia_scene
is_trend_scene
```

### 2.7 样本权重（1个，已使用）

```
search_weight
```

______________________________________________________________________

## 三、分阶段添加建议

### Phase 1（已完成）✅

- 15 个高价值特征
- 覆盖率提升: 7% → 14%

### Phase 2（建议）

- 添加 10 个比率特征（chajia/site, like 相关）
- 添加 3 个用户属性（active_days, mmb_level）
- 总计: +13 个

### Phase 3（可选）

- 添加 10 个 FG 交叉特征（高价值）
- 添加 10 个商品属性特征
- 总计: +20 个

______________________________________________________________________

## 四、特征价值评估

### 高价值（立即添加）

- offline_order\_\*\_common_ratio（转化信号）
- offline_chajia\_\*\_common_ratio（场景特异性）
- consume_power, convert_probability（质量信号）

### 中价值（Phase 2 添加）

- offline_like\_\*\_common_ratio（兴趣信号）
- active_days, mmb_level（用户属性）
- cate, comment_tag（商品属性）

### 低价值（暂不添加）

- 系统字段（无信息量）
- 样本标记（非特征）
- 部分 FG 交叉（冗余风险）

______________________________________________________________________

## 五、监控指标

### 特征覆盖率

- Phase 1: 196/211 = 92.9%
- Phase 2: 209/211 = 99.0%
- Phase 3: 211/211 = 100%

### 预期效果

- Phase 1: CTR +0.3-0.5%
- Phase 2: CTR +0.5-0.8%
- Phase 3: CTR +0.8-1.2%
