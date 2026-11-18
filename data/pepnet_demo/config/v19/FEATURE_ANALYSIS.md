# 特征工程分析报告

**分析对象**: home_flow_2608_v19_multiscene.config vs home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v5.ddl
**分析日期**: 2026-10-17

______________________________________________________________________

## 一、特征覆盖统计

| 指标                     | 数量 |
| ------------------------ | ---- |
| DDL 中特征数             | 211  |
| Config 中使用特征数      | 761  |
| DDL 中有但 Config 未使用 | 123  |
| Config 中有但 DDL 中没有 | 673  |

**说明**: Config 中的 673 个特征来自其他表 JOIN，DDL 中的 123 个未使用特征值得深入分析。

______________________________________________________________________

## 二、未使用特征分类

### 2.1 比率特征 (20个) — 高价值

```
offline_chajia_brand_common_ratio
offline_chajia_first_cate_id_common_ratio
offline_chajia_second_cate_id_common_ratio
offline_chajia_site_common_ratio
offline_chajia_third_cate_id_common_ratio

offline_like_brand_common_ratio
offline_like_first_cate_id_common_ratio
offline_like_second_cate_id_common_ratio
offline_like_site_common_ratio
offline_like_third_cate_id_common_ratio

offline_order_brand_common_ratio
offline_order_first_cate_id_common_ratio
offline_order_second_cate_id_common_ratio
offline_order_site_common_ratio
offline_order_third_cate_id_common_ratio

offline_search_click_brand_common_ratio
offline_search_click_first_cate_id_common_ratio
offline_search_click_second_cate_id_common_ratio
offline_search_click_site_common_ratio
offline_search_click_third_cate_id_common_ratio
```

**价值分析**:

- chajia（查价）相关比率 → 直接关联 trend 场景用户行为
- order（下单）相关比率 → 强转化信号
- search_click（搜索点击）→ 反映搜索意图

### 2.2 FG交叉特征 (22个)

```
brand_x_discount_intensity_fg
brand_x_f_req_month_fg
cate_id_path_x_discount_intensity_fg
cate_id_path_x_f_req_month_fg
core_entity_x_f_req_month_fg
dev_brand_x_first_cate_id_fg
dev_brand_x_item_id_fg
dev_brand_x_related_goods_ids_fg
dev_brand_x_second_cate_id_fg
dev_brand_x_third_cate_id_fg
gender_x_first_cate_id_fg
gender_x_item_id_fg
gender_x_related_goods_ids_fg
gender_x_second_cate_id_fg
gender_x_third_cate_id_fg
login_city_x_f_req_month_fg
login_city_x_first_cate_id_fg
login_city_x_item_id_fg
login_city_x_related_goods_ids_fg
login_city_x_second_cate_id_fg
login_city_x_third_cate_id_fg
price_tag_x_discount_intensity_fg
```

**价值分析**: 用户属性 × 商品属性的个性化交叉特征

### 2.3 标量特征 (81个) — 分层建议

#### A类：高价值（建议立即添加）

```
consume_power        # 消费能力
his_high_level       # 历史高等级
gold_coin            # 金币余额
convert_probability  # 转化率预测
potential_score      # 潜力评分
srh_hot              # 搜索热度
active_days          # 活跃天数
```

#### B类：中价值（可选添加）

```
mmb_level            # 用户等级
city_level           # 城市等级
title_vector         # 标题向量
coupon_titles        # 优惠券标题
```

#### C类：低价值（暂不添加）

```
# 系统字段（已有或无用）
__item_id__, __mmb_id__, event_unix_time, request_id, page, type

# 样本标记（非特征）
is_bijia_click, is_haojia_click, is_trend_click, is_conversion...
is_home_scene, is_bijia_scene, is_haojia_scene, is_trend_scene
search_weight
```

______________________________________________________________________

## 三、特征工程建议

### 优先级 P0（立即添加）

1. **比率特征** — 离线行为偏好

   - offline_chajia\_\*\_common_ratio (5个) → 关联trend场景
   - offline_order\_\*\_common_ratio (5个) → 强转化信号
   - offline_search_click\_\*\_common_ratio (5个) → 搜索意图

1. **用户质量特征**

   - consume_power, his_high_level, gold_coin
   - convert_probability, potential_score, srh_hot

### 优先级 P1（后续迭代）

3. **FG交叉特征** — 逐步添加高价值交叉
1. **数组特征处理** — active_days, bhv_gender 等

### 优先级 P2（评估后决定）

5. **标题/评论特征** — title_vector, comment_tag 等

______________________________________________________________________

## 四、风险提示

1. **特征冗余**: 新特征可能与现有特征高度相关
1. **训练时间**: 特征增加会导致训练时间增长
1. **过拟合风险**: 新特征需要验证泛化能力

______________________________________________________________________

## 五、实施建议

**方案 A：保守增量**

- 仅添加 P0 级特征（10-15个）
- 风险低，易于迭代

**方案 B：全面增强**

- 添加 P0 + P1 级特征（30-40个）
- 需要评估训练时间

**方案 C：实验对比**

- 创建多个 config 版本
- A/B 测试不同特征组合
