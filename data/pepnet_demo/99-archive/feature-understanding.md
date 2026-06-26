______________________________________________________________________

## date: 2026-05-30 tags: [archive, feature, data-schema] status: archived related: ["[[../10-architecture/data-schema]]"]

# Feature Understanding

## Feature Groups

### domain group

PEPNet 的 CDOT/LHUC/Bias 使用该组特征学习 **domain 条件向量**，用于对主网络（"all" 组）做 domain-specific 的权重缩放。

| 特征                               | 类型           | 来源                                                                | 维度 | 含义                                                       |
| ---------------------------------- | -------------- | ------------------------------------------------------------------- | :--: | ---------------------------------------------------------- |
| `mmb_id`                           | id_feature     | `user:mmb_id`                                                       |  32  | 用户 ID，hash_bucket 252w                                  |
| `item_id`                          | id_feature     | `item:item_id`                                                      |  32  | 商品 ID，hash_bucket 300w                                  |
| `f_req_page`                       | id_feature     | `user:f_req_page`                                                   |  4   | 页面来源（2 值：内容tab / 推荐tab）                        |
| `page`                             | id_feature     | `user:page`                                                         |  32  | 商品所在屏数（1～500+），用户耐心/深度信号                 |
| `user__kv_first_cate_id_click_15d` | lookup_feature | `user:user__kv_first_cate_id_click_15d` key 到 `item:first_cate_id` |  16  | 用户近 15 天对每个一级类目的点击次数，编码用户类目兴趣偏好 |

**domain 组特征设计思路：**

- 3 个粗粒度 ID（mmb_id, item_id, f_req_page）组成 user×item×page 的基准 domain 三元组
- `page` 替换 coarse 的 f_req_page 语义——屏位置编码用户浏览深度（p1 走马观花 vs p100+ 目标明确），不同 page 下的 CTR/CVR 模式差异显著，是强 domain 信号
- `user__kv_first_cate_id_click_15d` 是 user 对 category 的 KV 交叉特征：同类目推荐下，用户的近期类目点击分布编码了该 session 的兴趣场景
- 以上特征与主网络（"all" 组）特征正交，为 CDOT 提供 domain 差异化的信息

### all group

主网络使用的全部特征，经过 EPNet → LHUC-EPNet → PPNet → LHUC-PPNet → DCNv2 Cross → 各 Tower 输出。

**ID 类（~40 个）:**

| 特征                 | 来源                      | 维度 |  bucket  | 含义                       |
| -------------------- | ------------------------- | :--: | :------: | -------------------------- |
| `item_id`            | `item:item_id`            |  32  |   300w   | 商品 ID                    |
| `mmb_id`             | `user:mmb_id`             |  32  | 252w ZCH | 用户 ID                    |
| `spu_id`             | `item:spu_id`             |  24  |   300w   | 标准产品单元 ID            |
| `related_goods_ids`  | `item:related_goods_ids`  |  24  |   300w   | 关联商品 ID（多值）        |
| `tags`               | `item:tags`               |  24  |   626w   | 商品标签（多值）           |
| `cate_id_path`       | `item:cate_id_path`       |  12  |   20w    | 类目路径                   |
| `keyword`            | `item:keyword`            |  16  |   18w    | 商品关键词（多值）         |
| `brand`              | `item:brand`              |  16  |   20w    | 品牌 ID                    |
| `core_entity`        | `item:core_entity`        |  16  |   14w    | 核心实体                   |
| `username`           | `item:username`           |  12  |    5w    | 作者/发布者                |
| `third_cate_id`      | `item:third_cate_id`      |  12  |    2w    | 三级类目                   |
| `second_cate_id`     | `item:second_cate_id`     |  8   |   2000   | 二级类目                   |
| `first_cate_id`      | `item:first_cate_id`      |  8   |   300    | 一级类目                   |
| `site`               | `item:site`               |  8   |   410    | 站点                       |
| `publish_user`       | `item:publish_user`       |  8   |   2170   | 发布者                     |
| `discount_type`      | `item:discount_type`      |  8   |    3w    | 折扣类型（多值）           |
| `price_tag`          | `item:price_tag`          |  8   |   500    | 价格标签                   |
| `page`               | `user:page`               |  32  |   4580   | 屏数（也在 domain 组）     |
| `day_h`              | `user:day_h`              |  8   |   240    | 小时                       |
| `week_day`           | `user:week_day`           |  4   |    70    | 星期                       |
| `province`           | `user:province`           |  8   |   310    | 省                         |
| `city`               | `user:city`               |  8   |   3580   | 市                         |
| `login_province`     | `user:login_province`     |  8   |   4060   | 登录 IP 省                 |
| `login_city`         | `user:login_city`         |  8   |   4360   | 登录 IP 市                 |
| `app_version`        | `user:app_version`        |  8   |   3860   | App 版本                   |
| `os_type`            | `user:os_type`            |  4   |    40    | 操作系统                   |
| `os_version`         | `user:os_version`         |  8   |   2170   | 系统版本                   |
| `dev_brand`          | `user:dev_brand`          |  8   |   2000   | 设备品牌                   |
| `install_apps`       | `user:install_apps`       |  8   |   610    | 安装应用列表（多值）       |
| `lifecycle_tags`     | `user:lifecycle_tags`     |  4   |   140    | 生命周期标签（多值）       |
| `gender`             | `user:gender`             |  32  |    2     | 性别                       |
| `item_type`          | `item:item_type`          |  4   |    50    | 物料类型                   |
| `dianpufensi`        | `item:dianpufensi`        |  4   |    90    | 店铺粉丝数等级             |
| `dianpupingfen`      | `item:dianpupingfen`      |  4   |    70    | 店铺评分等级               |
| `discount_intensity` | `item:discount_intensity` |  8   |   180    | 折扣力度等级               |
| `first_cate_id`      | `item:first_cate_id`      |  8   |   300    | 一级类目                   |
| `gender_score`       | `item:gender_score`       |  4   |   110    | 性别适用评分               |
| `level`              | `item:level`              |  4   |    90    | 商品等级                   |
| `pinpaidengji`       | `item:pinpaidengji`       |  4   |    4     | 品牌等级                   |
| `promotion_channel`  | `item:promotion_channel`  |  4   |    80    | 推广渠道                   |
| `f_req_page`         | `user:f_req_page`         |  4   |    2     | 页面来源（也在 domain 组） |
| `reg_days`           | `user:reg_days`           |  8   |    —     | 注册天数（raw_feature）    |

