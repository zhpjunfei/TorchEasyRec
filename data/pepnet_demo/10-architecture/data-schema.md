______________________________________________________________________

## date: 2026-06-07 tags: [architecture, data, schema, features] related: \[[pepnet-dcn-ple]\]

# Data Schema — 特征体系

> 本项目使用的全部特征 (40+). 详细勘探见 `99-archive/feature_understanding.md` (老文件, 保留供追溯).

## 特征分组 (用于 PEPNetDCNPLE)

| Group   | 字段示例                                            | 在模型中作用              |
| :------ | :-------------------------------------------------- | :------------------------ |
| `main`  | item_id, mmb_id, page, user features, item features | 主信号, 过 main_group_dim |
| `cdot`  | f_req_domain, f_req_page                            | 域内 slot 交互 (CDOT)     |
| `bias`  | site_e, level_e, page                               | 首维 1-dim 偏置           |
| `lhuc`  | site_e, level_e                                     | EPNet/PPNet 门控          |
| `dcnv2` | (同 main)                                           | CrossV2 显式交叉          |

## 特征分类总览

| 类别                   | 举例                                                        | 模型使用           |
| :--------------------- | :---------------------------------------------------------- | :----------------- |
| 基础信息               | item_id, mmb_id, page, scene                                | ✅ id_feature      |
| 用户画像               | gender, province, app_version, dev_brand                    | ✅ id_feature      |
| 商品属性               | item_type, brand, cate_id_path, spu_id                      | ✅ id_feature      |
| 商品价格               | current_price, price_tag, discount_type                     | ✅ id/raw_feature  |
| 商品店铺               | dianpufensi, dianpupingfen, publish_user                    | ✅ id_feature      |
| 分类层级               | first_cate_id, second_cate_id, third_cate_id                | ✅ id_feature      |
| 时间特征               | day_h, week_day, pub_hours_fg, reg_days                     | ✅ id/expr_feature |
| 用户统计(15d)          | user\_\_cnt_click_15d, user\_\_cnt_conversion_15d           | ✅ raw_feature     |
| 用户KV统计(click)      | user\_\_kv_brand_click_15d, user\_\_kv_site_click_15d       | ✅ lookup_feature  |
| 用户KV统计(conversion) | user\_\_kv_brand_conversion_15d                             | ✅ lookup_feature  |
| 用户KV统计(favorite)   | user\_\_kv_brand_favorite_15d                               | ✅ lookup_feature  |
| 物品统计(多窗口)       | first_cate_id\_\_ratio_click_exposure_15d/3d/1d             | ✅ raw_feature     |
| 交叉统计               | gender\_\_ratio_click_exposure_15d, login_city\_\_ratio\_\* | ✅ raw_feature     |
| 序列特征               | click_10_seq, conversion_5_seq, favorite_10_seq             | ✅ sequence (DIN)  |
| 标签偏好               | cate_prefer, consume_power, price_prefer                    | ✅ id_feature      |
| 请求解析               | f_req_page, f_req_domain                                    | ✅ id_feature      |

## 关键特征详解

### f_req_domain (本项目重要)

- **类型**: `id_feature`, `hash_bucket_size: 500`, `embedding_dim: 8` (默认, v7 实验 d=16/32)
- **来源**: user request 解析
- **CDOT 角色**: 必填, v6_ple_d 实验证实 in CDOT 才有正增益
- **详见**: \[[../20-experiments/v6-design-matrix|v6 设计矩阵]\] / \[[../20-experiments/v7-ple-d-variants|v7 变种]\]

### f_req_page

- **类型**: `id_feature`, `hash_bucket_size: 100`, `embedding_dim: 4`
- **CDOT 角色**: 与 f_req_domain 同属 cdot_group
- **fix**: 之前 vocab_list 误配, 已用 hash_bucket_size=100 修复 (+2.6pp 单次)

### pub_hours_fg

- **类型**: `expr_feature`, `embedding_dim: 8`, 20 buckets
- **CDOT 角色**: 可选, v7_ple_ph 实验证实 PLE 下是噪声
- **详细分析**: 见 `99-archive/feature_understanding.md` (pub_hours 关键发现)
  - P50=8.57h, P75=21.59h, P90=33.52h, P99=48.29h
  - CTR 峰值 2h (3.79%) — 新品红利
  - CVR 峰值 16-20h — 用户决策滞后
- **处理方案**: LEAST > ABS (避免 TS-Skew)

### site_e / level_e

- **site**: 350+ 个值, site 346 (话题) click→CVR 0% (content stream)
- **level**: B(26%) → F(41%) click→CVR monotonic, embedding_dim=8
- **详见**: `99-archive/site_mapping.md` (老文件, 保留追溯)

### is_reedited_after_exposure

- **角色**: **噪声标记 (梯度调节器)**, 不是预测特征
- **离线训练**: 告诉模型"这条 pub_hours=0 的真实商品更老"
- **线上推理**: 永远 = 0, 不生效
- **类比**: sample_weight 降权, 不是预测信号

## 统计

- 特征数: **40+**
- 总 embedding 参数: ~50M
- mmb_id: zch 动态缓存, `zch_size: 2529348, eviction_interval: 2, lfu, threshold: 3.0`

## 文件位置

- `data/pepnet_demo/config/v6/home_flow_2604_v6_ple_d.config` — v6_ple_d config (含全部特征)
- `data/pepnet_demo/sql/sample_v2/home_flow_2604_ctrcvr_sorter_config_pyfg_encoded_v3.py` — fg_task v3_training_set

## 下一步

- \[[pepnet-dcn-ple|PEPNetDCNPLE]\] — 特征在模型中的具体使用
- \[[../30-data/site-mapping|site_mapping]\] — site/level 分布
