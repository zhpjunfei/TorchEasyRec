# 多场景融合方案 - 对抗性审核勘验 SQL

**目标分区**: dt = '20261003'

______________________________________________________________________

## 一、采样逻辑一致性验证（HIGH）

### 1.1 验证 v3 各场景的采样逻辑

```sql
-- 检查 v3 label table 是否对 bijia/haojia/trend 有 INNER JOIN 过滤
SELECT
    'bijia' AS scene,
    COUNT(1) AS total,
    SUM(CASE WHEN is_bijia_click = 1 THEN 1 ELSE 0 END) AS pos,
    SUM(CASE WHEN is_bijia_click = 0 THEN 1 ELSE 0 END) AS neg,
    ROUND(SUM(CASE WHEN is_bijia_click = 1 THEN 1.0 ELSE 0 END) / COUNT(1), 4) AS pos_rate
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '20261003' AND is_bijia_scene = 1

UNION ALL

SELECT
    'haojia' AS scene,
    COUNT(1) AS total,
    SUM(CASE WHEN is_haojia_click = 1 THEN 1 ELSE 0 END) AS pos,
    SUM(CASE WHEN is_haojia_click = 0 THEN 1 ELSE 0 END) AS neg,
    ROUND(SUM(CASE WHEN is_haojia_click = 1 THEN 1.0 ELSE 0 END) / COUNT(1), 4) AS pos_rate
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '20261003' AND is_haojia_scene = 1

UNION ALL

SELECT
    'trend' AS scene,
    COUNT(1) AS total,
    SUM(CASE WHEN is_trend_click = 1 THEN 1 ELSE 0 END) AS pos,
    SUM(CASE WHEN is_trend_click = 0 THEN 1 ELSE 0 END) AS neg,
    ROUND(SUM(CASE WHEN is_trend_click = 1 THEN 1.0 ELSE 0 END) / COUNT(1), 4) AS pos_rate
FROM home_flow_2606_ctrcvr_sorter_label_table_v3
WHERE dt = '20261003' AND is_trend_scene = 1;
```

**判断标准**：

- 如果 bijia/haojia 都是 INNER JOIN 过滤，正负样本应该都存在
- 如果 trend 是直接透传，应该也有正负样本

### 1.2 验证 v1 的编码过程是否有额外采样

```sql
-- 检查 v1 各场景的正负样本分布
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) AS home_pos,
    SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) AS home_neg,
    SUM(CASE WHEN is_bijia_click = 1 THEN 1 ELSE 0 END) AS bijia_pos,
    SUM(CASE WHEN is_haojia_click = 1 THEN 1 ELSE 0 END) AS haojia_pos,
    SUM(CASE WHEN is_trend_click = 1 THEN 1 ELSE 0 END) AS trend_pos
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END;
```

______________________________________________________________________

## 二、样本量不均衡分析（HIGH）

### 2.1 各场景正负样本详细分布

```sql
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total_pv,
    -- home 场景
    SUM(CASE WHEN is_click = 1 THEN 1 ELSE 0 END) AS home_pos,
    SUM(CASE WHEN is_click = 0 THEN 1 ELSE 0 END) AS home_neg,
    ROUND(SUM(CASE WHEN is_click = 1 THEN 1.0 ELSE 0 END) / COUNT(1), 4) AS home_pos_rate,
    -- 各场景辅助任务
    SUM(CASE WHEN is_bijia_click = 1 THEN 1 ELSE 0 END) AS bijia_pos,
    SUM(CASE WHEN is_bijia_click = 0 THEN 1 ELSE 0 END) AS bijia_neg,
    SUM(CASE WHEN is_haojia_click = 1 THEN 1 ELSE 0 END) AS haojia_pos,
    SUM(CASE WHEN is_haojia_click = 0 THEN 1 ELSE 0 END) AS haojia_neg,
    SUM(CASE WHEN is_trend_click = 1 THEN 1 ELSE 0 END) AS trend_pos,
    SUM(CASE WHEN is_trend_click = 0 THEN 1 ELSE 0 END) AS trend_neg
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END;
```

**判断标准**：

- 如果某场景负样本过多（如 haojia 正负比 1:6.9），辅助任务可能过拟合
- 建议：正负比 > 1:5 时考虑过采样正样本或降低权重

### 2.2 跨场景用户行为分析

```sql
-- 检查同一用户在多场景的行为
SELECT
    mmb_id,
    SUM(is_home_scene) AS home_pv,
    SUM(is_bijia_scene) AS bijia_pv,
    SUM(is_haojia_scene) AS haojia_pv,
    SUM(is_trend_scene) AS trend_pv,
    SUM(is_click) AS home_click,
    SUM(is_bijia_click) AS bijia_click,
    SUM(is_haojia_click) AS haojia_click,
    SUM(is_trend_click) AS trend_click
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY mmb_id
HAVING SUM(is_home_scene) > 0 AND SUM(is_bijia_scene) > 0
LIMIT 100;
```

**目的**：确认是否存在跨场景的行为迁移（在 bijia 点击的用户，在 home 是否也点击）

______________________________________________________________________