**KV 交叉特征（lookup_feature）:**

用户行为 KV 特征，map 端是用户近期的行为计数，key 端是物品属性。输出是 user×item 的交叉 embedding。

| 特征                                  | map                                  | key         | 维度  | 含义                                  |
| ------------------------------------- | ------------------------------------ | ----------- | :---: | ------------------------------------- |
| 各类 `user__kv_{attr}_click_15d`      | 用户 15 天点击 KV                    | item 各属性 | 16-24 | 用户对该物品属性的历史点击次数        |
| 各类 `user__kv_{attr}_conversion_15d` | 用户 15 天转化 KV                    | item 各属性 | 16-24 | 用户对该物品属性的历史转化次数        |
| 各类 `user__kv_{attr}_favorite_15d`   | 用户 15 天收藏 KV                    | item 各属性 | 16-24 | 用户对该物品属性的历史收藏次数        |
| 各类 `user__kv_{attr}_{action}_rt1h`  | 近 1 小时实时 KV                     | item 各属性 | 16-24 | 实时行为（click/conversion/favorite） |
| ...                                   | 同模式，时间窗口：rt3h, rt12h, rt24h |             |       |                                       |

属性 `{attr}` 包括：`cate_id_path`, `brand`, `first_cate_id`, `second_cate_id`, `third_cate_id`, `price_tag`, `promotion_channel`, `publish_user`, `site`, `discount_intensity`, `dianpupingfen`, `pinpaidengji`, `dianpufensi`, `gender_score`, `item_type`, `spu_id`, `item_id`, `core_entity`, `username`, `related_goods_ids`

**Ratio 统计特征（raw_feature）:**

| 模式                                            | 示例                                     | 维度 | 含义                  |
| ----------------------------------------------- | ---------------------------------------- | :--: | --------------------- |
| `{attr}__ratio_click_exposure_{1d,3d,15d}`      | `first_cate_id__ratio_click_exposure_3d` |  8   | 属性粒度曝光→点击率   |
| `{attr}__ratio_conversion_exposure_{1d,3d,15d}` | `brand__ratio_conversion_exposure_15d`   |  8   | 属性粒度曝光→转化率   |
| `{attr}__ratio_favorite_click_{1d,3d,15d}`      | `cate_id_path__ratio_favorite_click_1d`  |  8   | 属性粒度点击→收藏率   |
| `item__ratio_{action}_click_{1d,3d,15d}`        | `item__ratio_conversion_click_15d`       |  4   | 全局物品粒度点击→转化 |
| `{user_segment}__ratio_{action}_exposure_15d`   | `gender__ratio_click_exposure_15d`       | 4-8  | 用户分群曝光→行为率   |

