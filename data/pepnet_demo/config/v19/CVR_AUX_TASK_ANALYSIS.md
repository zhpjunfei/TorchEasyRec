# CVR 辅助任务分析

## 当前配置

### 主任务

```protobuf
task_towers {
  tower_name: "cvr"
  label_name: "is_conversion"
  weight: 1.0
  task_space_indicator_label: "is_click"  # 只在 home 且有点击时学习
}
```

### 辅助任务（当前只有 CTR）

```protobuf
task_towers { tower_name: "bijia_click", ... }
task_towers { tower_name: "haojia_click", ... }
task_towers { tower_name: "trend_click", ... }
```

## 为什么没有 CVR 辅助任务？

### 可能原因

1. **转化样本稀疏**

   - 主任务 CVR 的正样本率 = 11.69%（home 点击后转化）
   - 但这是点击后的转化，实际曝光转化率更低
   - 对于 bijia/haojia/trend，转化样本可能更少

1. **业务定义不同**

   - home 场景：is_conversion = 购买转化
   - bijia 场景：is_bijia_conversion = 搜索转化？
   - 各场景的转化定义可能不一致

1. **数据质量**

   - 需要验证各场景的转化样本量是否足够

## 需要验证的数据

请执行以下 SQL 检查各场景的转化数据：

```sql
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    SUM(is_click) AS clicks,
    SUM(is_bijia_click) AS bijia_clicks,
    SUM(is_haojia_click) AS haojia_clicks,
    SUM(is_trend_click) AS trend_clicks,
    SUM(is_conversion) AS home_convs,
    SUM(is_bijia_conversion) AS bijia_convs,
    SUM(is_haojia_conversion) AS haojia_convs,
    SUM(is_trend_conversion) AS trend_convs
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY ...;
```

## 判断标准

| 场景   | 判断标准                     | 建议                |
| ------ | ---------------------------- | ------------------- |
| bijia  | 转化样本 > 10万 且 CTVR > 5% | 可以加 CVR 辅助任务 |
| haojia | 转化样本 > 5万 且 CTVR > 3%  | 谨慎添加，降低权重  |
| trend  | 转化样本 > 10万 且 CTVR > 5% | 可以加 CVR 辅助任务 |

## 如果添加 CVR 辅助任务

```protobuf
task_towers {
  tower_name: "bijia_conversion"
  label_name: "is_bijia_conversion"
  weight: 0.3  # 转化样本少，降低权重
  task_space_indicator_label: "is_bijia_scene_click"  # 只在 bijia 且有点击时学习
  train_metrics { auc {} }
  train_metrics { grouped_auc { grouping_key: "is_bijia_scene" } }
  losses { binary_cross_entropy {} }
  mlp { hidden_units: [64, 32]; use_ln: true; dropout_ratio: 0.1 }
}
```

## 下一步

1. 执行 SQL 检查各场景转化数据
1. 根据结果决定是否添加 CVR 辅助任务
1. 如果添加，需要更新三个 Phase 配置