## 三、评估指标验证（HIGH）

### 3.1 各场景 AUC 评估准备

```sql
-- 检查各场景的样本量是否足够计算稳定的 AUC
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS sample_size,
    CASE
        WHEN COUNT(1) >= 100000 THEN '足够'
        ELSE '不足'
    END AS sufficient
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END;
```

### 3.2 预测分布校准分析（训练后执行）

```sql
-- 训练后检查各场景的预测概率分布
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS sample_size,
    ROUND(AVG(probs_ctr), 4) AS avg_pred,
    ROUND(STDDEV(probs_ctr), 4) AS std_pred,
    ROUND(MIN(probs_ctr), 4) AS min_pred,
    ROUND(MAX(probs_ctr), 4) AS max_pred,
    ROUND(SUM(is_click) * 100.0 / COUNT(1), 2) AS actual_ctr
FROM {predicted_table}
WHERE dt >= '20261003'
GROUP BY
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END;
```

______________________________________________________________________

## 四、序列特征有效性验证（MEDIUM）

### 4.1 各场景序列特征贡献度

```sql
-- 检查序列特征的有效性
SELECT
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END AS scene,
    COUNT(1) AS total,
    -- click_50 序列有效性
    ROUND(AVG(ARRAY_LENGTH(click_50_seq__item_id)), 2) AS click_50_avg_len,
    SUM(CASE WHEN ARRAY_LENGTH(click_50_seq__item_id) >= 10 THEN 1 ELSE 0 END) AS click_50_full_cnt,
    ROUND(SUM(CASE WHEN ARRAY_LENGTH(click_50_seq__item_id) >= 10 THEN 1.0 ELSE 0 END) * 100 / COUNT(1), 2) AS click_50_full_pct,
    -- chajia_50 序列有效性
    ROUND(AVG(ARRAY_LENGTH(chaprice_click_50_seq__item_id)), 2) AS chajia_50_avg_len,
    SUM(CASE WHEN ARRAY_LENGTH(chaprice_click_50_seq__item_id) >= 10 THEN 1 ELSE 0 END) AS chajia_50_full_cnt,
    ROUND(SUM(CASE WHEN ARRAY_LENGTH(chaprice_click_50_seq__item_id) >= 10 THEN 1.0 ELSE 0 END) * 100 / COUNT(1), 2) AS chajia_50_full_pct
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'
GROUP BY
    CASE
        WHEN is_home_scene = 1 THEN 'home'
        WHEN is_bijia_scene = 1 THEN 'bijia'
        WHEN is_haojia_scene = 1 THEN 'haojia'
        WHEN is_trend_scene = 1 THEN 'trend'
    END;
```

______________________________________________________________________

## 五、辅助任务权重敏感性分析（MEDIUM）

### 5.1 计算各辅助任务的样本贡献度

```sql
-- 评估各辅助任务的样本量是否足够支撑 weight=1.0
SELECT
    'bijia_click' AS task_name,
    SUM(is_bijia_scene) AS total_samples,
    SUM(is_bijia_click) AS pos_samples,
    ROUND(SUM(is_bijia_click) * 100.0 / SUM(is_bijia_scene), 2) AS pos_rate,
    CASE
        WHEN SUM(is_bijia_scene) >= 1000000 AND SUM(is_bijia_click) >= 100000 THEN '足够'
        ELSE '不足'
    END AS sufficient
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'

UNION ALL

SELECT
    'haojia_click' AS task_name,
    SUM(is_haojia_scene) AS total_samples,
    SUM(is_haojia_click) AS pos_samples,
    ROUND(SUM(is_haojia_click) * 100.0 / SUM(is_haojia_scene), 2) AS pos_rate,
    CASE
        WHEN SUM(is_haojia_scene) >= 1000000 AND SUM(is_haojia_click) >= 100000 THEN '足够'
        ELSE '不足'
    END AS sufficient
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003'

UNION ALL

SELECT
    'trend_click' AS task_name,
    SUM(is_trend_scene) AS total_samples,
    SUM(is_trend_click) AS pos_samples,
    ROUND(SUM(is_trend_click) * 100.0 / SUM(is_trend_scene), 2) AS pos_rate,
    CASE
        WHEN SUM(is_trend_scene) >= 1000000 AND SUM(is_trend_click) >= 100000 THEN '足够'
        ELSE '不足'
    END AS sufficient
FROM home_flow_2608_ctrcvr_sorter_config_pyfg_encoded_shuffled_60d_v1
WHERE dt = '20261003';
```

______________________________________________________________________

## 执行建议

| 优先级 | SQL      | 目的               |
| ------ | -------- | ------------------ |
| 🔴 高  | 1.1, 1.2 | 验证采样逻辑一致性 |
| 🔴 高  | 2.1      | 确认正负样本分布   |
| 🟡 中  | 3.1      | 评估样本量是否足够 |
| 🟡 中  | 4.1      | 验证序列特征有效性 |
| 🟢 低  | 5.1      | 辅助任务权重决策   |

请执行上述 SQL 后，把结果贴给我，我帮你判断是否需要调整配置。