属性包括：`first_cate_id`, `second_cate_id`, `cate_id_path`, `brand`, `site`, `core_entity`, `price_tag`, `promotion_channel`, `discount_intensity`, `dianpupingfen`, `pinpaidengji`, `spu_id`, `publish_user`, `username`

用户分群：`gender`, `login_city`, `dev_brand`

**Combo 交叉特征（combo_feature / expr_feature）:**

| 特征                          | 含义                           |
| ----------------------------- | ------------------------------ |
| `login_city_x_{attr}_fg`      | 登录城市 × 物品属性 交叉       |
| `gender_x_{attr}_fg`          | 性别 × 物品属性 交叉           |
| `dev_brand_x_{attr}_fg`       | 设备品牌 × 物品属性 交叉       |
| `brand_x_price_tag_fg`        | 品牌 × 价格标签 交叉           |
| `brand_x_cate_id_path_fg`     | 品牌 × 类目路径 交叉           |
| `price_tag_x_cate_id_path_fg` | 价格标签 × 类目路径 交叉       |
| `price_tag_x_spu_id_fg`       | 价格标签 × SPU 交叉            |
| `pub_hours_fg`                | 发布距今小时数（expr_feature） |

**统计量特征（raw_feature）:**

| 特征                                           | 维度 | 含义                                            |
| ---------------------------------------------- | :--: | ----------------------------------------------- |
| `{user}__cnt_{action}_{15d}`                   | 4-8  | 用户 15 天行为计数（click/conversion/favorite） |
| `{user}__num_{action}_avg_current_price_{15d}` | 4-8  | 用户 15 天行为中平均价格                        |
| `{item}__cnt_{action}_{1d,3d,15d}`             |  4   | 物品各窗口行为计数                              |
| `{item}__ratio_{action1}_click_{1d,3d,15d}`    |  4   | 物品各窗口行为比率                              |
| `{item}__cnt_{action}_rt{1h,3h,12h,24h}`       | 4-8  | 物品实时行为计数                                |
| `reg_days`                                     |  8   | 注册天数                                        |
| `current_price`                                |  8   | 当前价格（float）                               |

## CDOT 特征选择（domain 组）推理

### 为什么不把更多特征加入 domain 组？

CDOT 将所有 domain 特征的 embed 压缩到 `input_dim=16` 的 bottleneck 向量。多余的低价值特征会浪费压缩 budget，稀释有效信号。

### 各特征候选评估

| 候选                                     |   结论    | 理由                                                                                                            |
| ---------------------------------------- | :-------: | --------------------------------------------------------------------------------------------------------------- |
| `mmb_id` (32d)                           |  ✅ 选中  | user 身份标识，domain 的基准维度                                                                                |
| `item_id` (32d)                          |  ✅ 选中  | item 身份标识                                                                                                   |
| `f_req_page` (4d)                        |  ✅ 选中  | 最粗粒度的页面上下文（内容tab/推荐tab），属于 domain                                                            |
| `page` (32d)                             |  ✅ 选中  | 精细屏数位置，编码用户耐心深度 — p1 浏览态 vs p100+ 明确意图，CTR/CVR 模式完全不同                              |
| `user__kv_first_cate_id_click_15d` (16d) |  ✅ 选中  | 用户类目偏好 KV：同类目推荐下，同一 mmb_id 可能今天想买衣服明天想买手机，类目级 KV 捕捉这个 session domain 切换 |
| `day_h` (8d)                             | ❌ 待验证 | 时间维度有价值但 domain 组已有 page 和 f_req_page 覆盖部分上下文信号                                            |
| `week_day` (4d)                          | ❌ 待验证 | 同 day_h，边际收益存疑                                                                                          |
| 其他 KV（brand, price_tag...）           |    ❌     | 类目是推荐最强的 domain 维度，品牌/价格标签等边际递减                                                           |
| 用户画像（gender, city, os_type...）     |    ❌     | 与 `mmb_id` 高度共线（用户 ID 已吸收人口属性信息）                                                              |
| Ratio 特征                               |    ❌     | ratio 是连续的 0-1 值，CDOT compress 到 16 维后信息大量丢失；更适合放在 main group 让 EPNet/PPNet 直接消费      |
| Combo 特征                               |    ❌     | 已经是交叉特征，放入 domain 会导致 domain 表达过度强调某组交叉                                                  |
