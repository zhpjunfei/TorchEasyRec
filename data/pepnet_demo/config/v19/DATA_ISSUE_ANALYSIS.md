# v1 数据问题分析

## 问题描述

| 指标     | v3 (单天) | v1 (60天) | 差异    |
| -------- | --------- | --------- | ------- |
| home PV  | 116万     | 6566万    | +56x    |
| home CTR | 3.0%      | 36.9%     | +33.9pp |

## 核心疑问

用户确认：**采样逻辑只在 v3 有，v1 没有**

那为什么 v1 的 home CTR 从 3% 变成了 37%？

## 可能原因分析

### 假设 1: v1 包含了完整曝光样本

- v3: 邻接点击采样（只保留 click_cnt > 0 的样本）
- v1: 完整曝光（所有曝光都保留）
- 如果是这样，v1 的 CTR 应该更低（~0.1%），而不是更高

**结论**: 假设 1 不成立

### 假设 2: v1 的 feature store 有特殊采样

- feature store 在 join 特征时可能做了额外的采样
- 比如：只保留有点击的样本作为正样本，再加等量负样本
- 这样会导致 CTR = 50%

**结论**: 需要检查 feature store 的配置

### 假设 3: 查询统计口径不一致

- v3 的 CTR 计算可能有误
- 或者 v1 的查询条件有误

**结论**: 需要重新验证

## 验证 SQL

```sql
-- 1. 检查 home 场景的点击分布
SELECT
    is_click,
    COUNT(1) AS cnt
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003' AND is_home_scene = 1
GROUP BY is_click;

-- 2. 检查是否有其他过滤条件
SELECT
    COUNT(1) AS total,
    SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) AS clicks,
    SUM(CASE WHEN is_conversion = 1 THEN 1 ELSE 0 END) AS conversions,
    SUM(CASE WHEN is_favorite = 1 THEN 1 ELSE 0 END) AS favorites,
    SUM(CASE WHEN is_like = 1 THEN 1 ELSE 0 END) AS likes
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003' AND is_home_scene = 1;
```

## 下一步行动

1. 执行上述 SQL，确认 v1 的实际点击分布
1. 检查 feature store 的配置，看是否有特殊采样逻辑
1. 如果 v1 确实有采样问题，需要重新构建数据
1. 或者直接使用 v3 数据训练（跳过 feature store）

## 配置状态

当前 v19 配置已修正：

- ✅ task_space_indicator_label 使用场景标记
- ✅ label_fields 包含所有需要的字段
- ⚠️ 数据采样逻辑需要确认
